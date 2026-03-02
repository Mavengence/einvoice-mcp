"""Unit tests for validate tools (KoSIT mocked)."""

import httpx
import respx

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.validate import validate_xrechnung, validate_zugferd

KOSIT_URL = "http://kosit-mock:8081"

MOCK_VALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1">
  <rep:assessment>
    <rep:profileName>XRechnung 3.0.2</rep:profileName>
  </rep:assessment>
</rep:report>
"""

MOCK_INVALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1"
            xmlns:svrl="http://purl.oclc.org/dml/schematron/output/">
  <svrl:schematron-output>
    <svrl:failed-assert id="BR-01" location="/Invoice" flag="error">
      <svrl:text>BT-1 missing</svrl:text>
    </svrl:failed-assert>
  </svrl:schematron-output>
</rep:report>
"""


class TestValidateXrechnung:
    @respx.mock
    async def test_valid(self, sample_invoice_data: InvoiceData) -> None:
        xml = build_xml(sample_invoice_data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung(xml, client)
        assert result["valid"] is True
        await client.close()

    @respx.mock
    async def test_invalid(self) -> None:
        respx.post(f"{KOSIT_URL}/").respond(406, text=MOCK_INVALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung("<Invoice/>", client)
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        await client.close()

    @respx.mock
    async def test_connection_error(self) -> None:
        respx.post(f"{KOSIT_URL}/").mock(side_effect=httpx.ConnectError("refused"))
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung("<Invoice/>", client)
        assert result["valid"] is False
        assert any("erreichbar" in e["message"] for e in result["errors"])
        await client.close()


class TestValidateXrechnungPreScreen:
    """Verify defusedxml pre-screen catches non-XML before KoSIT call."""

    async def test_non_xml_content(self) -> None:
        """Non-XML content returns German error without calling KoSIT."""
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung("This is not XML at all", client)
        assert result["valid"] is False
        assert any("kein gültiges XML" in e["message"] for e in result["errors"])
        await client.close()

    async def test_binary_junk(self) -> None:
        """Binary-like content detected before KoSIT."""
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung("\x00\x01\x02 binary junk", client)
        assert result["valid"] is False
        assert any("kein gültiges XML" in e["message"] for e in result["errors"])
        await client.close()

    async def test_malformed_xml(self) -> None:
        """Malformed XML (unclosed tag) caught by pre-screen."""
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung("<root><unclosed>", client)
        assert result["valid"] is False
        assert any("kein gültiges XML" in e["message"] for e in result["errors"])
        await client.close()

    async def test_xxe_attack_blocked(self) -> None:
        """XXE entity attack blocked by defusedxml pre-screen."""
        xxe = '<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><root>&xxe;</root>'
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung(xxe, client)
        assert result["valid"] is False
        assert any("DTD" in e["message"] or "Entity" in e["message"] for e in result["errors"])
        await client.close()


class TestValidateZugferd:
    async def test_invalid_base64(self) -> None:
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_zugferd("not-valid-base64!!!", client)
        assert result["valid"] is False
        assert any("Base64" in e["message"] for e in result["errors"])
        await client.close()
