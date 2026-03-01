"""Unit tests for MCP tool functions (KoSIT mocked)."""

import httpx
import respx

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.parse import parse_einvoice
from einvoice_mcp.tools.validate import validate_xrechnung

KOSIT_URL = "http://kosit-mock:8081"

MOCK_VALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1">
  <rep:assessment>
    <rep:profileName>XRechnung 3.0.2</rep:profileName>
  </rep:assessment>
</rep:report>
"""


class TestValidateXrechnung:
    @respx.mock
    async def test_valid_xml(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")

        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)

        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung(xml_str, client)
        assert result["valid"] is True
        await client.close()

    @respx.mock
    async def test_connection_error(self) -> None:
        respx.post(f"{KOSIT_URL}/").mock(side_effect=httpx.ConnectError("refused"))
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung("<Invoice/>", client)
        assert result["valid"] is False
        assert len(result["errors"]) > 0
        await client.close()


class TestParseEinvoice:
    async def test_parse_xml(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        result = await parse_einvoice(xml_str, "xml")
        assert result["success"] is True
        assert result["invoice"]["invoice_id"] == "RE-2026-001"

    async def test_invalid_file_type(self) -> None:
        result = await parse_einvoice("<Invoice/>", "docx")
        assert result["success"] is False
        assert "Unbekannter Dateityp" in result["error"]

    async def test_invalid_base64_pdf(self) -> None:
        result = await parse_einvoice("not-base64!!!", "pdf")
        assert result["success"] is False
