"""Unit tests for invoice XML builder."""

from decimal import Decimal
from xml.etree import ElementTree as ET

from einvoice_mcp.models import Address, InvoiceData, InvoiceProfile, LineItem, Party
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

    def test_tax_registration_scheme_id_correct(self, sample_invoice_data: InvoiceData) -> None:
        """CRITICAL: Verify TaxRegistration schemeID='VA' with tax ID as text, not inverted."""
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        seller_tax_id = root.find(
            ".//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID", CII_NS
        )
        assert seller_tax_id is not None
        assert seller_tax_id.text == "DE123456789"
        assert seller_tax_id.get("schemeID") == "VA"

    def test_buyer_tax_registration_scheme_id(self, sample_invoice_data: InvoiceData) -> None:
        """Verify buyer TaxRegistration has correct schemeID='VA'."""
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        buyer_tax_id = root.find(
            ".//ram:BuyerTradeParty/ram:SpecifiedTaxRegistration/ram:ID", CII_NS
        )
        assert buyer_tax_id is not None
        assert buyer_tax_id.text == "DE987654321"
        assert buyer_tax_id.get("schemeID") == "VA"

    def test_seller_electronic_address_bt34(self, sample_invoice_data: InvoiceData) -> None:
        """BT-34: Seller electronic address with schemeID='EM' (mandatory XRechnung 3.0)."""
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        uri = root.find(".//ram:SellerTradeParty/ram:URIUniversalCommunication/ram:URIID", CII_NS)
        assert uri is not None
        assert uri.text == "rechnungen@techcorp.de"
        assert uri.get("schemeID") == "EM"

    def test_buyer_electronic_address_bt49(self, sample_invoice_data: InvoiceData) -> None:
        """BT-49: Buyer electronic address with schemeID='EM' (mandatory XRechnung 3.0)."""
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        uri = root.find(".//ram:BuyerTradeParty/ram:URIUniversalCommunication/ram:URIID", CII_NS)
        assert uri is not None
        assert uri.text == "einkauf@clientcorp.de"
        assert uri.get("schemeID") == "EM"

    def test_seller_contact_br_de_5(self, sample_invoice_data: InvoiceData) -> None:
        """BR-DE-5: Seller contact person name must be present."""
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        person = root.find(".//ram:SellerTradeParty/ram:DefinedTradeContact/ram:PersonName", CII_NS)
        assert person is not None
        assert person.text == "Max Mustermann"

    def test_seller_contact_email_br_de_7(self, sample_invoice_data: InvoiceData) -> None:
        """BR-DE-7: Seller contact email must be present."""
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        email = root.find(
            ".//ram:SellerTradeParty/ram:DefinedTradeContact"
            "/ram:EmailURIUniversalCommunication/ram:URIID",
            CII_NS,
        )
        assert email is not None
        assert email.text == "max@techcorp.de"

    def test_seller_contact_phone(self, sample_invoice_data: InvoiceData) -> None:
        """BT-42: Seller contact phone number."""
        xml_bytes = build_xml(sample_invoice_data)
        root = ET.fromstring(xml_bytes)
        phone = root.find(
            ".//ram:SellerTradeParty/ram:DefinedTradeContact"
            "/ram:TelephoneUniversalCommunication/ram:CompleteNumber",
            CII_NS,
        )
        assert phone is not None
        assert phone.text == "+49 30 1234567"

    def test_br_co_14_tax_total_equals_sum_of_trade_tax(self) -> None:
        """BR-CO-14: TaxTotalAmount MUST equal sum of ApplicableTradeTax.CalculatedAmount.

        Uses items with different tax rates where per-item vs per-group
        rounding could diverge (e.g. 3 items at 7% with price 33.33).
        """
        data = InvoiceData(
            invoice_id="BR-CO-14",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[
                LineItem(description="A", quantity="3", unit_price="33.33", tax_rate="7"),
                LineItem(description="B", quantity="1", unit_price="100.00", tax_rate="19"),
            ],
        )
        xml_bytes = build_xml(data)
        root = ET.fromstring(xml_bytes)

        # Sum all ApplicableTradeTax CalculatedAmount values
        ns = CII_NS
        trade_taxes = root.findall(
            ".//ram:ApplicableHeaderTradeSettlement/ram:ApplicableTradeTax", ns
        )
        calculated_sum = Decimal("0")
        for tt in trade_taxes:
            ca = tt.find("ram:CalculatedAmount", ns)
            if ca is not None and ca.text:
                calculated_sum += Decimal(ca.text)

        # Get TaxTotalAmount
        tax_total_el = root.find(
            ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:TaxTotalAmount", ns
        )
        assert tax_total_el is not None
        tax_total = Decimal(tax_total_el.text)

        # BR-CO-14: must match exactly
        assert tax_total == calculated_sum

    def test_iban_in_xml(self) -> None:
        """BT-84: IBAN must appear in PayeePartyCreditorFinancialAccount."""
        data = InvoiceData(
            invoice_id="IBAN-001",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
            seller_iban="DE89370400440532013000",
            seller_bic="COBADEFFXXX",
        )
        xml_str = build_xml(data).decode("utf-8")
        assert "DE89370400440532013000" in xml_str
        assert "COBADEFFXXX" in xml_str

    def test_no_iban_when_empty(self) -> None:
        """PayeePartyCreditorFinancialAccount should not appear without IBAN."""
        data = InvoiceData(
            invoice_id="NO-IBAN",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="1", unit_price="100")],
        )
        xml_str = build_xml(data).decode("utf-8")
        assert "IBANID" not in xml_str
        assert "PayeePartyCreditorFinancialAccount" not in xml_str or "IBAN" not in xml_str

    def test_line_item_net_amount_quantized(self) -> None:
        """Line item LineTotalAmount must be quantized to 2 decimal places."""
        data = InvoiceData(
            invoice_id="QUANT-001",
            issue_date="2026-01-01",
            seller=Party(name="S", address=Address(street="S", city="S", postal_code="00000")),
            buyer=Party(name="B", address=Address(street="B", city="B", postal_code="00000")),
            items=[LineItem(description="X", quantity="3", unit_price="33.33")],
        )
        xml_bytes = build_xml(data)
        root = ET.fromstring(xml_bytes)
        line_total = root.find(
            ".//ram:IncludedSupplyChainTradeLineItem"
            "/ram:SpecifiedLineTradeSettlement"
            "/ram:SpecifiedTradeSettlementLineMonetarySummation"
            "/ram:LineTotalAmount",
            CII_NS,
        )
        assert line_total is not None
        # 3 * 33.33 = 99.99 — must be exactly 99.99, not 99.990000...
        assert line_total.text == "99.99"

    def test_no_electronic_address_when_empty(self, sample_invoice_data: InvoiceData) -> None:
        """Electronic address elements should not appear when not set."""
        from einvoice_mcp.models import Address, Party

        data = sample_invoice_data.model_copy(
            update={
                "seller": Party(
                    name="NoEmail GmbH",
                    address=Address(street="Str. 1", city="Berlin", postal_code="10115"),
                    tax_id="DE111111111",
                ),
            }
        )
        xml_bytes = build_xml(data)
        root = ET.fromstring(xml_bytes)
        uri = root.find(".//ram:SellerTradeParty/ram:URIUniversalCommunication/ram:URIID", CII_NS)
        assert uri is None
