"""Unit tests for XML parser."""

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.xml_parser import _str_element, parse_xml


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

    def test_roundtrip_tax_total_not_zero(self, sample_invoice_data: InvoiceData) -> None:
        """Tax total must roundtrip correctly (was bug: drafthorse MultiCurrencyField)."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.totals is not None
        assert parsed.totals.tax_total > 0
        # Model and parsed should match
        expected = sample_invoice_data.total_tax()
        assert parsed.totals.tax_total == expected

    def test_roundtrip_seller_tax_id_no_scheme_suffix(
        self, sample_invoice_data: InvoiceData
    ) -> None:
        """Verify parsed tax_id does not contain the scheme suffix like 'DE123 (VA)'."""
        xml_bytes = build_xml(sample_invoice_data)
        parsed = parse_xml(xml_bytes)
        assert parsed.seller is not None
        assert parsed.seller.tax_id is not None
        assert "(" not in parsed.seller.tax_id
        assert parsed.seller.tax_id == "DE123456789"


class TestStrElement:
    def test_strips_scheme_suffix(self) -> None:
        """IDElement.__str__ returns 'value (schemeID)' — _str_element must strip it."""
        assert _str_element("DE123456789 (VA)") == "DE123456789"

    def test_strips_email_scheme_suffix(self) -> None:
        assert _str_element("email@example.de (EM)") == "email@example.de"

    def test_strips_empty_scheme(self) -> None:
        assert _str_element("plain ()") == "plain"

    def test_preserves_plain_string(self) -> None:
        assert _str_element("hello world") == "hello world"

    def test_preserves_parentheses_in_middle(self) -> None:
        """Parentheses in the middle should not be stripped."""
        assert _str_element("Company (GmbH) Name") == "Company (GmbH) Name"

    def test_none_returns_empty(self) -> None:
        assert _str_element(None) == ""
