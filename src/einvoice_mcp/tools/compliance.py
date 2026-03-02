"""Compliance checking tool for XRechnung/ZUGFeRD."""

import logging
from typing import Any

from defusedxml import ElementTree
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden

from einvoice_mcp.config import MAX_XML_SIZE
from einvoice_mcp.errors import EInvoiceError
from einvoice_mcp.models import ComplianceResult, FieldCheck
from einvoice_mcp.services.kosit import KoSITClient

logger = logging.getLogger(__name__)

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

# Valid target profiles for the compliance checker
_VALID_TARGET_PROFILES = frozenset({"XRECHNUNG", "ZUGFERD"})

SUGGESTIONS_MAP = {
    "BT-1": "BT-1 (Rechnungsnummer) fehlt — jede Rechnung muss eindeutig nummeriert sein.",
    "BT-2": "BT-2 (Rechnungsdatum) fehlt — Pflichtangabe nach §14 Abs. 4 Nr. 3 UStG.",
    "BT-10": (
        "BT-10 (Leitweg-ID / Käuferreferenz) fehlt — "
        "für XRechnung an öffentliche Auftraggeber zwingend erforderlich."
    ),
    "BT-31/32": (
        "Weder USt-IdNr. (BT-31) noch Steuernummer (BT-32) des Verkäufers vorhanden — "
        "mindestens eine Angabe ist gemäß §14 Abs. 4 Nr. 2 UStG erforderlich."
    ),
    "BT-34": (
        "BT-34 (Elektronische Adresse des Verkäufers) fehlt — "
        "seit XRechnung 3.0 Pflichtfeld (z.B. E-Mail-Adresse)."
    ),
    "BT-49": (
        "BT-49 (Elektronische Adresse des Käufers) fehlt — "
        "seit XRechnung 3.0 Pflichtfeld (z.B. E-Mail-Adresse)."
    ),
    "BT-41": (
        "BT-41 (Ansprechpartner des Verkäufers) fehlt — "
        "gemäß BR-DE-5 muss ein Kontaktname angegeben werden."
    ),
    "BT-42": (
        "BT-42 (Telefon des Ansprechpartners) fehlt — "
        "gemäß BR-DE-6 ist die Telefonnummer des Ansprechpartners Pflicht."
    ),
    "BT-43": (
        "BT-43 (E-Mail des Ansprechpartners) fehlt — "
        "gemäß BR-DE-7 ist die E-Mail-Adresse des Ansprechpartners Pflicht."
    ),
    "BT-84": (
        "BT-84 (IBAN) fehlt — bei Zahlungsart SEPA-Überweisung (Code 58) "
        "ist die IBAN gemäß BR-DE-23 Pflicht."
    ),
    "BT-71/73/74": (
        "Weder Lieferdatum (BT-71) noch Leistungszeitraum (BT-73/BT-74) angegeben — "
        "gemäß §14 Abs. 4 Nr. 6 UStG ist mindestens eine Angabe erforderlich."
    ),
    "BT-25": (
        "BT-25 (Vorherige Rechnungsnummer) fehlt — "
        "bei Gutschriften (TypeCode 381) muss die Originalrechnung "
        "referenziert werden."
    ),
    "RC-BT-31": (
        "Bei Steuerkategorie AE (Reverse Charge / §13b UStG) "
        "muss die USt-IdNr. des Verkäufers (BT-31) angegeben sein."
    ),
    "RC-BT-48": (
        "Bei Steuerkategorie AE (Reverse Charge / §13b UStG) "
        "muss die USt-IdNr. des Käufers (BT-48) angegeben sein."
    ),
    "RC-TAX-RATE": (
        "Bei Reverse Charge (§13b UStG / Kategorie AE) "
        "muss der Steuersatz 0% betragen."
    ),
    "KU-NOTE": (
        "Steuerkategorie E (steuerbefreit) erkannt, aber kein Hinweis auf §19 UStG "
        "(Kleinunternehmerregelung) oder einen anderen Befreiungsgrund in den "
        "Rechnungsbemerkungen gefunden. Bitte fügen Sie einen Hinweis wie "
        "'Gemäß §19 UStG wird keine Umsatzsteuer berechnet.' hinzu."
    ),
}


async def check_compliance(
    xml_content: str,
    kosit: KoSITClient,
    target_profile: str = "XRECHNUNG",
) -> dict[str, Any]:
    """Check e-invoice compliance against XRechnung or ZUGFeRD requirements.

    Performs both KoSIT validation and mandatory field checks.

    Args:
        xml_content: The CII XML as a string.
        kosit: KoSIT client instance.
        target_profile: Target profile ("XRECHNUNG" or "ZUGFERD").

    Returns:
        Compliance result with field checks and German suggestions.
    """
    profile_upper = target_profile.upper().strip()
    if profile_upper not in _VALID_TARGET_PROFILES:
        # Never reflect raw user input — use a generic message
        return ComplianceResult(
            valid=False,
            suggestions=["Fehler: Ungültiges Zielprofil. Erlaubt: XRECHNUNG, ZUGFERD."],
        ).model_dump()

    if len(xml_content) > MAX_XML_SIZE:
        return ComplianceResult(
            valid=False,
            suggestions=["Fehler: XML-Inhalt überschreitet das Größenlimit (10 MB)."],
        ).model_dump()

    is_xrechnung = profile_upper == "XRECHNUNG"
    field_checks = _check_fields(xml_content, xrechnung=is_xrechnung)
    missing_fields = [fc.field for fc in field_checks if fc.required and not fc.present]
    suggestions = [SUGGESTIONS_MAP[f] for f in missing_fields if f in SUGGESTIONS_MAP]

    # Add non-required but missing advisory checks (warnings, not errors)
    advisory_fields = [
        fc.field for fc in field_checks if not fc.required and not fc.present
    ]
    for af in advisory_fields:
        if af in SUGGESTIONS_MAP:
            suggestions.append(SUGGESTIONS_MAP[af])

    # KoSIT validation
    kosit_valid = None
    try:
        xml_bytes = xml_content.encode("utf-8")
        result = await kosit.validate(xml_bytes)
        kosit_valid = result.valid

        for err in result.errors:
            if err.message and err.message not in suggestions:
                suggestions.append(err.message)
    except EInvoiceError as exc:
        suggestions.append(exc.message_de)

    is_valid = kosit_valid is True and len(missing_fields) == 0

    if is_valid:
        profile_name = "XRechnung 3.0" if target_profile == "XRECHNUNG" else "ZUGFeRD EN16931"
        suggestions.insert(0, f"Validierung erfolgreich: {profile_name} konform.")

    compliance = ComplianceResult(
        valid=is_valid,
        kosit_valid=kosit_valid,
        field_checks=field_checks,
        missing_fields=missing_fields,
        suggestions=suggestions,
    )
    return compliance.model_dump()


def _check_fields(xml_content: str, *, xrechnung: bool = True) -> list[FieldCheck]:
    checks: list[FieldCheck] = []
    try:
        root = ElementTree.fromstring(xml_content.encode("utf-8"))
    except (ElementTree.ParseError, EntitiesForbidden, DTDForbidden, ExternalReferenceForbidden):
        return checks

    fields = _COMMON_FIELDS + (_XRECHNUNG_ONLY_FIELDS if xrechnung else [])
    for bt, name, xpath in fields:
        required = bt not in _OPTIONAL_FIELDS
        el = root.find(xpath, CII_NS)
        # Element is present if it has text or child elements (e.g. IssueDateTime)
        has_text = el is not None and bool(el.text and el.text.strip())
        has_children = el is not None and len(list(el)) > 0
        present = has_text or has_children
        value = el.text.strip() if has_text and el is not None and el.text else ""

        checks.append(
            FieldCheck(
                field=bt,
                name=name,
                present=present,
                value=value,
                required=required,
            )
        )

    # BT-31/BT-32 alternative check (§14 Abs. 4 Nr. 2 UStG):
    # At least one of USt-IdNr. (BT-31, schemeID=VA) or Steuernummer (BT-32, schemeID=FC)
    # must be present for the seller.
    tax_regs = root.findall(
        ".//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID", CII_NS
    )
    has_va = any(el.get("schemeID") == "VA" and el.text for el in tax_regs)
    has_fc = any(el.get("schemeID") == "FC" and el.text for el in tax_regs)
    bt31_or_32_present = has_va or has_fc
    va_value = next((el.text for el in tax_regs if el.get("schemeID") == "VA" and el.text), "")
    fc_value = next((el.text for el in tax_regs if el.get("schemeID") == "FC" and el.text), "")
    checks.append(
        FieldCheck(
            field="BT-31/32",
            name="USt-IdNr. oder Steuernummer des Verkäufers",
            present=bt31_or_32_present,
            value=va_value or fc_value,
            required=True,
        )
    )

    # BT-84 IBAN check (BR-DE-23): when PaymentMeansCode=58 (SEPA), IBAN is mandatory.
    pm_code_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:SpecifiedTradeSettlementPaymentMeans/ram:TypeCode",
        CII_NS,
    )
    pm_code = pm_code_el.text.strip() if pm_code_el is not None and pm_code_el.text else ""
    if pm_code == "58":
        iban_el = root.find(
            ".//ram:ApplicableHeaderTradeSettlement"
            "/ram:SpecifiedTradeSettlementPaymentMeans"
            "/ram:PayeePartyCreditorFinancialAccount/ram:IBANID",
            CII_NS,
        )
        iban_present = iban_el is not None and bool(iban_el.text and iban_el.text.strip())
        iban_value = ""
        if iban_present and iban_el is not None and iban_el.text:
            iban_value = iban_el.text.strip()
        checks.append(
            FieldCheck(
                field="BT-84",
                name="IBAN (SEPA-Überweisung)",
                present=iban_present,
                value=iban_value,
                required=True,
            )
        )

    # BT-71/73/74 check (§14 Abs. 4 Nr. 6 UStG):
    # Either delivery date (BT-71) or service period (BT-73/BT-74) must be present.
    delivery_el = root.find(
        ".//ram:ApplicableHeaderTradeDelivery"
        "/ram:ActualDeliverySupplyChainEvent/ram:OccurrenceDateTime",
        CII_NS,
    )
    period_start_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:BillingSpecifiedPeriod/ram:StartDateTime",
        CII_NS,
    )
    period_end_el = root.find(
        ".//ram:ApplicableHeaderTradeSettlement"
        "/ram:BillingSpecifiedPeriod/ram:EndDateTime",
        CII_NS,
    )
    has_delivery = delivery_el is not None and (
        bool(delivery_el.text and delivery_el.text.strip())
        or len(list(delivery_el)) > 0
    )
    has_period = (
        period_start_el is not None
        and (
            bool(period_start_el.text and period_start_el.text.strip())
            or len(list(period_start_el)) > 0
        )
    ) or (
        period_end_el is not None
        and (
            bool(period_end_el.text and period_end_el.text.strip())
            or len(list(period_end_el)) > 0
        )
    )
    bt71_or_period_present = has_delivery or has_period
    checks.append(
        FieldCheck(
            field="BT-71/73/74",
            name="Lieferdatum oder Leistungszeitraum",
            present=bt71_or_period_present,
            value="",
            required=True,
        )
    )

    # BT-25 check: for credit notes (TypeCode=381), preceding invoice is required
    type_code_el = root.find(
        ".//rsm:ExchangedDocument/ram:TypeCode", CII_NS
    )
    type_code_val = ""
    if type_code_el is not None and type_code_el.text:
        type_code_val = type_code_el.text.strip()
    if type_code_val == "381":
        inv_ref_el = root.find(
            ".//ram:ApplicableHeaderTradeSettlement"
            "/ram:InvoiceReferencedDocument/ram:IssuerAssignedID",
            CII_NS,
        )
        bt25_present = inv_ref_el is not None and bool(
            inv_ref_el.text and inv_ref_el.text.strip()
        )
        bt25_value = ""
        if bt25_present and inv_ref_el is not None and inv_ref_el.text:
            bt25_value = inv_ref_el.text.strip()
        checks.append(
            FieldCheck(
                field="BT-25",
                name="Vorherige Rechnungsnummer (Gutschrift)",
                present=bt25_present,
                value=bt25_value,
                required=True,
            )
        )

    # Reverse charge (§13b UStG) checks:
    # When TaxCategory AE is used, seller VAT ID (BT-31) and buyer VAT ID (BT-48)
    # must be present, and the tax rate must be 0%.
    tax_cats = root.findall(
        ".//ram:ApplicableTradeTax/ram:CategoryCode", CII_NS
    )
    has_ae = any(
        el.text and el.text.strip() == "AE" for el in tax_cats
    )
    if has_ae:
        # BT-31: Seller VAT ID required for RC
        if not has_va:
            checks.append(
                FieldCheck(
                    field="RC-BT-31",
                    name="USt-IdNr. des Verkäufers (Reverse Charge)",
                    present=False,
                    value="",
                    required=True,
                )
            )

        # BT-48: Buyer VAT ID required for RC
        buyer_tax_regs = root.findall(
            ".//ram:BuyerTradeParty/ram:SpecifiedTaxRegistration/ram:ID",
            CII_NS,
        )
        buyer_has_va = any(
            el.get("schemeID") == "VA" and el.text for el in buyer_tax_regs
        )
        if not buyer_has_va:
            checks.append(
                FieldCheck(
                    field="RC-BT-48",
                    name="USt-IdNr. des Käufers (Reverse Charge)",
                    present=False,
                    value="",
                    required=True,
                )
            )

        # Tax rate must be 0% for AE category
        for tax_el in root.findall(".//ram:ApplicableTradeTax", CII_NS):
            cat_el = tax_el.find("ram:CategoryCode", CII_NS)
            rate_el = tax_el.find("ram:RateApplicablePercent", CII_NS)
            if (
                cat_el is not None
                and cat_el.text
                and cat_el.text.strip() == "AE"
                and rate_el is not None
                and rate_el.text
            ):
                try:
                    rate_val = float(rate_el.text.strip())
                    if rate_val != 0.0:
                        checks.append(
                            FieldCheck(
                                field="RC-TAX-RATE",
                                name="Steuersatz bei Reverse Charge",
                                present=False,
                                value=rate_el.text.strip(),
                                required=True,
                            )
                        )
                except ValueError:
                    pass

    # §19 UStG (Kleinunternehmerregelung) hint:
    # When TaxCategory E (Exempt) is used with 0% rate AND no note references
    # a VAT exemption reason (§19, §4, Art. 132/135 MwStSystRL, etc.),
    # suggest adding a clarifying note.
    has_e = any(
        el.text and el.text.strip() == "E" for el in tax_cats
    )
    if has_e:
        # Check if any note references an exemption reason
        notes = root.findall(
            ".//rsm:ExchangedDocument/ram:IncludedNote/ram:Content", CII_NS
        )
        exemption_keywords = ["§19", "§ 19", "§4", "§ 4", "steuerbefreit", "exempt"]
        has_exemption_note = any(
            note_el.text
            and any(kw.lower() in note_el.text.lower() for kw in exemption_keywords)
            for note_el in notes
        )
        if not has_exemption_note:
            checks.append(
                FieldCheck(
                    field="KU-NOTE",
                    name="Hinweis Steuerbefreiung (§19 UStG)",
                    present=False,
                    value="",
                    required=False,  # recommendation, not hard requirement
                )
            )

    return checks
