"""Integration tests requiring a running KoSIT Validator.

Run with: make docker-up && make test-integration

These tests are skipped by default. Enable with:
    pytest tests/integration -m integration
"""

from decimal import Decimal

import pytest

from einvoice_mcp.models import Address, InvoiceData, LineItem, Party
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.services.xml_parser import parse_xml
from einvoice_mcp.tools.compliance import check_compliance
from einvoice_mcp.tools.generate import generate_xrechnung
from einvoice_mcp.tools.validate import validate_xrechnung


def _sample_invoice() -> InvoiceData:
    return InvoiceData(
        invoice_id="INT-2026-001",
        issue_date="2026-03-01",
        seller=Party(
            name="TechCorp GmbH",
            address=Address(
                street="Friedrichstraße 100",
                city="Berlin",
                postal_code="10117",
                country_code="DE",
            ),
            tax_id="DE123456789",
            electronic_address="rechnungen@techcorp.de",
            contact_name="Max Mustermann",
            contact_phone="+49 30 12345678",
            contact_email="max.mustermann@techcorp.de",
        ),
        buyer=Party(
            name="Stadtverwaltung Musterstadt",
            address=Address(
                street="Rathausplatz 1",
                city="Musterstadt",
                postal_code="12345",
                country_code="DE",
            ),
            electronic_address="einkauf@musterstadt.de",
        ),
        items=[
            LineItem(
                description="Software-Beratung",
                quantity=Decimal("40"),
                unit_code="HUR",
                unit_price=Decimal("150.00"),
                tax_rate=Decimal("19.00"),
            ),
        ],
        leitweg_id="04011000-12345-67",
        delivery_date="2026-02-28",
        payment_terms_text="Zahlbar innerhalb von 30 Tagen netto",
        payment_means_type_code="58",
        seller_iban="DE89370400440532013000",
    )


@pytest.mark.integration
class TestKoSITIntegration:
    """Tests that require a running KoSIT Validator on localhost:8081."""

    @pytest.fixture
    async def kosit(self) -> KoSITClient:
        client = KoSITClient()
        yield client  # type: ignore[misc]
        await client.close()

    async def test_kosit_health(self, kosit: KoSITClient) -> None:
        """KoSIT Validator should be reachable."""
        healthy = await kosit.health_check()
        assert healthy, "KoSIT Validator not reachable — run 'make docker-up'"

    async def test_generate_and_validate_xrechnung(self, kosit: KoSITClient) -> None:
        """Generate XRechnung → validate with real KoSIT → should be valid."""
        data = _sample_invoice()
        result = await generate_xrechnung(data, kosit)
        assert result["success"] is True
        assert result["kosit_valid"] is True

    async def test_validate_raw_xml(self, kosit: KoSITClient) -> None:
        """Build XML directly → validate with KoSIT."""
        data = _sample_invoice()
        xml_bytes = build_xml(data)
        xml_str = xml_bytes.decode("utf-8")
        result = await validate_xrechnung(xml_str, kosit)
        assert result["valid"] is True

    async def test_full_roundtrip(self, kosit: KoSITClient) -> None:
        """Generate → Validate → Parse → Compliance — full cycle."""
        data = _sample_invoice()

        # Generate
        gen_result = await generate_xrechnung(data, kosit)
        assert gen_result["success"] is True
        xml = gen_result["xml_content"]

        # Parse
        xml_bytes = xml.encode("utf-8")
        parsed = parse_xml(xml_bytes)
        assert parsed.invoice_id == "INT-2026-001"
        assert parsed.seller.name == "TechCorp GmbH"
        assert parsed.buyer_reference == "04011000-12345-67"
        assert parsed.payment_means_type_code == "58"

        # Compliance
        comp = await check_compliance(xml, kosit, "XRECHNUNG")
        assert comp["kosit_valid"] is True
        assert comp["valid"] is True

    async def test_invalid_xml_rejected(self, kosit: KoSITClient) -> None:
        """KoSIT should reject incomplete CII XML."""
        invalid_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<rsm:CrossIndustryInvoice '
            'xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100">'
            "</rsm:CrossIndustryInvoice>"
        )
        result = await validate_xrechnung(invalid_xml, kosit)
        assert result["valid"] is False
