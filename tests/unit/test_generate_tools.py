"""Unit tests for generate tools (KoSIT mocked)."""

import httpx
import respx

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.generate import generate_xrechnung, generate_zugferd

KOSIT_URL = "http://kosit-mock:8081"

MOCK_VALID_REPORT = """\
<?xml version="1.0" encoding="UTF-8"?>
<rep:report xmlns:rep="http://www.xoev.de/de/validator/varl/1">
  <rep:assessment>
    <rep:profileName>XRechnung 3.0.2</rep:profileName>
  </rep:assessment>
</rep:report>
"""


class TestGenerateXrechnung:
    @respx.mock
    async def test_success(self, sample_invoice_data: InvoiceData) -> None:
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await generate_xrechnung(sample_invoice_data, client)
        assert result["success"] is True
        assert "xml_content" in result
        assert "<ram:ID>RE-2026-001</ram:ID>" in result["xml_content"]
        assert result["totals"]["currency"] == "EUR"
        await client.close()

    @respx.mock
    async def test_validation_failure_still_returns_xml(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        respx.post(f"{KOSIT_URL}/").mock(side_effect=httpx.ConnectError("refused"))
        client = KoSITClient(base_url=KOSIT_URL)
        result = await generate_xrechnung(sample_invoice_data, client)
        assert result["success"] is True
        assert "xml_content" in result
        assert result["validation"]["valid"] is False
        await client.close()


class TestGenerateZugferd:
    @respx.mock
    async def test_success(self, sample_invoice_data: InvoiceData) -> None:
        respx.post(f"{KOSIT_URL}/").respond(200, text=MOCK_VALID_REPORT)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await generate_zugferd(sample_invoice_data, client)
        assert result["success"] is True
        assert "pdf_base64" in result
        assert result["pdf_size_bytes"] > 0
        assert result["totals"]["currency"] == "EUR"
        await client.close()

    @respx.mock
    async def test_validation_failure_still_returns_pdf(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        respx.post(f"{KOSIT_URL}/").mock(side_effect=httpx.ConnectError("refused"))
        client = KoSITClient(base_url=KOSIT_URL)
        result = await generate_zugferd(sample_invoice_data, client)
        assert result["success"] is True
        assert "pdf_base64" in result
        await client.close()
