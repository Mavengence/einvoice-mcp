"""Unit tests for PDF generator."""

from decimal import Decimal

from einvoice_mcp.models import (
    Address,
    AllowanceCharge,
    InvoiceData,
    LineItem,
    Party,
    TaxCategory,
)
from einvoice_mcp.services.pdf_generator import generate_invoice_pdf


class TestGenerateInvoicePdf:
    def test_produces_pdf_bytes(self, sample_invoice_data: InvoiceData) -> None:
        pdf_bytes = generate_invoice_pdf(sample_invoice_data)
        assert pdf_bytes is not None
        assert len(pdf_bytes) > 100

    def test_pdf_header(self, sample_invoice_data: InvoiceData) -> None:
        pdf_bytes = generate_invoice_pdf(sample_invoice_data)
        assert pdf_bytes[:5] == b"%PDF-"

    def test_reasonable_size(self, sample_invoice_data: InvoiceData) -> None:
        pdf_bytes = generate_invoice_pdf(sample_invoice_data)
        # A valid invoice PDF should be between 1KB and 1MB
        assert 1_000 < len(pdf_bytes) < 1_000_000

    def test_multi_rate_tax_breakdown(self) -> None:
        """PDF with multiple tax rates shows per-category breakdown."""
        data = InvoiceData(
            invoice_id="MR-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="Standard",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
                LineItem(
                    description="Reduced",
                    quantity="1",
                    unit_price="50",
                    tax_rate=Decimal("7"),
                ),
                LineItem(
                    description="Exempt",
                    quantity="1",
                    unit_price="200",
                    tax_rate=Decimal("0"),
                    tax_category=TaxCategory.E,
                ),
            ],
            tax_exemption_reason="Steuerbefreit gemäß §4 UStG",
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 1_000

    def test_multi_rate_with_doc_charge(self) -> None:
        """PDF with multi-rate items AND a document-level charge."""
        data = InvoiceData(
            invoice_id="MRC-001",
            issue_date="2026-01-01",
            seller=Party(
                name="Seller",
                address=Address(street="S", city="C", postal_code="00000"),
                tax_id="DE123456789",
            ),
            buyer=Party(
                name="Buyer",
                address=Address(street="B", city="C", postal_code="00000"),
            ),
            items=[
                LineItem(
                    description="A",
                    quantity="1",
                    unit_price="100",
                    tax_rate=Decimal("19"),
                ),
                LineItem(
                    description="B",
                    quantity="1",
                    unit_price="50",
                    tax_rate=Decimal("7"),
                ),
            ],
            allowances_charges=[
                AllowanceCharge(
                    charge=True,
                    amount=Decimal("10"),
                    reason="Versandkosten",
                    tax_rate=Decimal("19"),
                ),
            ],
        )
        pdf_bytes = generate_invoice_pdf(data)
        assert pdf_bytes[:5] == b"%PDF-"
        assert len(pdf_bytes) > 1_000
