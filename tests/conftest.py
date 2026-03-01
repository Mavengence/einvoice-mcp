"""Shared test fixtures."""

import pytest

from einvoice_mcp.models import (
    Address,
    InvoiceData,
    InvoiceProfile,
    LineItem,
    Party,
    TaxCategory,
)
from einvoice_mcp.services.kosit import KoSITClient


@pytest.fixture
def sample_seller() -> Party:
    return Party(
        name="TechCorp GmbH",
        address=Address(
            street="Hauptstr. 1",
            city="Berlin",
            postal_code="10115",
            country_code="DE",
        ),
        tax_id="DE123456789",
        electronic_address="rechnungen@techcorp.de",
    )


@pytest.fixture
def sample_buyer() -> Party:
    return Party(
        name="ClientCorp GmbH",
        address=Address(
            street="Kundenweg 42",
            city="München",
            postal_code="80999",
            country_code="DE",
        ),
        tax_id="DE987654321",
        electronic_address="einkauf@clientcorp.de",
    )


@pytest.fixture
def sample_items() -> list[LineItem]:
    return [
        LineItem(
            description="Software-Beratung",
            quantity="10",
            unit_code="HUR",
            unit_price="150.00",
            tax_rate="19.00",
            tax_category=TaxCategory.S,
        ),
        LineItem(
            description="Hosting-Service (Monat)",
            quantity="1",
            unit_code="H87",
            unit_price="49.99",
            tax_rate="19.00",
            tax_category=TaxCategory.S,
        ),
    ]


@pytest.fixture
def sample_invoice_data(
    sample_seller: Party,
    sample_buyer: Party,
    sample_items: list[LineItem],
) -> InvoiceData:
    return InvoiceData(
        invoice_id="RE-2026-001",
        issue_date="2026-03-01",
        seller=sample_seller,
        buyer=sample_buyer,
        items=sample_items,
        currency="EUR",
        payment_terms_days=30,
        buyer_reference="LEITWEG-123-456",
        profile=InvoiceProfile.XRECHNUNG,
        seller_contact_name="Max Mustermann",
        seller_contact_email="max@techcorp.de",
        seller_contact_phone="+49 30 1234567",
    )


@pytest.fixture
def kosit_client() -> KoSITClient:
    return KoSITClient(base_url="http://localhost:8081")
