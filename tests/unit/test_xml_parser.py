"""Unit tests for XML parser."""

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.xml_parser import parse_xml


class TestParseXml:
    def test_roundtrip_invoice_id(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.invoice_id == "RE-2026-001"

    def test_roundtrip_seller(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.name == "TechCorp GmbH"
        assert parsed.seller.address.city == "Berlin"

    def test_roundtrip_buyer(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.buyer is not None
        assert parsed.buyer.name == "ClientCorp GmbH"

    def test_roundtrip_currency(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.currency == "EUR"

    def test_roundtrip_profile(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert "xrechnung" in parsed.profile.lower() or "16931" in parsed.profile

    def test_roundtrip_has_items(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert len(parsed.items) >= 1

    def test_roundtrip_totals(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.totals is not None
        assert parsed.totals.net_total > 0
        assert parsed.totals.gross_total > parsed.totals.net_total
