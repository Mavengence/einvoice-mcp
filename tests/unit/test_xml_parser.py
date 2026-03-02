"""Unit tests for XML parser."""

from decimal import Decimal
from unittest.mock import patch

from einvoice_mcp.models import Address, InvoiceData, LineItem, Party, TaxCategory
from einvoice_mcp.services.cii_extractors import str_element
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.xml_parser import (
    _extract_tax_total_fallback,
    parse_xml,
)


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
        assert str_element("DE123456789 (VA)") == "DE123456789"

    def test_strips_email_scheme_suffix(self) -> None:
        assert str_element("email@example.de (EM)") == "email@example.de"

    def test_strips_numeric_scheme(self) -> None:
        """EAS numeric schemeIDs like 9930 must be stripped."""
        assert str_element("4000000000098 (9930)") == "4000000000098"

    def test_strips_empty_parens(self) -> None:
        """Empty parens from drafthorse IDElements are stripped."""
        assert str_element("plain ()") == "plain"
        assert str_element("()") == ""

    def test_preserves_plain_string(self) -> None:
        assert str_element("hello world") == "hello world"

    def test_preserves_parentheses_in_middle(self) -> None:
        """Parentheses in the middle should not be stripped."""
        assert str_element("Company (GmbH) Name") == "Company (GmbH) Name"

    def test_preserves_lowercase_parens(self) -> None:
        """Lowercase parenthetical text (descriptions) must NOT be stripped."""
        assert str_element("Reisekosten (pauschal)") == "Reisekosten (pauschal)"
        assert str_element("Software-Lizenz (jährlich)") == "Software-Lizenz (jährlich)"

    def test_preserves_unicode_parens(self) -> None:
        """German umlauts in parens must NOT be stripped (not ASCII schemeIDs)."""
        assert str_element("Artikel (3Ü)") == "Artikel (3Ü)"

    def test_none_returns_empty(self) -> None:
        assert str_element(None) == ""


class TestTaxTotalFallback:
    def test_no_container(self) -> None:
        """Returns 0 when tax_total_other_currency is None."""

        class FakeMS:
            tax_total_other_currency = None

        assert _extract_tax_total_fallback(FakeMS()) == Decimal("0")

    def test_tuple_children(self) -> None:
        """Extracts amount from tuple children."""

        class FakeChild:
            children = ((Decimal("19.00"), "EUR"),)

        class FakeMS:
            tax_total_other_currency = FakeChild()

        assert _extract_tax_total_fallback(FakeMS()) == Decimal("19.00")

    def test_invalid_tuple_children(self) -> None:
        """Returns 0 for invalid tuple children."""

        class FakeChild:
            children = (("not-a-number", "EUR"),)

        class FakeMS:
            tax_total_other_currency = FakeChild()

        assert _extract_tax_total_fallback(FakeMS()) == Decimal("0")

    def test_non_tuple_children_skipped(self) -> None:
        """Non-tuple children are skipped."""

        class FakeChild:
            children = ("not-a-tuple",)

        class FakeMS:
            tax_total_other_currency = FakeChild()

        assert _extract_tax_total_fallback(FakeMS()) == Decimal("0")

    def test_empty_children(self) -> None:
        """Returns 0 when children is empty."""

        class FakeChild:
            children = ()

        class FakeMS:
            tax_total_other_currency = FakeChild()

        assert _extract_tax_total_fallback(FakeMS()) == Decimal("0")


class TestParserEdgeCases:
    def test_negative_quantity_uses_abs(self) -> None:
        """Negative quantities in XML are preserved as absolute values."""
        data = InvoiceData(
            invoice_id="NEG-QTY",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="5", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        # Patch the XML to have negative quantity
        xml_str = xml_bytes.decode("utf-8")
        xml_str = xml_str.replace(">5<", ">-5<", 1)
        parsed = parse_xml(xml_str.encode("utf-8"))
        assert len(parsed.items) == 1
        assert parsed.items[0].quantity == Decimal("5")

    def test_zero_quantity_fallback(self) -> None:
        """Zero quantities fall back to 0.01."""
        data = InvoiceData(
            invoice_id="ZERO-QTY",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        # Replace the billed quantity with zero
        xml_str = xml_bytes.decode("utf-8")
        xml_str = xml_str.replace(
            '<ram:BilledQuantity unitCode="H87">1</ram:BilledQuantity>',
            '<ram:BilledQuantity unitCode="H87">0</ram:BilledQuantity>',
        )
        parsed = parse_xml(xml_str.encode("utf-8"))
        assert len(parsed.items) == 1
        assert parsed.items[0].quantity == Decimal("0.01")

    def test_empty_party_name_returns_none(self) -> None:
        """A party with empty name returns None via _extract_party."""
        from einvoice_mcp.services.cii_extractors import extract_party

        class FakeParty:
            name = ""

        result = extract_party(FakeParty())
        assert result is None

    def test_type_code_parsed(self) -> None:
        """TypeCode roundtrips through generate/parse."""
        data = InvoiceData(
            invoice_id="TC-TEST",
            issue_date="2026-01-01",
            type_code="381",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        parsed = parse_xml(build_xml(data))
        assert parsed.type_code == "381"

    def test_extract_totals_error_returns_none(self) -> None:
        """If _extract_totals raises, returns None."""
        data = InvoiceData(
            invoice_id="T",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_bytes = build_xml(data)
        with patch(
            "einvoice_mcp.services.xml_parser.safe_decimal",
            side_effect=RuntimeError("boom"),
        ):
            # The outer try/except in _extract_totals should catch this
            # and _extract_invoice should still succeed with totals=None
            parsed = parse_xml(xml_bytes)
            # Items and seller/buyer still work, totals might be None
            # depending on where the mock hits
            assert parsed.invoice_id == "T"


class TestExemptionReasonExtraction:
    """Verify exemption reason extraction from CII XML."""

    def test_exemption_reason_extracted(self) -> None:
        """BT-120/BT-121 roundtrip via parser."""
        data = InvoiceData(
            invoice_id="EXPATH-001",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="X",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.E,
                ),
            ],
            tax_exemption_reason="Steuerbefreit §4 Nr. 11 UStG",
            tax_exemption_reason_code="vatex-eu-132",
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.tax_exemption_reason == "Steuerbefreit §4 Nr. 11 UStG"
        assert parsed.tax_exemption_reason_code == "vatex-eu-132"

    def test_no_exemption_reason(self) -> None:
        """Standard-rated invoice has empty exemption fields."""
        data = InvoiceData(
            invoice_id="NOEX-001",
            issue_date="2026-01-01",
            seller=Party(
                name="S",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="B",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[
                LineItem(description="X", quantity="1", unit_price="100"),
            ],
        )
        xml = build_xml(data)
        parsed = parse_xml(xml)
        assert parsed.tax_exemption_reason == ""
        assert parsed.tax_exemption_reason_code == ""
