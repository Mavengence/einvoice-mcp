"""Unit tests for Pydantic models."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from einvoice_mcp.models import (
    Address,
    ComplianceResult,
    FieldCheck,
    InvoiceData,
    InvoiceProfile,
    LineItem,
    ParsedInvoice,
    Party,
    TaxCategory,
    ValidationResult,
)


class TestAddress:
    def test_valid_address(self) -> None:
        addr = Address(street="Hauptstr. 1", city="Berlin", postal_code="10115")
        assert addr.country_code == "DE"

    def test_custom_country(self) -> None:
        addr = Address(street="Rue 1", city="Paris", postal_code="75001", country_code="FR")
        assert addr.country_code == "FR"


class TestParty:
    def test_party_with_tax_id(self, sample_seller: Party) -> None:
        assert sample_seller.name == "TechCorp GmbH"
        assert sample_seller.tax_id == "DE123456789"

    def test_party_without_tax_id(self) -> None:
        party = Party(
            name="Test GmbH",
            address=Address(street="Test 1", city="Test", postal_code="12345"),
        )
        assert party.tax_id is None


class TestLineItem:
    def test_valid_line_item(self) -> None:
        item = LineItem(description="Test", quantity="5", unit_price="100.00")
        assert item.quantity == Decimal("5")
        assert item.tax_rate == Decimal("19.00")
        assert item.unit_code == "H87"

    def test_zero_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LineItem(description="Test", quantity="0", unit_price="100.00")

    def test_negative_quantity_rejected(self) -> None:
        with pytest.raises(ValidationError):
            LineItem(description="Test", quantity="-1", unit_price="100.00")

    def test_tax_categories(self) -> None:
        for cat in TaxCategory:
            item = LineItem(description="Test", quantity="1", unit_price="10", tax_category=cat)
            assert item.tax_category == cat


class TestInvoiceData:
    def test_totals_single_item(self) -> None:
        data = InvoiceData(
            invoice_id="TEST-001",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="10", unit_price="100.00", tax_rate="19.00")],
        )
        assert data.total_net() == Decimal("1000.00")
        assert data.total_tax() == Decimal("190.0000")
        assert data.total_gross() == Decimal("1190.0000")

    def test_totals_multiple_items(self, sample_invoice_data: InvoiceData) -> None:
        net = sample_invoice_data.total_net()
        assert net == Decimal("10") * Decimal("150.00") + Decimal("1") * Decimal("49.99")
        assert net == Decimal("1549.99")

    def test_total_tax_uses_per_group_rounding(self) -> None:
        """BR-CO-14: total_tax() must use per-group rounding, not per-item.

        3 separate items at 33.33 @7%: per-item gives 3*2.33=6.99,
        per-group gives (99.99*7/100).quantize(0.01) = 7.00.
        """
        data = InvoiceData(
            invoice_id="ROUND",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[
                LineItem(description="A", quantity="1", unit_price="33.33", tax_rate="7"),
                LineItem(description="B", quantity="1", unit_price="33.33", tax_rate="7"),
                LineItem(description="C", quantity="1", unit_price="33.33", tax_rate="7"),
                LineItem(description="D", quantity="1", unit_price="100.00", tax_rate="19"),
            ],
        )
        # Per-group: 7% group basis=99.99, tax=7.00
        #            19% group basis=100.00, tax=19.00
        # Total tax = 26.00 (per-group), NOT 25.99 (per-item)
        assert data.total_tax() == Decimal("26.00")

    def test_empty_items_rejected(self) -> None:
        with pytest.raises(ValidationError):
            InvoiceData(
                invoice_id="TEST",
                issue_date="2026-01-01",
                seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
                buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
                items=[],
            )

    def test_default_profile(self) -> None:
        data = InvoiceData(
            invoice_id="TEST",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="10")],
        )
        assert data.profile == InvoiceProfile.XRECHNUNG


class TestValidationResult:
    def test_valid_result(self) -> None:
        r = ValidationResult(valid=True, profile="XRechnung 3.0")
        assert r.valid is True
        assert len(r.errors) == 0

    def test_invalid_result(self) -> None:
        r = ValidationResult(
            valid=False,
            errors=[{"message": "BT-10 missing", "severity": "error"}],
        )
        assert r.valid is False
        assert len(r.errors) == 1


class TestParsedInvoice:
    def test_default_values(self) -> None:
        p = ParsedInvoice()
        assert p.invoice_id == ""
        assert p.items == []
        assert p.totals is None


class TestComplianceResult:
    def test_passing_compliance(self) -> None:
        c = ComplianceResult(
            valid=True,
            kosit_valid=True,
            field_checks=[
                FieldCheck(field="BT-1", name="Rechnungsnummer", present=True, value="RE-001"),
            ],
            suggestions=["Validierung erfolgreich: XRechnung 3.0 konform."],
        )
        assert c.valid is True
        assert len(c.missing_fields) == 0

    def test_failing_compliance(self) -> None:
        c = ComplianceResult(
            valid=False,
            kosit_valid=False,
            missing_fields=["BT-10"],
            suggestions=["BT-10 fehlt"],
        )
        assert c.valid is False
        assert "BT-10" in c.missing_fields
