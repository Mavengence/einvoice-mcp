"""Compliance checking tool for XRechnung/ZUGFeRD."""

import logging
from typing import Any

from einvoice_mcp.config import MAX_XML_SIZE
from einvoice_mcp.errors import EInvoiceError
from einvoice_mcp.models import ComplianceResult
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.compliance_checks import check_fields

logger = logging.getLogger(__name__)

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
        "bei Gutschriften (TypeCode 381) und Korrekturrechnungen (TypeCode 384) "
        "muss die Originalrechnung referenziert werden."
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
    "LW-FMT": (
        "Die Leitweg-ID hat kein gültiges Format. "
        "Erwartet: Grobadresse-Feinadresse-Prüfziffer (z.B. 04011000-12345-67)."
    ),
    "VAT-FMT": (
        "Die deutsche USt-IdNr. hat kein gültiges Format. "
        "Erwartet: DE + 9 Ziffern (z.B. DE123456789)."
    ),
    "EX-TAX-RATE": (
        "Bei Drittlandslieferung (Kategorie G) "
        "muss der Steuersatz 0% betragen."
    ),
    "IC-BT-48": (
        "Bei innergemeinschaftlicher Lieferung (Steuerkategorie K / §4 Nr. 1b UStG) "
        "muss die USt-IdNr. des Käufers (BT-48) angegeben sein."
    ),
    "IC-TAX-RATE": (
        "Bei innergemeinschaftlicher Lieferung (Kategorie K) "
        "muss der Steuersatz 0% betragen."
    ),
    "KB-INFO": (
        "Der Rechnungsbetrag liegt unter 250€ — diese Rechnung könnte als "
        "Kleinbetragsrechnung (§33 UStDV) gelten. Bestimmte Pflichtangaben "
        "wie Käufername und -adresse können entfallen."
    ),
    "KU-NOTE": (
        "Steuerkategorie E (steuerbefreit) erkannt, aber kein Hinweis auf §19 UStG "
        "(Kleinunternehmerregelung) oder einen anderen Befreiungsgrund in den "
        "Rechnungsbemerkungen gefunden. Bitte fügen Sie einen Hinweis wie "
        "'Gemäß §19 UStG wird keine Umsatzsteuer berechnet.' hinzu."
    ),
    "E-BT-120": (
        "Bei Steuerkategorie E (steuerbefreit) ist der Befreiungsgrund (BT-120) "
        "gemäß BR-E-10 erforderlich. Bitte geben Sie den Grund an, z.B. "
        "'Gemäß §19 UStG wird keine Umsatzsteuer berechnet.' oder "
        "'Steuerbefreit gemäß §4 Nr. 11 UStG.'"
    ),
    "DD-BT-89": (
        "Bei SEPA-Lastschrift (PaymentMeansCode 59) ist die Mandatsreferenz "
        "(BT-89) gemäß BR-DE-24 erforderlich."
    ),
    "DD-BT-91": (
        "Bei SEPA-Lastschrift (PaymentMeansCode 59) ist die IBAN des Käufers "
        "(BT-91) erforderlich."
    ),
    "BT-20": (
        "BT-20 (Zahlungsbedingungen) fehlt — "
        "gemäß BR-DE-15 müssen Zahlungsbedingungen angegeben werden."
    ),
    "CC-BT-87": (
        "Bei Kreditkartenzahlung (PaymentMeansCode 48) ist die Kartennummer "
        "(BT-87, letzte 4-6 Stellen) erforderlich."
    ),
    "REP-BT-63": (
        "Der steuerliche Vertreter (BG-11) wurde angegeben, aber die "
        "USt-IdNr. des Vertreters (BT-63) fehlt — diese ist Pflicht."
    ),
    "BR-DE-3": (
        "BR-DE-3: Der Verkäufer ist nicht in Deutschland ansässig. "
        "Gemäß BR-DE-3 muss in diesem Fall ein steuerlicher Vertreter (BG-11) "
        "mit Name, Adresse und USt-IdNr. angegeben werden."
    ),
    "RC-COUNTRY": (
        "Bei Reverse Charge (§13b UStG / Kategorie AE) sollten "
        "Verkäufer und Käufer in unterschiedlichen Ländern ansässig sein. "
        "Beide Parteien haben denselben Ländercode — bitte prüfen."
    ),
    "IC-COUNTRY": (
        "Bei innergemeinschaftlicher Lieferung (Kategorie K / §4 Nr. 1b UStG) "
        "müssen Verkäufer und Käufer in verschiedenen EU-Ländern ansässig sein. "
        "Beide Parteien haben denselben Ländercode."
    ),
    "384-BT-25": (
        "BT-25 (Vorherige Rechnungsnummer) fehlt — "
        "bei Korrekturrechnungen (TypeCode 384) muss die zu korrigierende "
        "Originalrechnung gemäß §14 Abs. 4 UStG referenziert werden."
    ),
    "BT-48": (
        "BT-48 (USt-IdNr. des Käufers) — "
        "erforderlich bei innergemeinschaftlichen Lieferungen (K), "
        "Reverse Charge (AE) und anderen EU-grenzüberschreitenden Transaktionen."
    ),
    "BT-86": (
        "BT-86 (BIC der Bank des Verkäufers) — "
        "optional, aber empfohlen für SEPA-Überweisungen zur Fehlerreduzierung. "
        "Für DE-IBANs wird der BIC automatisch ermittelt, bei EU-IBANs empfohlen."
    ),
    "BR-DE-18": (
        "BR-DE-18: Mindestens eine Zahlungsart (BT-81) muss angegeben werden. "
        "Gültige Codes: 58 (SEPA-Überweisung), 59 (SEPA-Lastschrift), "
        "30 (Banküberweisung), 48 (Kreditkarte) etc."
    ),
    "BR-DE-19": (
        "BR-DE-19: Der Zahlungsart-Code (BT-81) ist ungültig. "
        "Erlaubte Codes gemäß UNTDID 4461: 1, 10, 20, 30, 31, 42, 48, 49, "
        "57, 58, 59, 97, ZZZ."
    ),
    "BR-DE-16": (
        "BR-DE-16/21: Der EAS-Code (schemeID) der elektronischen Adresse des "
        "Verkäufers (BT-34) ist ungültig. Gängige Codes: EM (E-Mail), "
        "9930 (USt-IdNr.), 0204 (Leitweg-ID)."
    ),
    "BR-DE-22": (
        "BR-DE-22: Der EAS-Code (schemeID) der elektronischen Adresse des "
        "Käufers (BT-49) ist ungültig. Gängige Codes: EM (E-Mail), "
        "9930 (USt-IdNr.), 0204 (Leitweg-ID)."
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
    field_checks = check_fields(xml_content, xrechnung=is_xrechnung)
    missing_fields = [fc.field for fc in field_checks if fc.required and not fc.present]
    suggestions = [SUGGESTIONS_MAP[f] for f in missing_fields if f in SUGGESTIONS_MAP]

    # Add non-required advisory checks (warnings + informational notes)
    advisory_fields = [
        fc.field for fc in field_checks if not fc.required and not fc.present
    ]
    for af in advisory_fields:
        if af in SUGGESTIONS_MAP:
            suggestions.append(SUGGESTIONS_MAP[af])
    # Informational advisories (present=True, required=False)
    info_fields = [
        fc.field for fc in field_checks if not fc.required and fc.present
    ]
    for inf in info_fields:
        if inf in SUGGESTIONS_MAP:
            suggestions.append(SUGGESTIONS_MAP[inf])

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
