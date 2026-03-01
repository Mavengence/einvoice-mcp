"""Unit tests for compliance checker (field checks only, KoSIT mocked)."""

from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.tools.compliance import _check_fields


class TestCheckFields:
    def test_valid_xrechnung_has_bt1(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        checks = _check_fields(xml_str)
        bt1 = next((c for c in checks if c.field == "BT-1"), None)
        assert bt1 is not None
        assert bt1.present is True
        assert bt1.value == "RE-2026-001"

    def test_valid_xrechnung_has_seller_name(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        checks = _check_fields(xml_str)
        bt27 = next((c for c in checks if c.field == "BT-27"), None)
        assert bt27 is not None
        assert bt27.present is True

    def test_valid_xrechnung_has_buyer_reference(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        checks = _check_fields(xml_str)
        bt10 = next((c for c in checks if c.field == "BT-10"), None)
        assert bt10 is not None
        assert bt10.present is True

    def test_minimal_xml_missing_fields(self) -> None:
        minimal_xml = (
            '<?xml version="1.0"?>'
            "<rsm:CrossIndustryInvoice"
            ' xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"'
            ' xmlns:ram="urn:un:unece:uncefact:data:standard:'
            'ReusableAggregateBusinessInformationEntity:100">'
            "</rsm:CrossIndustryInvoice>"
        )
        checks = _check_fields(minimal_xml)
        required_missing = [c for c in checks if c.required and not c.present]
        assert len(required_missing) > 0

    def test_invalid_xml_returns_empty(self) -> None:
        checks = _check_fields("not xml at all")
        assert checks == []
