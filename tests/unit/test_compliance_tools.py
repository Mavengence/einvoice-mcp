"""Unit tests for compliance tool (KoSIT mocked)."""

import httpx
import respx

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.compliance import check_compliance

KOSIT_URL = "http://kosit-mock:8081"

MOCK_VALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1">
  <rep:assessment>
    <rep:profileName>XRechnung 3.0.2</rep:profileName>
  </rep:assessment>
</rep:report>
"""


class TestCheckCompliance:
    @respx.mock
    async def test_valid_xrechnung(self, sample_invoice_data: InvoiceData) -> None:
        xml = build_xml(sample_invoice_data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert result["valid"] is True
        assert result["kosit_valid"] is True
        assert any("erfolgreich" in s for s in result["suggestions"])
        await client.close()

    @respx.mock
    async def test_kosit_connection_error(self, sample_invoice_data: InvoiceData) -> None:
        xml = build_xml(sample_invoice_data).decode("utf-8")
        respx.post(f"{KOSIT_URL}/").mock(side_effect=httpx.ConnectError("refused"))
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(xml, client, "XRECHNUNG")
        assert result["valid"] is False
        assert result["kosit_valid"] is None
        await client.close()

    async def test_minimal_xml_missing_fields(self) -> None:
        minimal = (
            '<?xml version="1.0"?>'
            "<rsm:CrossIndustryInvoice"
            ' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"'
            ' xmlns:ram="urn:un:unece:uncefact:data:standard:'
            'ReusableAggregateBusinessInformationEntity:100">'
            "</rsm:CrossIndustryInvoice>"
        )
        respx.post(f"{KOSIT_URL}/").mock(side_effect=httpx.ConnectError("refused"))
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(minimal, client, "XRECHNUNG")
        assert result["valid"] is False
        assert len(result["missing_fields"]) > 0
        await client.close()
