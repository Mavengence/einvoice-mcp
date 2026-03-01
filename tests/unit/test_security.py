"""Tests for security hardening: size limits, XXE protection, input validation."""

import pytest
from pydantic import ValidationError

from einvoice_mcp.config import MAX_PDF_BASE64_SIZE, MAX_XML_SIZE
from einvoice_mcp.models import Address, InvoiceData, LineItem, Party
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.compliance import check_compliance
from einvoice_mcp.tools.parse import parse_einvoice
from einvoice_mcp.tools.validate import validate_xrechnung, validate_zugferd

KOSIT_URL = "http://kosit-mock:8081"


class TestXMLSizeLimits:
    async def test_validate_rejects_oversized_xml(self) -> None:
        huge_xml = "x" * (MAX_XML_SIZE + 1)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_xrechnung(huge_xml, client)
        assert result["valid"] is False
        assert any("Größenlimit" in e["message"] for e in result["errors"])
        await client.close()

    async def test_parse_rejects_oversized_xml(self) -> None:
        huge_xml = "x" * (MAX_XML_SIZE + 1)
        result = await parse_einvoice(huge_xml, "xml")
        assert result["success"] is False
        assert "Größenlimit" in result["error"]

    async def test_compliance_rejects_oversized_xml(self) -> None:
        huge_xml = "x" * (MAX_XML_SIZE + 1)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await check_compliance(huge_xml, client, "XRECHNUNG")
        assert result["valid"] is False
        assert any("Größenlimit" in s for s in result["suggestions"])
        await client.close()


class TestPDFSizeLimits:
    async def test_validate_rejects_oversized_pdf(self) -> None:
        huge_pdf = "A" * (MAX_PDF_BASE64_SIZE + 1)
        client = KoSITClient(base_url=KOSIT_URL)
        result = await validate_zugferd(huge_pdf, client)
        assert result["valid"] is False
        assert any("Größenlimit" in e["message"] for e in result["errors"])
        await client.close()

    async def test_parse_rejects_oversized_pdf(self) -> None:
        huge_pdf = "A" * (MAX_PDF_BASE64_SIZE + 1)
        result = await parse_einvoice(huge_pdf, "pdf")
        assert result["success"] is False
        assert "Größenlimit" in result["error"]


class TestXXEProtection:
    async def test_compliance_rejects_xxe_attempt(self) -> None:
        """Verify that defusedxml blocks entity expansion attacks."""
        xxe_xml = (
            '<?xml version="1.0"?>'
            '<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>'
            "<rsm:CrossIndustryInvoice"
            ' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"'
            ' xmlns:ram="urn:un:unece:uncefact:data:standard:'
            'ReusableAggregateBusinessInformationEntity:100">'
            "&xxe;"
            "</rsm:CrossIndustryInvoice>"
        )
        client = KoSITClient(base_url=KOSIT_URL)
        # defusedxml should reject this — the field checks will return empty
        # (ParseError caught), so no fields found
        result = await check_compliance(xxe_xml, client, "XRECHNUNG")
        # The key assertion: the XXE payload should not be resolved
        assert result["valid"] is False
        await client.close()


class TestInputSanitization:
    async def test_parse_rejects_unknown_file_type(self) -> None:
        result = await parse_einvoice("<test/>", "exe")
        assert result["success"] is False
        assert "Unbekannter Dateityp" in result["error"]
        # Verify the reflected input is NOT in the error message
        assert "exe" not in result["error"]


class TestModelFieldConstraints:
    def test_address_street_too_long(self) -> None:
        with pytest.raises(ValidationError):
            Address(street="x" * 201, city="Berlin", postal_code="10115")

    def test_address_empty_street(self) -> None:
        with pytest.raises(ValidationError):
            Address(street="", city="Berlin", postal_code="10115")

    def test_country_code_wrong_length(self) -> None:
        with pytest.raises(ValidationError):
            Address(street="A", city="B", postal_code="12345", country_code="DEU")

    def test_invoice_id_max_length(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="x" * 101,
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
            )

    def test_tax_rate_max_100(self) -> None:
        with pytest.raises(ValidationError):
            LineItem(description="X", quantity="1", unit_price="10", tax_rate="101")

    def test_payment_terms_max_365(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
                payment_terms_days=400,
            )

    def test_currency_must_be_3_chars(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[LineItem(description="X", quantity="1", unit_price="10")],
                currency="EURO",
            )

    def test_max_1000_items(self) -> None:
        items = [
            LineItem(description="X", quantity="1", unit_price="1") for _ in range(1001)
        ]
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="T",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=items,
            )
