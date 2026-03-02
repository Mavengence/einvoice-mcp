"""XML field scanning for compliance checks (BR-DE rules, EN 16931)."""

import re
from xml.etree.ElementTree import Element

from defusedxml import ElementTree
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden

from einvoice_mcp.models import FieldCheck
from einvoice_mcp.tools.arithmetic_checks import check_arithmetic

CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}

# Common EN 16931 mandatory fields (shared by XRechnung and ZUGFeRD)
_COMMON_FIELDS = [
    ("BT-1", "Rechnungsnummer", ".//rsm:ExchangedDocument/ram:ID"),
    ("BT-2", "Rechnungsdatum", ".//rsm:ExchangedDocument/ram:IssueDateTime"),
    ("BT-3", "Rechnungsartcode", ".//rsm:ExchangedDocument/ram:TypeCode"),
    (
        "BT-5",
        "Währung",
        ".//ram:ApplicableHeaderTradeSettlement/ram:InvoiceCurrencyCode",
    ),
    ("BT-27", "Verkäufer-Name", ".//ram:SellerTradeParty/ram:Name"),
    ("BT-35", "Verkäufer-Straße", ".//ram:SellerTradeParty/ram:PostalTradeAddress/ram:LineOne"),
    (
        "BT-37",
        "Verkäufer-Stadt",
        ".//ram:SellerTradeParty/ram:PostalTradeAddress/ram:CityName",
    ),
    (
        "BT-38",
        "Verkäufer-PLZ",
        ".//ram:SellerTradeParty/ram:PostalTradeAddress/ram:PostcodeCode",
    ),
    (
        "BT-40",
        "Verkäufer-Land",
        ".//ram:SellerTradeParty/ram:PostalTradeAddress/ram:CountryID",
    ),
    ("BT-44", "Käufer-Name", ".//ram:BuyerTradeParty/ram:Name"),
    (
        "BT-50",
        "Käufer-Straße",
        ".//ram:BuyerTradeParty/ram:PostalTradeAddress/ram:LineOne",
    ),
    (
        "BT-52",
        "Käufer-Stadt",
        ".//ram:BuyerTradeParty/ram:PostalTradeAddress/ram:CityName",
    ),
    (
        "BT-53",
        "Käufer-PLZ",
        ".//ram:BuyerTradeParty/ram:PostalTradeAddress/ram:PostcodeCode",
    ),
    (
        "BT-55",
        "Käufer-Land",
        ".//ram:BuyerTradeParty/ram:PostalTradeAddress/ram:CountryID",
    ),
]

# XRechnung-specific CIUS fields (NOT required for ZUGFeRD)
_XRECHNUNG_ONLY_FIELDS = [
    (
        "BT-10",
        "Käuferreferenz / Leitweg-ID",
        ".//ram:ApplicableHeaderTradeAgreement/ram:BuyerReference",
    ),
    (
        "BT-34",
        "Elektronische Adresse des Verkäufers",
        ".//ram:SellerTradeParty/ram:URIUniversalCommunication/ram:URIID",
    ),
    (
        "BT-49",
        "Elektronische Adresse des Käufers",
        ".//ram:BuyerTradeParty/ram:URIUniversalCommunication/ram:URIID",
    ),
    (
        "BT-41",
        "Ansprechpartner des Verkäufers",
        ".//ram:SellerTradeParty/ram:DefinedTradeContact/ram:PersonName",
    ),
    (
        "BT-42",
        "Telefon des Ansprechpartners",
        ".//ram:SellerTradeParty/ram:DefinedTradeContact"
        "/ram:TelephoneUniversalCommunication/ram:CompleteNumber",
    ),
    (
        "BT-43",
        "E-Mail des Ansprechpartners",
        ".//ram:SellerTradeParty/ram:DefinedTradeContact"
        "/ram:EmailURIUniversalCommunication/ram:URIID",
    ),
]

# Optional fields (informational, not flagged as missing)
_OPTIONAL_FIELDS = {"BT-6"}

# Valid EAS codes for electronic addresses (BR-DE-16/21/22)
# Full Peppol EAS code list v9.5 (2025-12-23)
_VALID_EAS = frozenset({
    "EM",
    # ISO 6523 ICD codes
    "0002", "0007", "0009", "0037", "0060", "0088", "0096", "0097",
    "0106", "0130", "0135", "0142", "0147", "0151", "0154", "0158",
    "0170", "0177", "0183", "0184", "0188", "0190", "0191", "0192",
    "0193", "0194", "0195", "0196", "0198", "0199", "0200", "0201",
    "0202", "0203", "0204", "0205", "0208", "0209", "0210", "0211",
    "0212", "0213", "0215", "0216", "0217", "0218", "0221", "0225",
    "0230", "0235", "0240",
    # National VAT / registration schemes
    "9910", "9913", "9914", "9915", "9918", "9919", "9920", "9922",
    "9923", "9924", "9925", "9926", "9927", "9928", "9929", "9930",
    "9931", "9932", "9933", "9934", "9935", "9936", "9937", "9938",
    "9939", "9940", "9941", "9942", "9943", "9944", "9945", "9946",
    "9947", "9948", "9949", "9950", "9951", "9952", "9953", "9957",
    "9959",
})

# Valid payment means codes (BR-DE-19, UNTDID 4461 subset)
_VALID_PM_CODES = frozenset({
    "1", "10", "20", "30", "31", "42", "48", "49", "57", "58", "59", "97", "ZZZ",
})


def check_fields(xml_content: str, *, xrechnung: bool = True) -> list[FieldCheck]:
    """Scan CII XML for mandatory fields and compliance rules.

    Returns a list of FieldCheck results for all checked fields.
    """
    checks: list[FieldCheck] = []
    try:
        root = ElementTree.fromstring(xml_content.encode("utf-8"))
    except (ElementTree.ParseError, EntitiesForbidden, DTDForbidden, ExternalReferenceForbidden):
        return checks

    # --- Basic mandatory fields ---
    fields = _COMMON_FIELDS + (_XRECHNUNG_ONLY_FIELDS if xrechnung else [])
    for bt, name, xpath in fields:
        required = bt not in _OPTIONAL_FIELDS
        el = root.find(xpath, CII_NS)
        has_text = el is not None and bool(el.text and el.text.strip())
        has_children = el is not None and len(list(el)) > 0
        present = has_text or has_children
        value = el.text.strip() if has_text and el is not None and el.text else ""
        checks.append(FieldCheck(
            field=bt, name=name, present=present,
            value=value, required=required,
        ))

    # --- BT-31/BT-32 alternative (§14 Abs. 4 Nr. 2 UStG) ---
    tax_regs = root.findall(
        ".//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID", CII_NS
    )
    has_va = any(el.get("schemeID") == "VA" and el.text for el in tax_regs)
    has_fc = any(el.get("schemeID") == "FC" and el.text for el in tax_regs)
    va_value = next((el.text for el in tax_regs if el.get("schemeID") == "VA" and el.text), "")
    fc_value = next((el.text for el in tax_regs if el.get("schemeID") == "FC" and el.text), "")
    checks.append(FieldCheck(
        field="BT-31/32", name="USt-IdNr. oder Steuernummer des Verkäufers",
        present=has_va or has_fc, value=va_value or fc_value, required=True,
    ))

    # --- Payment means code ---
    pm_code_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode", CII_NS,
    )
    pm_code = pm_code_el.text.strip() if pm_code_el is not None and pm_code_el.text else ""

    # BR-DE-23: SEPA requires IBAN
    _check_sepa_iban(checks, root, pm_code)

    # BT-71/73/74: delivery date or service period
    _check_delivery_or_period(checks, root)

    # BT-25: credit note / correction requires preceding invoice
    _check_preceding_invoice(checks, root)

    # Tax category checks (AE, K, G, E)
    _check_tax_categories(checks, root, has_va)

    # Payment-specific checks
    _check_sepa_direct_debit(checks, root, pm_code)
    _check_payment_terms(checks, root, xrechnung)
    _check_credit_card(checks, root, pm_code)

    # Seller tax representative
    _check_tax_representative(checks, root)

    # BR-DE-3/BR-DE-4: Non-DE seller requires tax representative (XRechnung only)
    if xrechnung:
        _check_non_de_seller_tax_rep(checks, root)

    # BR-DE-5/6/7: Seller contact (XRechnung only)
    if xrechnung:
        _check_seller_contact(checks, root)

    # BR-DE-26: Not both BT-31 and BT-32 (XRechnung)
    if xrechnung:
        _check_no_dual_tax_id(checks, root, has_va, has_fc)

    # BR-DE-18/19: Payment means presence and code validity
    _check_payment_means_rules(checks, root)

    # BR-DE-20: Max one payment instruction type
    _check_single_payment_instruction(checks, root)

    # BR-DE-16/21/22: EAS scheme ID validation
    _check_eas_scheme_ids(checks, root)

    # BR-DE-25: Grand total must be non-negative
    _check_grand_total_nonneg(checks, root)

    # BR-DE-8/9/10/11/13: Date format code "102" (YYYYMMDD)
    _check_date_formats(checks, root)

    # BR-CO: Mathematical integrity checks (advisory)
    check_arithmetic(checks, root)

    # Format validations (advisory)
    _check_leitweg_format(checks, root, xrechnung)
    _check_vat_format(checks, tax_regs)
    _check_kleinbetragsrechnung(checks, root)

    return checks


def _check_sepa_iban(
    checks: list[FieldCheck], root: Element, pm_code: str
) -> None:
    """BR-DE-23: IBAN required for SEPA transfer (code 58)."""
    if pm_code != "58":
        return
    iban_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementPaymentMeans"
        "/ram:PayeePartyCreditorFinancialAccount/ram:IBANID", CII_NS,
    )
    iban_present = (
        iban_el is not None and bool(iban_el.text and iban_el.text.strip())
    )
    iban_value = (
        iban_el.text.strip()
        if iban_present and iban_el is not None and iban_el.text
        else ""
    )
    checks.append(FieldCheck(
        field="BT-84", name="IBAN (SEPA-Überweisung)",
        present=iban_present, value=iban_value, required=True,
    ))


def _check_delivery_or_period(checks: list[FieldCheck], root: Element) -> None:
    """BT-71/73/74: delivery date or service period (§14 Abs. 4 Nr. 6 UStG)."""
    delivery_el = root.find(
        ".//ram:ApplicableHeaderTradeDelivery"
        "/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime", CII_NS,
    )
    period_start_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement/ram:BillingSpecifiedPeriod/ram:StartDateTime",
        CII_NS,
    )
    period_end_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement/ram:BillingSpecifiedPeriod/ram:EndDateTime",
        CII_NS,
    )
    def _has_content(el: Element | None) -> bool:
        if el is None:
            return False
        return bool(el.text and el.text.strip()) or len(list(el)) > 0

    has_delivery = _has_content(delivery_el)
    has_period = _has_content(period_start_el) or _has_content(period_end_el)
    checks.append(FieldCheck(
        field="BT-71/73/74",
        name="Lieferdatum oder Leistungszeitraum",
        present=has_delivery or has_period,
        value="",
        required=True,
    ))


def _check_preceding_invoice(checks: list[FieldCheck], root: Element) -> None:
    """BT-25: credit notes (381) and corrections (384) require preceding invoice."""
    type_code_el = root.find(
        ".//rsm:ExchangedDocument/ram:TypeCode", CII_NS,
    )
    type_code_val = (
        type_code_el.text.strip()
        if type_code_el is not None and type_code_el.text
        else ""
    )
    if type_code_val not in ("381", "384"):
        return
    inv_ref_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement/ram:InvoiceReferencedDocument/ram:IssuerAssignedID",
        CII_NS,
    )
    bt25_present = (
        inv_ref_el is not None
        and bool(inv_ref_el.text and inv_ref_el.text.strip())
    )
    bt25_value = (
        inv_ref_el.text.strip()
        if bt25_present and inv_ref_el is not None and inv_ref_el.text
        else ""
    )
    label = (
        "Vorherige Rechnungsnummer (Gutschrift)"
        if type_code_val == "381"
        else "Vorherige Rechnungsnummer (Korrekturrechnung)"
    )
    field_key = "BT-25" if type_code_val == "381" else "384-BT-25"
    checks.append(FieldCheck(
        field=field_key, name=label, present=bt25_present, value=bt25_value, required=True,
    ))


def _check_tax_rate_zero(
    checks: list[FieldCheck], root: Element,
    category: str, field: str, name: str,
) -> None:
    """Check that all ApplicableTradeTax entries for a category have rate 0%."""
    for tax_el in root.findall(".//ram:ApplicableTradeTax", CII_NS):
        cat_el = tax_el.find("ram:CategoryCode", CII_NS)
        rate_el = tax_el.find("ram:RateApplicablePercent", CII_NS)
        if (
            cat_el is not None and cat_el.text and cat_el.text.strip() == category
            and rate_el is not None and rate_el.text
        ):
            try:
                if float(rate_el.text.strip()) != 0.0:
                    checks.append(FieldCheck(
                        field=field, name=name,
                        present=False, value=rate_el.text.strip(), required=True,
                    ))
            except ValueError:
                pass


def _check_country_mismatch(
    checks: list[FieldCheck], root: Element,
    field: str, name: str, *, required: bool,
) -> None:
    """Check that seller and buyer are in different countries."""
    seller_el = root.find(".//ram:SellerTradeParty/ram:PostalTradeAddress/ram:CountryID", CII_NS)
    buyer_el = root.find(".//ram:BuyerTradeParty/ram:PostalTradeAddress/ram:CountryID", CII_NS)
    seller_cc = seller_el.text.strip() if seller_el is not None and seller_el.text else ""
    buyer_cc = buyer_el.text.strip() if buyer_el is not None and buyer_el.text else ""
    if seller_cc and buyer_cc and seller_cc == buyer_cc:
        checks.append(FieldCheck(
            field=field, name=name,
            present=False, value=f"{seller_cc}={buyer_cc}", required=required,
        ))


def _check_tax_categories(
    checks: list[FieldCheck], root: Element, has_va: bool,
) -> None:
    """Check tax-category-specific rules (AE, K, G, E)."""
    tax_cats = root.findall(".//ram:ApplicableTradeTax/ram:CategoryCode", CII_NS)

    # Reverse charge (AE / §13b UStG)
    has_ae = any(el.text and el.text.strip() == "AE" for el in tax_cats)
    if has_ae:
        if not has_va:
            checks.append(FieldCheck(
                field="RC-BT-31", name="USt-IdNr. des Verkäufers (Reverse Charge)",
                present=False, value="", required=True,
            ))
        buyer_tax_regs = root.findall(
            ".//ram:BuyerTradeParty/ram:SpecifiedTaxRegistration/ram:ID", CII_NS,
        )
        if not any(el.get("schemeID") == "VA" and el.text for el in buyer_tax_regs):
            checks.append(FieldCheck(
                field="RC-BT-48", name="USt-IdNr. des Käufers (Reverse Charge)",
                present=False, value="", required=True,
            ))
        _check_tax_rate_zero(
            checks, root, "AE", "RC-TAX-RATE",
            "Steuersatz bei Reverse Charge",
        )
        _check_country_mismatch(
            checks, root, "RC-COUNTRY",
            "Länderprüfung Reverse Charge", required=False,
        )

    # Intra-community supply (K / §4 Nr. 1b UStG)
    has_k = any(el.text and el.text.strip() == "K" for el in tax_cats)
    if has_k:
        buyer_tax_regs_k = root.findall(
            ".//ram:BuyerTradeParty"
            "/ram:SpecifiedTaxRegistration/ram:ID", CII_NS,
        )
        has_buyer_vat = any(
            el.get("schemeID") == "VA" and el.text
            for el in buyer_tax_regs_k
        )
        if not has_buyer_vat:
            checks.append(FieldCheck(
                field="IC-BT-48",
                name="USt-IdNr. Käufer (innergemeinschaftlich)",
                present=False, value="", required=True,
            ))
        _check_tax_rate_zero(
            checks, root, "K", "IC-TAX-RATE",
            "Steuersatz bei ig. Lieferung",
        )
        _check_country_mismatch(
            checks, root, "IC-COUNTRY",
            "Länderprüfung ig. Lieferung", required=True,
        )

    # Export outside EU (G)
    has_g = any(el.text and el.text.strip() == "G" for el in tax_cats)
    if has_g:
        _check_tax_rate_zero(checks, root, "G", "EX-TAX-RATE", "Steuersatz bei Drittlandslieferung")

    # Exempt (E) — §19 UStG hint + BR-E-10
    has_e = any(el.text and el.text.strip() == "E" for el in tax_cats)
    if has_e:
        notes = root.findall(".//rsm:ExchangedDocument/ram:IncludedNote/ram:Content", CII_NS)
        exemption_keywords = ["§19", "§ 19", "§4", "§ 4", "steuerbefreit", "exempt"]
        has_exemption_note = any(
            note_el.text and any(kw.lower() in note_el.text.lower() for kw in exemption_keywords)
            for note_el in notes
        )
        if not has_exemption_note:
            checks.append(FieldCheck(
                field="KU-NOTE", name="Hinweis Steuerbefreiung (§19 UStG)",
                present=False, value="", required=False,
            ))
        exemption_el = root.find(".//ram:ApplicableTradeTax/ram:ExemptionReason", CII_NS)
        if not (exemption_el is not None and bool(exemption_el.text and exemption_el.text.strip())):
            checks.append(FieldCheck(
                field="E-BT-120", name="Befreiungsgrund (TaxCategory E)",
                present=False, value="", required=True,
            ))


def _check_sepa_direct_debit(
    checks: list[FieldCheck], root: Element, pm_code: str,
) -> None:
    """BR-DE-24: SEPA direct debit (code 59) requires mandate + buyer IBAN."""
    if pm_code != "59":
        return
    mandate_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradePaymentTerms/ram:DirectDebitMandateID", CII_NS,
    )
    if not (mandate_el is not None and bool(mandate_el.text and mandate_el.text.strip())):
        checks.append(FieldCheck(
            field="DD-BT-89", name="Mandatsreferenz (SEPA-Lastschrift)",
            present=False, value="", required=True,
        ))
    buyer_iban_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementPaymentMeans"
        "/ram:PayerPartyDebtorFinancialAccount/ram:IBANID", CII_NS,
    )
    if not (buyer_iban_el is not None and bool(buyer_iban_el.text and buyer_iban_el.text.strip())):
        checks.append(FieldCheck(
            field="DD-BT-91", name="IBAN des Käufers (SEPA-Lastschrift)",
            present=False, value="", required=True,
        ))
    # BT-90: Creditor reference ID (Gläubigeridentifikationsnummer)
    cred_ref_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:CreditorReferenceID", CII_NS,
    )
    if not (cred_ref_el is not None and bool(cred_ref_el.text and cred_ref_el.text.strip())):
        checks.append(FieldCheck(
            field="DD-BT-90",
            name="Gläubiger-ID (SEPA-Lastschrift)",
            present=False, value="", required=True,
        ))


def _check_payment_terms(
    checks: list[FieldCheck], root: Element, xrechnung: bool,
) -> None:
    """BR-DE-15: Payment terms (BT-20) required for XRechnung."""
    if not xrechnung:
        return
    pt_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradePaymentTerms/ram:Description", CII_NS,
    )
    pt_present = pt_el is not None and bool(pt_el.text and pt_el.text.strip())
    checks.append(FieldCheck(
        field="BT-20", name="Zahlungsbedingungen",
        present=pt_present,
        value=pt_el.text.strip() if pt_present and pt_el is not None and pt_el.text else "",
        required=True,
    ))


def _check_credit_card(
    checks: list[FieldCheck], root: Element, pm_code: str,
) -> None:
    """Credit card (code 48): BT-87 card PAN required."""
    if pm_code != "48":
        return
    card_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementPaymentMeans"
        "/ram:ApplicableTradeSettlementFinancialCard/ram:ID", CII_NS,
    )
    if not (card_el is not None and bool(card_el.text and card_el.text.strip())):
        checks.append(FieldCheck(
            field="CC-BT-87", name="Kartennummer (Kreditkarte)",
            present=False, value="", required=True,
        ))


def _check_tax_representative(checks: list[FieldCheck], root: Element) -> None:
    """BG-11: If tax representative present, BT-63 VAT ID required."""
    rep_name_el = root.find(".//ram:SellerTaxRepresentativeTradeParty/ram:Name", CII_NS)
    if not (rep_name_el is not None and rep_name_el.text):
        return
    rep_tax_el = root.find(
        ".//ram:SellerTaxRepresentativeTradeParty/ram:SpecifiedTaxRegistration/ram:ID", CII_NS,
    )
    if not (rep_tax_el is not None and bool(rep_tax_el.text and rep_tax_el.text.strip())):
        checks.append(FieldCheck(
            field="REP-BT-63", name="USt-IdNr. des Steuervertreters",
            present=False, value="", required=True,
        ))


def _check_non_de_seller_tax_rep(checks: list[FieldCheck], root: Element) -> None:
    """BR-DE-3/BR-DE-4: Non-DE seller must provide tax representative (BG-11)."""
    seller_country_el = root.find(
        ".//ram:SellerTradeParty/ram:PostalTradeAddress/ram:CountryID", CII_NS,
    )
    if seller_country_el is None or not seller_country_el.text:
        return
    seller_country = seller_country_el.text.strip()
    if seller_country == "DE":
        return
    # Seller is outside DE — check for tax representative
    rep_name_el = root.find(".//ram:SellerTaxRepresentativeTradeParty/ram:Name", CII_NS)
    has_rep = rep_name_el is not None and bool(rep_name_el.text and rep_name_el.text.strip())
    if not has_rep:
        checks.append(FieldCheck(
            field="BR-DE-3", name="Steuervertreter bei nicht-DE Verkäufer",
            present=False, value=seller_country, required=True,
        ))


def _check_seller_contact(checks: list[FieldCheck], root: Element) -> None:
    """BR-DE-5/6/7: Seller contact name, phone, email (XRechnung)."""
    contact_base = ".//ram:SellerTradeParty/ram:DefinedTradeContact"
    name_el = root.find(f"{contact_base}/ram:PersonName", CII_NS)
    phone_el = root.find(
        f"{contact_base}/ram:TelephoneUniversalCommunication"
        "/ram:CompleteNumber", CII_NS,
    )
    email_el = root.find(
        f"{contact_base}/ram:EmailURIUniversalCommunication"
        "/ram:URIID", CII_NS,
    )
    if not (name_el is not None and name_el.text and name_el.text.strip()):
        checks.append(FieldCheck(
            field="BR-DE-5", name="Ansprechpartner (BT-41)",
            present=False, value="", required=True,
        ))
    if not (phone_el is not None and phone_el.text and phone_el.text.strip()):
        checks.append(FieldCheck(
            field="BR-DE-6", name="Telefon Ansprechpartner (BT-42)",
            present=False, value="", required=True,
        ))
    if not (email_el is not None and email_el.text and email_el.text.strip()):
        checks.append(FieldCheck(
            field="BR-DE-7", name="E-Mail Ansprechpartner (BT-43)",
            present=False, value="", required=True,
        ))


def _check_no_dual_tax_id(
    checks: list[FieldCheck], root: Element,
    has_va: bool, has_fc: bool,
) -> None:
    """BR-DE-26: Seller must NOT have both USt-IdNr and Steuernummer."""
    if has_va and has_fc:
        checks.append(FieldCheck(
            field="BR-DE-26",
            name="Nur USt-IdNr. ODER Steuernummer",
            present=False,
            value="Beide vorhanden (VA + FC)",
            required=True,
        ))


def _check_payment_means_rules(checks: list[FieldCheck], root: Element) -> None:
    """BR-DE-18: Payment means present. BR-DE-19: Valid UNTDID 4461 code."""
    pm_elements = root.findall(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode", CII_NS,
    )
    if not pm_elements:
        checks.append(FieldCheck(
            field="BR-DE-18", name="Zahlungsart (PaymentMeansCode)",
            present=False, value="", required=True,
        ))
    for pm_el in pm_elements:
        if pm_el.text:
            code = pm_el.text.strip()
            if code and code not in _VALID_PM_CODES:
                checks.append(FieldCheck(
                    field="BR-DE-19", name="Zahlungsart-Code ungültig",
                    present=False, value=code, required=True,
                ))


def _check_single_payment_instruction(checks: list[FieldCheck], root: Element) -> None:
    """BR-DE-20: Max one payment instruction type per invoice.

    Cannot mix credit transfer (58) and direct debit (59) in the same invoice.
    """
    pm_elements = root.findall(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode", CII_NS,
    )
    codes = {el.text.strip() for el in pm_elements if el.text and el.text.strip()}
    # Credit transfer codes: 30, 31, 42, 58 (SEPA)
    ct_codes = codes & {"30", "31", "42", "58"}
    # Direct debit codes: 49, 59 (SEPA)
    dd_codes = codes & {"49", "59"}
    if ct_codes and dd_codes:
        checks.append(FieldCheck(
            field="BR-DE-20",
            name="Widersprüchliche Zahlungsanweisungen",
            present=False,
            value=f"Überweisung ({', '.join(sorted(ct_codes))}) + "
                  f"Lastschrift ({', '.join(sorted(dd_codes))})",
            required=True,
        ))


def _check_eas_scheme_ids(checks: list[FieldCheck], root: Element) -> None:
    """BR-DE-16/21/22: Electronic address schemeID must be valid EAS."""
    seller_ea_el = root.find(
        ".//ram:SellerTradeParty/ram:URIUniversalCommunication/ram:URIID", CII_NS,
    )
    if seller_ea_el is not None:
        scheme = seller_ea_el.get("schemeID", "")
        if scheme and scheme not in _VALID_EAS:
            checks.append(FieldCheck(
                field="BR-DE-16", name="Verkäufer-EAS-Code ungültig",
                present=False, value=scheme, required=True,
            ))
    buyer_ea_el = root.find(
        ".//ram:BuyerTradeParty/ram:URIUniversalCommunication/ram:URIID", CII_NS,
    )
    if buyer_ea_el is not None:
        scheme = buyer_ea_el.get("schemeID", "")
        if scheme and scheme not in _VALID_EAS:
            checks.append(FieldCheck(
                field="BR-DE-22", name="Käufer-EAS-Code ungültig",
                present=False, value=scheme, required=True,
            ))


def _check_leitweg_format(
    checks: list[FieldCheck], root: Element, xrechnung: bool,
) -> None:
    """Leitweg-ID format validation (advisory, XRechnung only)."""
    if not xrechnung:
        return
    buyer_ref_el = root.find(
        ".//ram:ApplicableHeaderTradeAgreement/ram:BuyerReference", CII_NS,
    )
    if buyer_ref_el is not None and buyer_ref_el.text:
        leitweg = buyer_ref_el.text.strip()
        if leitweg and not re.match(
            r"^[0-9]{2,12}-[0-9A-Za-z]{1,30}-[0-9A-Za-z]{2,5}$", leitweg
        ):
            checks.append(FieldCheck(
                field="LW-FMT", name="Leitweg-ID Format",
                present=False, value=leitweg, required=False,
            ))


def _check_vat_format(
    checks: list[FieldCheck], tax_regs: list[Element],
) -> None:
    """German VAT ID format validation (advisory)."""
    for tax_el in tax_regs:
        if tax_el.get("schemeID") == "VA" and tax_el.text:
            vat_id = tax_el.text.strip()
            if vat_id.startswith("DE") and not re.match(r"^DE\d{9}$", vat_id):
                checks.append(FieldCheck(
                    field="VAT-FMT", name="USt-IdNr. Format",
                    present=False, value=vat_id, required=False,
                ))
                break


def _check_kleinbetragsrechnung(checks: list[FieldCheck], root: Element) -> None:
    """§33 UStDV: Advisory for invoices with gross total ≤250€."""
    grand_total_el = root.find(
        ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation/ram:GrandTotalAmount", CII_NS,
    )
    if grand_total_el is not None and grand_total_el.text:
        try:
            grand_total = float(grand_total_el.text.strip())
            if 0 < grand_total <= 250.0:
                checks.append(FieldCheck(
                    field="KB-INFO", name="Kleinbetragsrechnung (§33 UStDV)",
                    present=True, value=f"{grand_total:.2f}", required=False,
                ))
        except ValueError:
            pass


def _check_grand_total_nonneg(checks: list[FieldCheck], root: Element) -> None:
    """BR-DE-25: Grand total (BT-112) must be >= 0."""
    gt_el = root.find(
        ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation"
        "/ram:GrandTotalAmount", CII_NS,
    )
    if gt_el is not None and gt_el.text:
        try:
            total = float(gt_el.text.strip())
            if total < 0:
                checks.append(FieldCheck(
                    field="BR-DE-25",
                    name="Bruttobetrag negativ",
                    present=False,
                    value=f"{total:.2f}",
                    required=True,
                ))
        except ValueError:
            pass


def _check_date_formats(checks: list[FieldCheck], root: Element) -> None:
    """BR-DE-8/9/10/11/13: CII dates must use format code 102 (YYYYMMDD)."""
    # Map of (BR-DE rule, label, XPath to the DateTimeString element)
    date_checks = [
        (
            "BR-DE-9", "Rechnungsdatum Datumsformat",
            ".//rsm:ExchangedDocument/ram:IssueDateTime"
            "/udt:DateTimeString",
        ),
        (
            "BR-DE-8", "Lieferdatum Datumsformat",
            ".//ram:ApplicableHeaderTradeDelivery"
            "/ram:ActualDeliverySupplyChainEvent"
            "/ram:OccurrenceDateTime/udt:DateTimeString",
        ),
        (
            "BR-DE-10", "Leistungszeitraum Beginn Datumsformat",
            ".//ram:ApplicableHeaderTradeSettlement"
            "/ram:BillingSpecifiedPeriod"
            "/ram:StartDateTime/udt:DateTimeString",
        ),
        (
            "BR-DE-11", "Leistungszeitraum Ende Datumsformat",
            ".//ram:ApplicableHeaderTradeSettlement"
            "/ram:BillingSpecifiedPeriod"
            "/ram:EndDateTime/udt:DateTimeString",
        ),
        (
            "BR-DE-13", "Fälligkeitsdatum Datumsformat",
            ".//ram:ApplicableHeaderTradeSettlement"
            "/ram:SpecifiedTradePaymentTerms"
            "/ram:DueDateDateTime/udt:DateTimeString",
        ),
    ]
    for rule, name, xpath in date_checks:
        el = root.find(xpath, CII_NS)
        if el is None:
            continue
        fmt = el.get("format", "")
        if fmt and fmt != "102":
            checks.append(FieldCheck(
                field=rule,
                name=name,
                present=False,
                value=f"format={fmt} (erwartet: 102)",
                required=True,
            ))


