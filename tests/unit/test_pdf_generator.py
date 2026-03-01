"""Unit tests for PDF generator."""

from einvoice_mcp.models import InvoiceData
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
