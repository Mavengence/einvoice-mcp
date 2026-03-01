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
    (
        "BT-31",
        "Verkäufer-USt-IdNr.",
        ".//ram:SellerTradeParty/ram:SpecifiedTaxRegistration/ram:ID",
    ),
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
    "BT-2": "BT-2 (Rechnungsdatum) fehlt — Pflichtangabe nach §14 UStG.",
    "BT-10": (
        "BT-10 (Leitweg-ID / Käuferreferenz) fehlt — "
        "für XRechnung an öffentliche Auftraggeber zwingend erforderlich."
    ),
    "BT-31": (
        "BT-31 (USt-IdNr. des Verkäufers) fehlt — für den Vorsteuerabzug des Käufers erforderlich."
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
    "BT-43": (
        "BT-43 (E-Mail des Ansprechpartners) fehlt — "
        "gemäß BR-DE-7 ist die E-Mail-Adresse des Ansprechpartners Pflicht."
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
    profile_upper = target_profile.upper()
    if profile_upper not in _VALID_TARGET_PROFILES:
        return ComplianceResult(
            valid=False,
            suggestions=[
                f"Fehler: Ungültiges Zielprofil '{target_profile}'. Erlaubt: XRECHNUNG, ZUGFERD."
            ],
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

    return checks
