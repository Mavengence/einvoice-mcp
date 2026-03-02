"""Tests for server helper functions."""

import json

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.server import _build_invoice_data


class TestBuildInvoiceData:
    def test_valid_data(self) -> None:
        items = json.dumps([{"description": "Test", "quantity": 1, "unit_price": 100}])
        result = _build_invoice_data(
            invoice_id="RE-001",
            issue_date="2026-01-01",
            seller_name="Seller GmbH",
            seller_street="Str 1",
            seller_city="Berlin",
            seller_postal_code="10115",
            seller_country_code="DE",
            seller_tax_id="DE123456789",
            buyer_name="Buyer GmbH",
            buyer_street="Str 2",
            buyer_city="München",
            buyer_postal_code="80999",
            buyer_country_code="DE",
            items_json=items,
        )
        assert isinstance(result, InvoiceData)
        assert result.invoice_id == "RE-001"

    def test_invalid_json_items(self) -> None:
        result = _build_invoice_data(
            invoice_id="RE-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json="not-valid-json",
        )
        assert isinstance(result, str)
        assert "JSON" in result

    def test_invalid_profile(self) -> None:
        items = json.dumps([{"description": "Test", "quantity": 1, "unit_price": 100}])
        result = _build_invoice_data(
            invoice_id="RE-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json=items,
            profile="INVALID_PROFILE",
        )
        assert isinstance(result, str)
        assert "Ungültiges Profil" in result

    def test_pydantic_validation_error_returns_german_string(self) -> None:
        """Pydantic errors (e.g. invalid date) must return a German error string, not raise."""
        items = json.dumps([{"description": "Test", "quantity": 1, "unit_price": 100}])
        result = _build_invoice_data(
            invoice_id="RE-001",
            issue_date="not-a-date",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json=items,
        )
        assert isinstance(result, str)
        assert "Fehler" in result
        assert "Ungültige Rechnungsdaten" in result

    def test_pydantic_validation_error_country_code(self) -> None:
        """Country code too long triggers Pydantic validation, caught as German error."""
        items = json.dumps([{"description": "Test", "quantity": 1, "unit_price": 100}])
        result = _build_invoice_data(
            invoice_id="RE-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DEU",
            seller_tax_id="",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json=items,
        )
        assert isinstance(result, str)
        assert "Fehler" in result

    def test_invalid_allowances_charges_json(self) -> None:
        """Invalid JSON in allowances_charges_json returns German error string."""
        items = json.dumps([{"description": "Test", "quantity": 1, "unit_price": 100}])
        result = _build_invoice_data(
            invoice_id="RE-001",
            issue_date="2026-01-01",
            seller_name="S",
            seller_street="S",
            seller_city="S",
            seller_postal_code="00000",
            seller_country_code="DE",
            seller_tax_id="",
            buyer_name="B",
            buyer_street="B",
            buyer_city="B",
            buyer_postal_code="00000",
            buyer_country_code="DE",
            items_json=items,
            allowances_charges_json="not-valid-json",
        )
        assert isinstance(result, str)
        assert "allowances_charges" in result
