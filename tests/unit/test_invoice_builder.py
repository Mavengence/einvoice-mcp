"""Unit tests for invoice XML builder."""

from xml.etree import ElementTree as ET

from einvoice_mcp.models import InvoiceData, InvoiceProfile
from einvoice_mcp.services.invoice_builder import GUIDELINE_MAP, build_xml

CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}


class TestBuildXml:
    def test_produces_valid_xml(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        assert xml_bytes is not None
        assert len(xml_bytes) > 0
        # Should be parseable XML
        root = ET.fromstring(xml_bytes)
        assert root is not None

    def test_contains_invoice_id(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        doc_id = root.find(".//rsm:ExchangedDocument/ram:ID", CII_NS)
        assert doc_id is not None
        assert doc_id.text == "RE-2026-001"

    def test_contains_seller(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        seller_name = root.find(".//ram:SellerTradeParty/ram:Name", CII_NS)
        assert seller_name is not None
        assert seller_name.text == "TechCorp GmbH"

    def test_contains_buyer(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        buyer_name = root.find(".//ram:BuyerTradeParty/ram:Name", CII_NS)
        assert buyer_name is not None
        assert buyer_name.text == "ClientCorp GmbH"

    def test_contains_line_items(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        # Should contain both item descriptions
        assert "Software-Beratung" in xml_str
        assert "Hosting-Service" in xml_str

    def test_xrechnung_guideline(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        expected = GUIDELINE_MAP[InvoiceProfile.XRECHNUNG]
        assert expected in xml_str

    def test_zugferd_profile(self, sample_invoice_data: InvoiceData) -> None:
        data = sample_invoice_data.model_copy(update={"profile": InvoiceProfile.ZUGFERD_EN16931})
        xml_bytes = build_xml(data)
        xml_str = xml_bytes.decode("utf-8")
        expected = GUIDELINE_MAP[InvoiceProfile.ZUGFERD_EN16931]
        assert expected in xml_str

    def test_buyer_reference_set(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        assert "LEITWEG-123-456" in xml_str

    def test_currency_eur(self, sample_invoice_data: InvoiceData) -> None:
        xml_bytes = build_xml(sample_invoice_data)
        xml_str = xml_bytes.decode("utf-8")
        assert "EUR" in xml_str
