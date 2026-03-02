"""FastMCP server entry point for the e-invoice MCP."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations
from pydantic import ValidationError as PydanticValidationError

from einvoice_mcp.config import settings
from einvoice_mcp.models import (
    AllowanceCharge,
    InvoiceData,
    InvoiceProfile,
    ItemAttribute,
    LineItem,
    SupportingDocument,
)
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.compliance import check_compliance
from einvoice_mcp.tools.generate import generate_xrechnung, generate_zugferd
from einvoice_mcp.tools.parse import parse_einvoice
from einvoice_mcp.tools.validate import validate_xrechnung, validate_zugferd

logging.basicConfig(
    level=settings.log_level,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Valid profile values for user-facing error messages
_VALID_PROFILES = ", ".join(p.value for p in InvoiceProfile)


@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict[str, Any]]:
    """Initialize and clean up the KoSIT client."""
    kosit = KoSITClient()
    healthy = await kosit.health_check()
    if healthy:
        logger.info("KoSIT validator is reachable at %s", settings.kosit_url)
    else:
        logger.warning(
            "KoSIT validator is NOT reachable at %s — "
            "validation tools will return errors until it is available.",
            settings.kosit_url,
        )
    try:
        yield {"kosit": kosit}
    finally:
        await kosit.close()


mcp = FastMCP(
    "einvoice-mcp",
    instructions=(
        "MCP-Server für deutsche E-Rechnungen (XRechnung / ZUGFeRD). "
        "Ermöglicht Validierung, Erstellung, Parsing und Compliance-Prüfung "
        "von elektronischen Rechnungen gemäß EN 16931."
    ),
    lifespan=app_lifespan,
)


@mcp.resource("einvoice://schemas/line-item")
def schema_line_item() -> str:
    """JSON-Schema für eine Rechnungsposition (items-Array-Element).

    Verwenden Sie dieses Schema um korrekte JSON-Objekte für den
    'items' Parameter der generate-Tools zu erstellen.
    """
    return json.dumps(LineItem.model_json_schema(), ensure_ascii=False, indent=2)


@mcp.resource("einvoice://schemas/allowance-charge")
def schema_allowance_charge() -> str:
    """JSON-Schema für Zu-/Abschläge (allowances_charges-Array-Element).

    Verwenden Sie dieses Schema um korrekte JSON-Objekte für den
    'allowances_charges' Parameter der generate-Tools zu erstellen.
    """
    return json.dumps(AllowanceCharge.model_json_schema(), ensure_ascii=False, indent=2)


@mcp.resource("einvoice://schemas/item-attribute")
def schema_item_attribute() -> str:
    """JSON-Schema für Artikelmerkmale (BG-30, BT-160/BT-161).

    Name/Wert-Paare für Produkteigenschaften wie Farbe, Größe, Material.
    """
    return json.dumps(ItemAttribute.model_json_schema(), ensure_ascii=False, indent=2)


@mcp.resource("einvoice://schemas/supporting-document")
def schema_supporting_document() -> str:
    """JSON-Schema für zusätzliche Belegdokumente (BG-24, BT-122..BT-125).

    Anhänge wie Zollpapiere, Zertifikate, Zeitnachweise.
    """
    return json.dumps(SupportingDocument.model_json_schema(), ensure_ascii=False, indent=2)


@mcp.resource("einvoice://schemas/invoice-data")
def schema_invoice_data() -> str:
    """Vollständiges JSON-Schema für InvoiceData.

    Zeigt alle verfügbaren Felder mit Typen, Beschreibungen und
    Validierungsregeln für die Rechnungserstellung.
    """
    return json.dumps(InvoiceData.model_json_schema(), ensure_ascii=False, indent=2)


# --- Reference resources (code tables for AI agents) ---


@mcp.resource("einvoice://reference/type-codes")
def reference_type_codes() -> str:
    """Rechnungsart-Codes (BT-3) gemäß UNTDID 1001 / EN 16931.

    Zeigt alle gültigen Codes mit deutscher Beschreibung.
    """
    return json.dumps(
        {
            "380": "Handelsrechnung (Standard)",
            "381": "Gutschrift / Credit Note",
            "384": "Korrekturrechnung",
            "389": "Selbstfakturierte Rechnung (Self-billed)",
            "875": "Teilrechnung (Partial invoice)",
            "876": "Teilschlussrechnung (Partial final invoice)",
            "877": "Schlussrechnung (Final invoice)",
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("einvoice://reference/payment-means-codes")
def reference_payment_means_codes() -> str:
    """Zahlungsart-Codes (BT-81) gemäß UNTDID 4461 / EN 16931.

    Die häufigsten Codes für den deutschen Markt.
    """
    return json.dumps(
        {
            "1": "Nicht definiert (Instrument not defined)",
            "10": "Bar (Cash)",
            "20": "Scheck (Cheque)",
            "30": "Überweisung (Credit transfer)",
            "31": "Lastschrift (Debit transfer)",
            "42": "Zahlung an Bankkonto (Payment to bank account)",
            "48": "Kreditkarte (Bank card / credit card)",
            "49": "Lastschrift (Direct debit)",
            "57": "Dauerauftrag (Standing agreement)",
            "58": "SEPA-Überweisung (SEPA credit transfer) — STANDARD",
            "59": "SEPA-Lastschrift (SEPA direct debit)",
            "97": "Clearing zwischen Partnern (Clearing between partners)",
            "ZZZ": "Vereinbarte Zahlungsart (Mutually defined)",
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("einvoice://reference/tax-categories")
def reference_tax_categories() -> str:
    """Steuerkategorie-Codes (BT-151) gemäß UNTDID 5305 / EN 16931.

    Alle 9 gültigen Kategorien mit deutschen Erklärungen und typischen Steuersätzen.
    """
    return json.dumps(
        {
            "S": {
                "name": "Normaler Steuersatz (Standard rate)",
                "typical_rates": ["19.00", "7.00"],
                "usage": "Standardfall für B2B-Rechnungen in Deutschland",
            },
            "Z": {
                "name": "Nullsatz (Zero rated)",
                "typical_rates": ["0.00"],
                "usage": "Selten in DE — für spezielle EU-Regelungen",
            },
            "E": {
                "name": "Steuerbefreit (Exempt)",
                "typical_rates": ["0.00"],
                "usage": "§19 UStG (Kleinunternehmer), §4 UStG (steuerbefreite Umsätze)",
                "note": "BT-120 (ExemptionReason) ist Pflicht",
            },
            "AE": {
                "name": "Reverse Charge (§13b UStG)",
                "typical_rates": ["0.00"],
                "usage": "Steuerschuldnerschaft des Leistungsempfängers",
                "note": "BT-31 und BT-48 (USt-IdNr.) sind Pflicht",
            },
            "K": {
                "name": "Innergemeinschaftliche Lieferung (§4 Nr. 1b UStG)",
                "typical_rates": ["0.00"],
                "usage": "Lieferung an Unternehmer in anderen EU-Ländern",
                "note": "BT-48 (Käufer-USt-IdNr.) ist Pflicht",
            },
            "G": {
                "name": "Ausfuhrlieferung / Export (§4 Nr. 1a UStG)",
                "typical_rates": ["0.00"],
                "usage": "Lieferung in Drittländer (außerhalb EU)",
            },
            "O": {
                "name": "Nicht steuerbar (Not subject to VAT)",
                "typical_rates": ["0.00"],
                "usage": "Umsätze außerhalb des Steuergebiets",
            },
            "L": {
                "name": "IGIC (Kanarische Inseln)",
                "typical_rates": ["7.00"],
                "usage": "Kanarische Inseln Steuer",
            },
            "M": {
                "name": "IPSI (Ceuta und Melilla)",
                "typical_rates": ["4.00"],
                "usage": "Ceuta und Melilla Steuer",
            },
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("einvoice://reference/unit-codes")
def reference_unit_codes() -> str:
    """Häufige Mengeneinheiten-Codes (BT-130) gemäß UN/ECE Recommendation 20.

    Die in deutschen Rechnungen am häufigsten verwendeten Einheiten.
    """
    return json.dumps(
        {
            "H87": "Stück (Piece)",
            "HUR": "Stunde (Hour)",
            "DAY": "Tag (Day)",
            "MON": "Monat (Month)",
            "ANN": "Jahr (Year)",
            "KGM": "Kilogramm",
            "GRM": "Gramm",
            "TNE": "Tonne",
            "MTR": "Meter",
            "KTM": "Kilometer",
            "MTK": "Quadratmeter",
            "LTR": "Liter",
            "MTQ": "Kubikmeter",
            "SET": "Satz / Set",
            "PR": "Paar (Pair)",
            "BX": "Karton / Box",
            "C62": "Einheit / one (generic unit)",
            "XPK": "Paket (Package)",
            "MIN": "Minute",
            "SEC": "Sekunde",
            "WEE": "Woche (Week)",
            "KWH": "Kilowattstunde",
            "MWH": "Megawattstunde",
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("einvoice://reference/eas-codes")
def reference_eas_codes() -> str:
    """Electronic Address Scheme Codes (BT-34-1/BT-49-1).

    Identifizierungsschema für elektronische Adressen in XRechnung.
    """
    return json.dumps(
        {
            "EM": "E-Mail-Adresse — STANDARD für deutsche Unternehmen",
            "9930": "USt-IdNr. als elektronische Adresse (DE + Nummer)",
            "0088": "EAN Location Number (GLN)",
            "0204": "Leitweg-ID (deutsche öffentliche Verwaltung)",
            "9906": "IT Codice Fiscale",
            "9925": "IT Partita IVA",
            "0007": "Organisationskennung (DUNS)",
            "0060": "DUNS+4 Nummer",
            "0190": "Dutch Originator's Identification Number",
            "0191": "Centre of Registers and Information Systems, Estonia",
            "0192": "Finnish OVT code",
            "0195": "Singapore UEN",
            "0196": "Icelandic kennitala",
            "0198": "Danish CVR number",
            "0199": "LEI (Legal Entity Identifier)",
            "0200": "Lithuanian juridinio asmens kodas",
            "0201": "LT KPV number for natural persons",
            "0208": "Belgian enterprise number (KBO/BCE)",
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.resource("einvoice://system/kosit-status")
async def kosit_status(ctx: Context) -> str:
    """Aktueller Status des KoSIT-Validators.

    Prüft on-demand, ob der KoSIT-Validator erreichbar ist.
    Gibt JSON mit 'healthy', 'url' und 'message' zurück.
    """
    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    healthy = await kosit.health_check()
    return json.dumps(
        {
            "healthy": healthy,
            "url": settings.kosit_url,
            "message": (
                "KoSIT-Validator ist erreichbar und bereit."
                if healthy
                else "KoSIT-Validator ist NICHT erreichbar. "
                "Bitte prüfen Sie ob der Docker-Container läuft."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


@mcp.prompt()
def gutschrift_erstellen() -> str:
    """Anleitung: Gutschrift / Credit Note (TypeCode 381) erstellen.

    Schritt-für-Schritt-Anleitung für die korrekte Erstellung einer Gutschrift
    nach deutschem Steuerrecht (§14 Abs. 4 UStG).
    """
    return (
        "# Gutschrift (Credit Note) erstellen — Checkliste\n\n"
        "Eine Gutschrift korrigiert eine bereits gestellte Rechnung.\n\n"
        "## Pflichtparameter:\n"
        "- `type_code`: **381** (Gutschrift)\n"
        "- `preceding_invoice_number`: Nummer der Originalrechnung (BT-25, PFLICHT)\n"
        "- Alle Standardfelder wie bei einer normalen Rechnung\n\n"
        "## Beträge:\n"
        "- Positionen mit **positiven** Beträgen eintragen\n"
        "- Die Gutschrift reduziert die offene Forderung\n\n"
        "## Beispiel:\n"
        "```\n"
        "type_code: '381'\n"
        "preceding_invoice_number: 'RE-2026-001'\n"
        "invoice_note: 'Gutschrift zu Rechnung RE-2026-001 wegen Retoure'\n"
        "```\n\n"
        "## Häufige Fehler:\n"
        "- BT-25 vergessen → KoSIT-Validierung schlägt fehl\n"
        "- Falscher TypeCode (380 statt 381)\n"
        "- Negative Beträge (nicht nötig — Gutschrift-Semantik ist implizit)"
    )


@mcp.prompt()
def reverse_charge_checkliste() -> str:
    """Checkliste für Reverse Charge (§13b UStG) — Kategorie AE.

    Alle Pflichtangaben und Prüfschritte für Rechnungen mit
    Steuerschuldnerschaft des Leistungsempfängers.
    """
    return (
        "# Reverse Charge (§13b UStG) — Checkliste\n\n"
        "## Voraussetzungen:\n"
        "- Leistender Unternehmer im Ausland ODER\n"
        "- Bauleistungen (§13b Abs. 2 Nr. 4 UStG) ODER\n"
        "- Andere §13b-Tatbestände\n\n"
        "## Pflichtangaben:\n"
        "1. **tax_category**: `AE` für alle Positionen\n"
        "2. **tax_rate**: `0.00` (muss 0% sein)\n"
        "3. **seller_tax_id**: USt-IdNr. des Verkäufers (BT-31, PFLICHT)\n"
        "4. **buyer_tax_id**: USt-IdNr. des Käufers (BT-48, PFLICHT)\n"
        "5. **tax_exemption_reason**: z.B. 'Reverse Charge — "
        "Steuerschuldnerschaft des Leistungsempfängers gemäß §13b UStG'\n"
        "6. **tax_exemption_reason_code**: `vatex-eu-ae`\n\n"
        "## Hinweis auf der Rechnung:\n"
        "Pflichthinweis nach §14a Abs. 5 UStG: "
        "'Steuerschuldnerschaft des Leistungsempfängers'\n\n"
        "## Beispiel:\n"
        "```json\n"
        '{"description": "IT-Beratung", "quantity": 10, "unit_code": "HUR",\n'
        ' "unit_price": 150.00, "tax_rate": 0.00, "tax_category": "AE"}\n'
        "```"
    )


@mcp.prompt()
def xrechnung_schnellstart() -> str:
    """Schnellstart: XRechnung für öffentliche Auftraggeber erstellen.

    Minimale Pflichtangaben für eine gültige XRechnung 3.0.
    """
    return (
        "# XRechnung — Schnellstart\n\n"
        "## Mindestangaben für eine gültige XRechnung:\n\n"
        "### Pflicht:\n"
        "- `invoice_id`: Eindeutige Rechnungsnummer\n"
        "- `issue_date`: Rechnungsdatum (YYYY-MM-DD)\n"
        "- `seller_name`, `seller_street`, `seller_city`, `seller_postal_code`, "
        "`seller_country_code`\n"
        "- `seller_tax_id`: USt-IdNr. (DE...)\n"
        "- `buyer_name`, `buyer_street`, `buyer_city`, `buyer_postal_code`, "
        "`buyer_country_code`\n"
        "- `items`: Mindestens eine Position\n"
        "- `leitweg_id` ODER `buyer_reference`: Leitweg-ID des Auftraggebers\n\n"
        "### XRechnung-spezifisch (BR-DE-Regeln):\n"
        "- `seller_electronic_address`: E-Mail des Verkäufers (BT-34)\n"
        "- `buyer_electronic_address`: E-Mail des Käufers (BT-49)\n"
        "- `seller_contact_name`: Ansprechpartner (BT-41, BR-DE-5)\n"
        "- `seller_contact_phone`: Telefon (BT-42, BR-DE-6)\n"
        "- `seller_contact_email`: E-Mail (BT-43, BR-DE-7)\n"
        "- `payment_terms_text`: Zahlungsbedingungen (BT-20, BR-DE-15)\n"
        "- `delivery_date` ODER `service_period_start`/`service_period_end`\n\n"
        "### Leitweg-ID Format:\n"
        "Typisch: `04011000-12345-67` (Grobadresse-Feinadresse-Prüfziffer)\n"
        "Fragen Sie den Auftraggeber nach seiner Leitweg-ID.\n\n"
        "### Empfohlene Zahlungsart:\n"
        "- `payment_means_type_code`: `58` (SEPA-Überweisung)\n"
        "- `seller_iban`: IBAN des Verkäufers"
    )


@mcp.prompt()
def korrekturrechnung_erstellen() -> str:
    """Anleitung: Korrekturrechnung (TypeCode 384) erstellen.

    Unterschiede zur Gutschrift und korrekte Vorgehensweise
    nach §14 Abs. 4 UStG.
    """
    return (
        "# Korrekturrechnung (TypeCode 384) erstellen\n\n"
        "## Unterschied zur Gutschrift (381):\n"
        "- **381 Gutschrift**: Reduziert eine Forderung (z.B. Retoure, Rabatt)\n"
        "- **384 Korrekturrechnung**: Ersetzt/korrigiert eine fehlerhafte Rechnung\n\n"
        "## Pflichtparameter:\n"
        "- `type_code`: **384**\n"
        "- `preceding_invoice_number`: Nummer der fehlerhaften Originalrechnung (BT-25)\n"
        "- `invoice_note`: Grund der Korrektur angeben\n"
        "- Alle korrekten Daten der neuen Rechnung\n\n"
        "## Beispiel:\n"
        "```\n"
        "type_code: '384'\n"
        "preceding_invoice_number: 'RE-2026-001'\n"
        "invoice_note: 'Korrektur der Rechnung RE-2026-001 — "
        "falscher Steuersatz korrigiert'\n"
        "```\n\n"
        "## Steuerliche Wirkung:\n"
        "- Die Korrekturrechnung ERSETZT die Originalrechnung\n"
        "- Der Käufer muss den Vorsteuerabzug der Originalrechnung korrigieren\n"
        "- Zeitpunkt: Die Korrektur wirkt für den Besteuerungszeitraum "
        "der Originalrechnung"
    )


@mcp.prompt()
def abschlagsrechnung_guide() -> str:
    """Anleitung: Abschlagsrechnung / Teilrechnung (TypeCode 875/876/877).

    Erklärung der Rechnungstypen für Teilleistungen und Schlussrechnungen
    nach §632a BGB und §14 Abs. 1 UStG.
    """
    return (
        "# Abschlagsrechnung & Teilrechnung — TypeCode 875/876/877\n\n"
        "## TypeCode-Auswahl:\n"
        "- **875 — Teilrechnung (Partial Invoice)**: Rechnung über eine "
        "Teilleistung innerhalb eines Gesamtauftrags\n"
        "- **876 — Vorauszahlungsrechnung (Prepayment Invoice)**: "
        "Abschlagsrechnung VOR Leistungserbringung\n"
        "- **877 — Schlussrechnung (Final Invoice)**: Abschluss nach "
        "vorherigen Teil-/Vorauszahlungen\n\n"
        "## Pflichtangaben:\n"
        "- `type_code`: **875**, **876** oder **877**\n"
        "- `contract_reference`: Vertragsnummer / Auftragsnummer (BT-12)\n"
        "- `invoice_note`: Bezug auf Gesamtauftrag und bisherige Zahlungen\n"
        "- `project_reference`: Projektnummer, falls vorhanden (BT-11)\n\n"
        "## Beispiel Abschlagsrechnung:\n"
        "```\n"
        "type_code: '876'\n"
        "contract_reference: 'V-2026-100'\n"
        "invoice_note: '2. Abschlag für Auftrag V-2026-100 "
        "(Gesamtauftrag: 50.000€, bisherige Abschläge: 15.000€)'\n"
        "```\n\n"
        "## Schlussrechnung:\n"
        "```\n"
        "type_code: '877'\n"
        "contract_reference: 'V-2026-100'\n"
        "invoice_note: 'Schlussrechnung V-2026-100. "
        "Gesamtleistung: 50.000€, abzgl. Abschläge: 30.000€'\n"
        "```\n\n"
        "## Steuerrecht:\n"
        "- Abschläge sind umsatzsteuerpflichtig bei Vereinnahmung "
        "(§13 Abs. 1 Nr. 1a Satz 4 UStG)\n"
        "- Schlussrechnung korrigiert Vorsteuerabzug der Abschläge"
    )


@mcp.prompt()
def ratenzahlung_rechnung() -> str:
    """Anleitung: Rechnung mit Ratenzahlung erstellen.

    Korrekte Darstellung von Ratenzahlungsvereinbarungen
    in XRechnung/ZUGFeRD.
    """
    return (
        "# Rechnung mit Ratenzahlung\n\n"
        "## Darstellung in XRechnung:\n"
        "Ratenzahlung wird über `payment_terms_text` (BT-20) abgebildet.\n\n"
        "## Beispiel:\n"
        "```\n"
        "payment_terms_text: '3 Raten: "
        "1. Rate 1.000€ fällig 01.04.2026, "
        "2. Rate 1.000€ fällig 01.05.2026, "
        "3. Rate 1.000€ fällig 01.06.2026'\n"
        "due_date: '2026-04-01'  # Erste Fälligkeit\n"
        "```\n\n"
        "## Hinweise:\n"
        "- `due_date` (BT-9): Datum der **ersten** Rate\n"
        "- `payment_terms_text` (BT-20): Gesamten Ratenplan textlich beschreiben\n"
        "- Optional: Skonto-Bedingungen pro Rate möglich\n\n"
        "## Mit Skonto:\n"
        "```\n"
        "payment_terms_text: '3 Raten à 1.000€, "
        "2% Skonto bei Zahlung innerhalb von 10 Tagen'\n"
        "skonto_percent: 2.0\n"
        "skonto_days: 10\n"
        "```\n\n"
        "## Rechtlicher Hintergrund:\n"
        "- §271 BGB: Fälligkeit nach Vereinbarung\n"
        "- Ratenvereinbarungen sollten schriftlich fixiert sein"
    )


@mcp.prompt()
def handwerkerrechnung_35a() -> str:
    """Anleitung: Handwerkerrechnung nach §35a EStG.

    Rechnungsstellung für haushaltsnahe Handwerkerleistungen mit
    Ausweisung der Arbeitskosten für den Steuerabzug des Kunden.
    """
    return (
        "# Handwerkerrechnung für §35a EStG\n\n"
        "## Hintergrund:\n"
        "Kunden können 20% der Arbeitskosten (max. 1.200€/Jahr) als "
        "Steuerermäßigung geltend machen (§35a Abs. 3 EStG).\n\n"
        "## Pflicht auf der Rechnung:\n"
        "1. **Getrennte Ausweisung** von Arbeitskosten und Materialkosten\n"
        "2. **Adresse der Leistungserbringung** (Haushalt des Kunden)\n"
        "3. **Banküberweisung** als Zahlungsart (§35a Abs. 5 Satz 3: "
        "keine Barzahlung!)\n\n"
        "## Umsetzung in XRechnung:\n"
        "```\n"
        "items:\n"
        "  - description: 'Arbeitsleistung: Bad sanieren (30 Std)'\n"
        "    quantity: 30\n"
        "    unit_code: 'HUR'\n"
        "    unit_price: 55.00\n"
        "    tax_rate: 19.00\n"
        "  - description: 'Material: Fliesen, Kleber, Silikon'\n"
        "    quantity: 1\n"
        "    unit_code: 'C62'\n"
        "    unit_price: 800.00\n"
        "    tax_rate: 19.00\n"
        "delivery_location_name: 'Privathaushalt Meier'\n"
        "delivery_street: 'Musterstraße 42'\n"
        "delivery_city: 'München'\n"
        "delivery_postal_code: '80331'\n"
        "delivery_country_code: 'DE'\n"
        "payment_means_type_code: '58'  # SEPA-Überweisung — PFLICHT!\n"
        "invoice_note: 'Arbeitskosten: 1.650€ netto "
        "(§35a EStG steuerlich absetzbar)'\n"
        "```\n\n"
        "## Häufige Fehler:\n"
        "- Keine Trennung von Material/Arbeit → Finanzamt lehnt ab\n"
        "- Barzahlung → §35a nicht anwendbar\n"
        "- Lieferort fehlt → Nachweis des Haushalts nicht erbracht"
    )


@mcp.prompt()
def typecode_entscheidungshilfe() -> str:
    """Entscheidungshilfe: Welcher TypeCode für welchen Anlass?

    Übersicht aller unterstützten Rechnungstypen nach EN 16931
    mit deutschen Erklärungen und Anwendungsfällen.
    """
    return (
        "# TypeCode — Welcher Rechnungstyp?\n\n"
        "| Code | Typ | Wann verwenden? |\n"
        "|------|-----|------------------|\n"
        "| **380** | Handelsrechnung | Standardrechnung für Lieferungen/Leistungen |\n"
        "| **381** | Gutschrift | Korrektur zugunsten des Käufers "
        "(Retoure, Rabatt) |\n"
        "| **384** | Korrekturrechnung | Fehlerhafte Rechnung ersetzen |\n"
        "| **389** | Selbstfakturierte Rechnung | Käufer stellt Rechnung "
        "im Namen des Verkäufers |\n"
        "| **875** | Teilrechnung | Rechnung über Teilleistung |\n"
        "| **876** | Vorauszahlungsrechnung | Abschlag vor Leistung |\n"
        "| **877** | Schlussrechnung | Endabrechnung nach Abschlägen |\n\n"
        "## Entscheidungsbaum:\n\n"
        "1. **Neue Lieferung/Leistung?** → **380**\n"
        "2. **Korrektur einer Rechnung?**\n"
        "   - Zugunsten des Käufers → **381** (Gutschrift)\n"
        "   - Fehlerhafte Daten korrigieren → **384** (Korrekturrechnung)\n"
        "3. **Teilweise Leistungserbringung?**\n"
        "   - Abschlag vorab → **876**\n"
        "   - Teilleistung erbracht → **875**\n"
        "   - Letzte Rechnung nach Abschlägen → **877**\n"
        "4. **Käufer stellt Rechnung?** → **389** (Gutschriftverfahren)\n\n"
        "## Pflichtfelder je nach TypeCode:\n"
        "- **381/384**: `preceding_invoice_number` (BT-25) PFLICHT\n"
        "- **875/876/877**: `contract_reference` (BT-12) empfohlen\n"
        "- **389**: Vereinbarung zwischen den Parteien erforderlich"
    )


# Map Pydantic field paths to German BT descriptions for user-friendly errors
_FIELD_TO_BT: dict[str, str] = {
    "invoice_id": "BT-1 (Rechnungsnummer)",
    "issue_date": "BT-2 (Rechnungsdatum)",
    "type_code": "BT-3 (Rechnungsart)",
    "currency": "BT-5 (Währung)",
    "seller": "BG-4 (Verkäufer)",
    "seller.name": "BT-27 (Verkäufername)",
    "seller.address": "BG-5 (Verkäuferadresse)",
    "seller.address.street": "BT-35 (Straße Verkäufer)",
    "seller.address.city": "BT-37 (Ort Verkäufer)",
    "seller.address.postal_code": "BT-38 (PLZ Verkäufer)",
    "seller.address.country_code": "BT-40 (Land Verkäufer)",
    "seller.tax_id": "BT-31 (USt-IdNr. Verkäufer)",
    "seller.electronic_address": "BT-34 (Elektr. Adresse Verkäufer)",
    "buyer": "BG-7 (Käufer)",
    "buyer.name": "BT-44 (Käufername)",
    "buyer.address": "BG-8 (Käuferadresse)",
    "buyer.address.street": "BT-50 (Straße Käufer)",
    "buyer.address.city": "BT-52 (Ort Käufer)",
    "buyer.address.postal_code": "BT-53 (PLZ Käufer)",
    "buyer.address.country_code": "BT-55 (Land Käufer)",
    "items": "BG-25 (Rechnungsposition)",
    "seller_iban": "BT-84 (IBAN)",
    "seller_bic": "BT-86 (BIC)",
    "leitweg_id": "BT-10 (Leitweg-ID)",
}


def _format_pydantic_errors(exc: PydanticValidationError) -> str:
    """Format Pydantic validation errors with BT number references."""
    parts: list[str] = []
    for err in exc.errors()[:5]:
        loc = ".".join(str(p) for p in err["loc"])
        bt_ref = _FIELD_TO_BT.get(loc, loc)
        parts.append(f"{bt_ref}: {err['msg']}")
    return "Fehler: Ungültige Rechnungsdaten:\n" + "\n".join(f"  - {p}" for p in parts)


def _build_invoice_data(
    *,
    invoice_id: str,
    issue_date: str,
    seller_name: str,
    seller_street: str,
    seller_city: str,
    seller_postal_code: str,
    seller_country_code: str,
    seller_tax_id: str,
    buyer_name: str,
    buyer_street: str,
    buyer_city: str,
    buyer_postal_code: str,
    buyer_country_code: str,
    items_json: str,
    seller_street_2: str = "",
    seller_street_3: str = "",
    seller_country_subdivision: str = "",
    buyer_street_2: str = "",
    buyer_street_3: str = "",
    buyer_country_subdivision: str = "",
    buyer_tax_id: str = "",
    currency: str = "EUR",
    payment_terms_days: int | None = None,
    leitweg_id: str = "",
    buyer_reference: str = "",
    profile: str = "XRECHNUNG",
    seller_electronic_address: str = "",
    seller_electronic_address_scheme: str = "EM",
    buyer_electronic_address: str = "",
    buyer_electronic_address_scheme: str = "EM",
    seller_contact_name: str = "",
    seller_contact_email: str = "",
    seller_contact_phone: str = "",
    buyer_contact_name: str = "",
    buyer_contact_email: str = "",
    buyer_contact_phone: str = "",
    seller_iban: str = "",
    seller_bic: str = "",
    seller_bank_name: str = "",
    type_code: str = "380",
    seller_tax_number: str = "",
    seller_registration_id: str = "",
    buyer_registration_id: str = "",
    delivery_party_name: str = "",
    delivery_street: str = "",
    delivery_city: str = "",
    delivery_postal_code: str = "",
    delivery_country_code: str = "",
    delivery_date: str = "",
    service_period_start: str = "",
    service_period_end: str = "",
    due_date: str = "",
    invoice_note: str = "",
    payment_terms_text: str = "",
    purchase_order_reference: str = "",
    sales_order_reference: str = "",
    contract_reference: str = "",
    project_reference: str = "",
    preceding_invoice_number: str = "",
    despatch_advice_reference: str = "",
    invoiced_object_identifier: str = "",
    business_process_type: str = "",
    buyer_iban: str = "",
    mandate_reference_id: str = "",
    skonto_percent: str = "",
    skonto_days: int | None = None,
    skonto_base_amount: str = "",
    payment_means_type_code: str = "58",
    remittance_information: str = "",
    allowances_charges_json: str = "",
    tax_exemption_reason: str = "",
    tax_exemption_reason_code: str = "",
    tender_or_lot_reference: str = "",
    seller_trading_name: str = "",
    buyer_trading_name: str = "",
    payee_name: str = "",
    payee_id: str = "",
    payee_legal_registration_id: str = "",
    payment_card_pan: str = "",
    payment_card_holder: str = "",
    seller_tax_rep_name: str = "",
    seller_tax_rep_street: str = "",
    seller_tax_rep_city: str = "",
    seller_tax_rep_postal_code: str = "",
    seller_tax_rep_country_code: str = "",
    seller_tax_rep_tax_id: str = "",
    receiving_advice_reference: str = "",
    delivery_location_id: str = "",
    payment_means_text: str = "",
    supporting_documents_json: str = "",
) -> InvoiceData | str:
    """Build InvoiceData from flat MCP tool parameters.

    Returns InvoiceData on success, or a German error string on failure.
    """
    try:
        items_list = json.loads(items_json)
    except json.JSONDecodeError:
        return "Fehler: 'items' muss ein gültiges JSON-Array sein."

    ac_list: list[dict[str, object]] = []
    if allowances_charges_json:
        try:
            ac_list = json.loads(allowances_charges_json)
        except json.JSONDecodeError:
            return "Fehler: 'allowances_charges' muss ein gültiges JSON-Array sein."

    sd_list: list[dict[str, object]] = []
    if supporting_documents_json:
        try:
            sd_list = json.loads(supporting_documents_json)
        except json.JSONDecodeError:
            return "Fehler: 'supporting_documents' muss ein gültiges JSON-Array sein."

    try:
        invoice_profile = InvoiceProfile(profile)
    except ValueError:
        return f"Fehler: Ungültiges Profil. Erlaubt: {_VALID_PROFILES}."

    try:
        return InvoiceData.model_validate(
            {
                "invoice_id": invoice_id,
                "issue_date": issue_date,
                "type_code": type_code,
                "seller": {
                    "name": seller_name,
                    "address": {
                        "street": seller_street,
                        "street_2": seller_street_2 or None,
                        "street_3": seller_street_3 or None,
                        "city": seller_city,
                        "postal_code": seller_postal_code,
                        "country_code": seller_country_code,
                        "country_subdivision": seller_country_subdivision or None,
                    },
                    "tax_id": seller_tax_id or None,
                    "tax_number": seller_tax_number or None,
                    "registration_id": seller_registration_id or None,
                    "electronic_address": seller_electronic_address or None,
                    "electronic_address_scheme": seller_electronic_address_scheme,
                    "trading_name": seller_trading_name or None,
                },
                "buyer": {
                    "name": buyer_name,
                    "address": {
                        "street": buyer_street,
                        "street_2": buyer_street_2 or None,
                        "street_3": buyer_street_3 or None,
                        "city": buyer_city,
                        "postal_code": buyer_postal_code,
                        "country_code": buyer_country_code,
                        "country_subdivision": buyer_country_subdivision or None,
                    },
                    "tax_id": buyer_tax_id or None,
                    "registration_id": buyer_registration_id or None,
                    "electronic_address": buyer_electronic_address or None,
                    "electronic_address_scheme": buyer_electronic_address_scheme,
                    "trading_name": buyer_trading_name or None,
                },
                "items": items_list,
                "allowances_charges": ac_list,
                "currency": currency,
                "payment_terms_days": payment_terms_days,
                "leitweg_id": leitweg_id or None,
                "buyer_reference": buyer_reference or None,
                "profile": invoice_profile,
                "seller_contact_name": seller_contact_name or None,
                "seller_contact_email": seller_contact_email or None,
                "seller_contact_phone": seller_contact_phone or None,
                "buyer_contact_name": buyer_contact_name or None,
                "buyer_contact_email": buyer_contact_email or None,
                "buyer_contact_phone": buyer_contact_phone or None,
                "seller_iban": seller_iban or None,
                "seller_bic": seller_bic or None,
                "seller_bank_name": seller_bank_name or None,
                "delivery_party_name": delivery_party_name or None,
                "delivery_street": delivery_street or None,
                "delivery_city": delivery_city or None,
                "delivery_postal_code": delivery_postal_code or None,
                "delivery_country_code": delivery_country_code or None,
                "delivery_date": delivery_date or None,
                "service_period_start": service_period_start or None,
                "service_period_end": service_period_end or None,
                "due_date": due_date or None,
                "invoice_note": invoice_note or None,
                "payment_terms_text": payment_terms_text or None,
                "purchase_order_reference": purchase_order_reference or None,
                "sales_order_reference": sales_order_reference or None,
                "contract_reference": contract_reference or None,
                "project_reference": project_reference or None,
                "preceding_invoice_number": preceding_invoice_number or None,
                "despatch_advice_reference": despatch_advice_reference or None,
                "invoiced_object_identifier": invoiced_object_identifier or None,
                "business_process_type": business_process_type or None,
                "buyer_iban": buyer_iban or None,
                "mandate_reference_id": mandate_reference_id or None,
                "skonto_percent": skonto_percent or None,
                "skonto_days": skonto_days,
                "skonto_base_amount": skonto_base_amount or None,
                "payment_means_type_code": payment_means_type_code,
                "remittance_information": remittance_information or None,
                "tax_exemption_reason": tax_exemption_reason or None,
                "tax_exemption_reason_code": tax_exemption_reason_code or None,
                "tender_or_lot_reference": tender_or_lot_reference or None,
                "payee_name": payee_name or None,
                "payee_id": payee_id or None,
                "payee_legal_registration_id": payee_legal_registration_id or None,
                "payment_card_pan": payment_card_pan or None,
                "payment_card_holder": payment_card_holder or None,
                "receiving_advice_reference": receiving_advice_reference or None,
                "delivery_location_id": delivery_location_id or None,
                "payment_means_text": payment_means_text or None,
                "supporting_documents": sd_list,
                **(
                    {
                        "seller_tax_representative": {
                            "name": seller_tax_rep_name,
                            "address": {
                                "street": seller_tax_rep_street,
                                "city": seller_tax_rep_city,
                                "postal_code": seller_tax_rep_postal_code,
                                "country_code": seller_tax_rep_country_code or "DE",
                            },
                            "tax_id": seller_tax_rep_tax_id or None,
                        }
                    }
                    if seller_tax_rep_name
                    else {}
                ),
            }
        )
    except PydanticValidationError as exc:
        return _format_pydantic_errors(exc)


# --- Tool 1: Validate XRechnung ---


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def einvoice_validate_xrechnung(xml_content: str, ctx: Context) -> str:
    """Validiert eine XRechnung (CII XML) gegen den KoSIT-Validator.

    Gibt Fehler, Warnungen und das erkannte Profil zurück.

    Args:
        xml_content: Der vollständige XRechnung-XML-Inhalt als String.
    """
    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await validate_xrechnung(xml_content, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Tool 2: Validate ZUGFeRD ---


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def einvoice_validate_zugferd(pdf_base64: str, ctx: Context) -> str:
    """Validiert eine ZUGFeRD-PDF, indem das eingebettete XML extrahiert und geprüft wird.

    Args:
        pdf_base64: Die ZUGFeRD-PDF als Base64-kodierter String.
    """
    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await validate_zugferd(pdf_base64, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Tool 3: Generate XRechnung ---


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def einvoice_generate_xrechnung(
    invoice_id: str,
    issue_date: str,
    seller_name: str,
    seller_street: str,
    seller_city: str,
    seller_postal_code: str,
    seller_country_code: str,
    seller_tax_id: str,
    buyer_name: str,
    buyer_street: str,
    buyer_city: str,
    buyer_postal_code: str,
    buyer_country_code: str,
    items: str,
    ctx: Context,
    seller_street_2: str = "",
    seller_street_3: str = "",
    seller_country_subdivision: str = "",
    buyer_street_2: str = "",
    buyer_street_3: str = "",
    buyer_country_subdivision: str = "",
    buyer_tax_id: str = "",
    currency: str = "EUR",
    payment_terms_days: int | None = None,
    leitweg_id: str = "",
    buyer_reference: str = "",
    profile: str = "XRECHNUNG",
    seller_electronic_address: str = "",
    seller_electronic_address_scheme: str = "EM",
    buyer_electronic_address: str = "",
    buyer_electronic_address_scheme: str = "EM",
    seller_contact_name: str = "",
    seller_contact_email: str = "",
    seller_contact_phone: str = "",
    buyer_contact_name: str = "",
    buyer_contact_email: str = "",
    buyer_contact_phone: str = "",
    seller_iban: str = "",
    seller_bic: str = "",
    seller_bank_name: str = "",
    type_code: str = "380",
    seller_tax_number: str = "",
    seller_registration_id: str = "",
    buyer_registration_id: str = "",
    delivery_party_name: str = "",
    delivery_street: str = "",
    delivery_city: str = "",
    delivery_postal_code: str = "",
    delivery_country_code: str = "",
    delivery_date: str = "",
    service_period_start: str = "",
    service_period_end: str = "",
    due_date: str = "",
    invoice_note: str = "",
    payment_terms_text: str = "",
    purchase_order_reference: str = "",
    sales_order_reference: str = "",
    contract_reference: str = "",
    project_reference: str = "",
    preceding_invoice_number: str = "",
    despatch_advice_reference: str = "",
    invoiced_object_identifier: str = "",
    business_process_type: str = "",
    buyer_iban: str = "",
    mandate_reference_id: str = "",
    skonto_percent: str = "",
    skonto_days: int | None = None,
    skonto_base_amount: str = "",
    payment_means_type_code: str = "58",
    remittance_information: str = "",
    allowances_charges: str = "",
    tax_exemption_reason: str = "",
    tax_exemption_reason_code: str = "",
    tender_or_lot_reference: str = "",
    seller_trading_name: str = "",
    buyer_trading_name: str = "",
    payee_name: str = "",
    payee_id: str = "",
    payee_legal_registration_id: str = "",
    payment_card_pan: str = "",
    payment_card_holder: str = "",
    seller_tax_rep_name: str = "",
    seller_tax_rep_street: str = "",
    seller_tax_rep_city: str = "",
    seller_tax_rep_postal_code: str = "",
    seller_tax_rep_country_code: str = "",
    seller_tax_rep_tax_id: str = "",
    receiving_advice_reference: str = "",
    delivery_location_id: str = "",
    payment_means_text: str = "",
    supporting_documents: str = "",
) -> str:
    """Erstellt eine XRechnung-konforme CII-XML-Rechnung.

    Die Rechnung wird automatisch gegen den KoSIT-Validator geprüft.

    Args:
        invoice_id: Rechnungsnummer (z.B. "RE-2026-001").
        issue_date: Rechnungsdatum im Format YYYY-MM-DD.
        seller_name: Name des Verkäufers / Rechnungsstellers.
        seller_street: Straße und Hausnummer des Verkäufers.
        seller_city: Stadt des Verkäufers.
        seller_postal_code: PLZ des Verkäufers.
        seller_country_code: Ländercode des Verkäufers (z.B. "DE").
        seller_tax_id: USt-IdNr. des Verkäufers (z.B. "DE123456789").
        buyer_name: Name des Käufers / Rechnungsempfängers.
        buyer_street: Straße und Hausnummer des Käufers.
        buyer_city: Stadt des Käufers.
        buyer_postal_code: PLZ des Käufers.
        buyer_country_code: Ländercode des Käufers (z.B. "DE").
        items: JSON-Array der Positionen.
        seller_street_2: Adresszeile 2 des Verkäufers (BT-36).
        seller_street_3: Adresszeile 3 des Verkäufers (BT-37).
        seller_country_subdivision: Bundesland Verkäufer (BT-39, z.B. 'BY').
        buyer_street_2: Adresszeile 2 des Käufers (BT-51).
        buyer_street_3: Adresszeile 3 des Käufers (BT-52).
        buyer_country_subdivision: Bundesland Käufer (BT-54, z.B. 'NW').
        buyer_tax_id: USt-IdNr. des Käufers (optional).
        currency: Währungscode (Standard: "EUR").
        payment_terms_days: Zahlungsziel in Tagen (optional).
        leitweg_id: Leitweg-ID (optional).
        buyer_reference: Käuferreferenz BT-10 (optional).
        profile: Rechnungsprofil.
        seller_electronic_address: Elektronische Adresse (BT-34).
        seller_electronic_address_scheme: EAS-Code (EM/9930).
        buyer_electronic_address: Elektronische Adresse (BT-49).
        buyer_electronic_address_scheme: EAS-Code (EM/9930).
        seller_contact_name: Ansprechpartner (BT-41).
        seller_contact_email: E-Mail (BT-43).
        seller_contact_phone: Telefon (BT-42).
        buyer_contact_name: Ansprechpartner Käufer (BT-44).
        buyer_contact_email: E-Mail Käufer (BT-47).
        buyer_contact_phone: Telefon Käufer (BT-46).
        seller_iban: IBAN (BT-84).
        seller_bic: BIC (BT-86).
        seller_bank_name: Bankname.
        type_code: Rechnungsart (BT-3): 380/381/384.
        seller_tax_number: Steuernummer (BT-32).
        delivery_party_name: Lieferort Name (BT-70).
        delivery_street: Lieferort Straße (BT-75).
        delivery_city: Lieferort Stadt (BT-77).
        delivery_postal_code: Lieferort PLZ (BT-78).
        delivery_country_code: Lieferort Land (BT-80).
        delivery_date: Lieferdatum (BT-71, YYYY-MM-DD).
        service_period_start: Leistungszeitraum Beginn (BT-73).
        service_period_end: Leistungszeitraum Ende (BT-74).
        due_date: Fälligkeitsdatum (BT-9, YYYY-MM-DD).
        invoice_note: Freitext-Bemerkung (BT-22).
        payment_terms_text: Zahlungsbedingungen (BT-20).
        purchase_order_reference: Bestellnummer (BT-13).
        sales_order_reference: Auftragsbestätigung (BT-14).
        contract_reference: Vertragsnummer (BT-12).
        project_reference: Projektreferenz (BT-11).
        preceding_invoice_number: Vorige Rechnungsnr. (BT-25).
        despatch_advice_reference: Lieferscheinnummer (BT-16).
        invoiced_object_identifier: Abrechnungsobjekt (BT-18).
        business_process_type: Geschäftsprozesstyp (BT-23).
        seller_registration_id: Handelsregister/GLN (BT-29).
        buyer_registration_id: GLN des Käufers (BT-46).
        buyer_iban: IBAN des Käufers (BT-91, SEPA-Lastschrift).
        mandate_reference_id: SEPA-Mandatsreferenz (BT-89).
        skonto_percent: Skonto-Prozentsatz (z.B. "2.00").
        skonto_days: Skonto-Frist in Tagen.
        skonto_base_amount: Skonto-Basisbetrag (optional).
        payment_means_type_code: Zahlungsart (BT-81, Standard 58).
        remittance_information: Verwendungszweck (BT-83).
        allowances_charges: JSON-Array der Zu-/Abschläge (BG-20/BG-21).
        tax_exemption_reason: Befreiungsgrund Text (BT-120).
        tax_exemption_reason_code: Befreiungsgrund Code (BT-121).
        tender_or_lot_reference: Vergabe-/Losnummer (BT-17).
        seller_trading_name: Handelsname Verkäufer (BT-28).
        buyer_trading_name: Handelsname Käufer (BT-45).
        payee_name: Zahlungsempfänger Name (BT-59).
        payee_id: Kennung des Zahlungsempfängers (BT-60).
        payee_legal_registration_id: Handelsregister Zahlungsempfänger (BT-61).
        payment_card_pan: Kartennummer letzte Stellen (BT-87).
        payment_card_holder: Karteninhaber (BT-88).
        seller_tax_rep_name: Steuervertreter Name (BT-62).
        seller_tax_rep_street: Steuervertreter Straße (BT-64).
        seller_tax_rep_city: Steuervertreter Stadt.
        seller_tax_rep_postal_code: Steuervertreter PLZ.
        seller_tax_rep_country_code: Steuervertreter Land.
        seller_tax_rep_tax_id: Steuervertreter USt-IdNr. (BT-63).
        receiving_advice_reference: Wareneingangsreferenz (BT-15).
        delivery_location_id: Lieferort-Kennung (BT-71).
        payment_means_text: Zahlungsart Freitext (BT-82).
        supporting_documents: JSON-Array Belegdokumente (BG-24).
    """
    data = _build_invoice_data(
        invoice_id=invoice_id,
        issue_date=issue_date,
        seller_name=seller_name,
        seller_street=seller_street,
        seller_street_2=seller_street_2,
        seller_street_3=seller_street_3,
        seller_country_subdivision=seller_country_subdivision,
        seller_city=seller_city,
        seller_postal_code=seller_postal_code,
        seller_country_code=seller_country_code,
        seller_tax_id=seller_tax_id,
        buyer_name=buyer_name,
        buyer_street=buyer_street,
        buyer_street_2=buyer_street_2,
        buyer_street_3=buyer_street_3,
        buyer_country_subdivision=buyer_country_subdivision,
        buyer_city=buyer_city,
        buyer_postal_code=buyer_postal_code,
        buyer_country_code=buyer_country_code,
        items_json=items,
        buyer_tax_id=buyer_tax_id,
        currency=currency,
        payment_terms_days=payment_terms_days,
        leitweg_id=leitweg_id,
        buyer_reference=buyer_reference,
        profile=profile,
        seller_electronic_address=seller_electronic_address,
        seller_electronic_address_scheme=seller_electronic_address_scheme,
        buyer_electronic_address=buyer_electronic_address,
        buyer_electronic_address_scheme=buyer_electronic_address_scheme,
        seller_contact_name=seller_contact_name,
        seller_contact_email=seller_contact_email,
        seller_contact_phone=seller_contact_phone,
        buyer_contact_name=buyer_contact_name,
        buyer_contact_email=buyer_contact_email,
        buyer_contact_phone=buyer_contact_phone,
        seller_iban=seller_iban,
        seller_bic=seller_bic,
        seller_bank_name=seller_bank_name,
        type_code=type_code,
        seller_tax_number=seller_tax_number,
        delivery_party_name=delivery_party_name,
        delivery_street=delivery_street,
        delivery_city=delivery_city,
        delivery_postal_code=delivery_postal_code,
        delivery_country_code=delivery_country_code,
        delivery_date=delivery_date,
        service_period_start=service_period_start,
        service_period_end=service_period_end,
        due_date=due_date,
        invoice_note=invoice_note,
        payment_terms_text=payment_terms_text,
        purchase_order_reference=purchase_order_reference,
        sales_order_reference=sales_order_reference,
        contract_reference=contract_reference,
        project_reference=project_reference,
        preceding_invoice_number=preceding_invoice_number,
        despatch_advice_reference=despatch_advice_reference,
        invoiced_object_identifier=invoiced_object_identifier,
        business_process_type=business_process_type,
        seller_registration_id=seller_registration_id,
        buyer_registration_id=buyer_registration_id,
        buyer_iban=buyer_iban,
        mandate_reference_id=mandate_reference_id,
        skonto_percent=skonto_percent,
        skonto_days=skonto_days,
        skonto_base_amount=skonto_base_amount,
        payment_means_type_code=payment_means_type_code,
        remittance_information=remittance_information,
        allowances_charges_json=allowances_charges,
        tax_exemption_reason=tax_exemption_reason,
        tax_exemption_reason_code=tax_exemption_reason_code,
        tender_or_lot_reference=tender_or_lot_reference,
        seller_trading_name=seller_trading_name,
        buyer_trading_name=buyer_trading_name,
        payee_name=payee_name,
        payee_id=payee_id,
        payee_legal_registration_id=payee_legal_registration_id,
        payment_card_pan=payment_card_pan,
        payment_card_holder=payment_card_holder,
        seller_tax_rep_name=seller_tax_rep_name,
        seller_tax_rep_street=seller_tax_rep_street,
        seller_tax_rep_city=seller_tax_rep_city,
        seller_tax_rep_postal_code=seller_tax_rep_postal_code,
        seller_tax_rep_country_code=seller_tax_rep_country_code,
        seller_tax_rep_tax_id=seller_tax_rep_tax_id,
        receiving_advice_reference=receiving_advice_reference,
        delivery_location_id=delivery_location_id,
        payment_means_text=payment_means_text,
        supporting_documents_json=supporting_documents,
    )

    if isinstance(data, str):
        return json.dumps({"success": False, "error": data}, ensure_ascii=False)

    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await generate_xrechnung(data, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Tool 4: Generate ZUGFeRD ---


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=False,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def einvoice_generate_zugferd(
    invoice_id: str,
    issue_date: str,
    seller_name: str,
    seller_street: str,
    seller_city: str,
    seller_postal_code: str,
    seller_country_code: str,
    seller_tax_id: str,
    buyer_name: str,
    buyer_street: str,
    buyer_city: str,
    buyer_postal_code: str,
    buyer_country_code: str,
    items: str,
    ctx: Context,
    seller_street_2: str = "",
    seller_street_3: str = "",
    seller_country_subdivision: str = "",
    buyer_street_2: str = "",
    buyer_street_3: str = "",
    buyer_country_subdivision: str = "",
    buyer_tax_id: str = "",
    currency: str = "EUR",
    payment_terms_days: int | None = None,
    leitweg_id: str = "",
    buyer_reference: str = "",
    profile: str = "ZUGFERD_EN16931",
    seller_electronic_address: str = "",
    seller_electronic_address_scheme: str = "EM",
    buyer_electronic_address: str = "",
    buyer_electronic_address_scheme: str = "EM",
    seller_contact_name: str = "",
    seller_contact_email: str = "",
    seller_contact_phone: str = "",
    buyer_contact_name: str = "",
    buyer_contact_email: str = "",
    buyer_contact_phone: str = "",
    seller_iban: str = "",
    seller_bic: str = "",
    seller_bank_name: str = "",
    type_code: str = "380",
    seller_tax_number: str = "",
    seller_registration_id: str = "",
    buyer_registration_id: str = "",
    delivery_party_name: str = "",
    delivery_street: str = "",
    delivery_city: str = "",
    delivery_postal_code: str = "",
    delivery_country_code: str = "",
    delivery_date: str = "",
    service_period_start: str = "",
    service_period_end: str = "",
    due_date: str = "",
    invoice_note: str = "",
    payment_terms_text: str = "",
    purchase_order_reference: str = "",
    sales_order_reference: str = "",
    contract_reference: str = "",
    project_reference: str = "",
    preceding_invoice_number: str = "",
    despatch_advice_reference: str = "",
    invoiced_object_identifier: str = "",
    business_process_type: str = "",
    buyer_iban: str = "",
    mandate_reference_id: str = "",
    skonto_percent: str = "",
    skonto_days: int | None = None,
    skonto_base_amount: str = "",
    payment_means_type_code: str = "58",
    remittance_information: str = "",
    allowances_charges: str = "",
    tax_exemption_reason: str = "",
    tax_exemption_reason_code: str = "",
    tender_or_lot_reference: str = "",
    seller_trading_name: str = "",
    buyer_trading_name: str = "",
    payee_name: str = "",
    payee_id: str = "",
    payee_legal_registration_id: str = "",
    payment_card_pan: str = "",
    payment_card_holder: str = "",
    seller_tax_rep_name: str = "",
    seller_tax_rep_street: str = "",
    seller_tax_rep_city: str = "",
    seller_tax_rep_postal_code: str = "",
    seller_tax_rep_country_code: str = "",
    seller_tax_rep_tax_id: str = "",
    receiving_advice_reference: str = "",
    delivery_location_id: str = "",
    payment_means_text: str = "",
    supporting_documents: str = "",
) -> str:
    """Erstellt eine ZUGFeRD-Hybrid-PDF (visuelle PDF + eingebettetes CII-XML).

    Args:
        invoice_id: Rechnungsnummer.
        issue_date: Rechnungsdatum (YYYY-MM-DD).
        seller_name: Name des Verkäufers.
        seller_street: Straße des Verkäufers.
        seller_city: Stadt des Verkäufers.
        seller_postal_code: PLZ des Verkäufers.
        seller_country_code: Land des Verkäufers.
        seller_tax_id: USt-IdNr. des Verkäufers.
        buyer_name: Name des Käufers.
        buyer_street: Straße des Käufers.
        buyer_city: Stadt des Käufers.
        buyer_postal_code: PLZ des Käufers.
        buyer_country_code: Land des Käufers.
        items: JSON-Array der Positionen.
        seller_street_2: Adresszeile 2 des Verkäufers (BT-36).
        seller_street_3: Adresszeile 3 des Verkäufers (BT-37).
        seller_country_subdivision: Bundesland Verkäufer (BT-39, z.B. 'BY').
        buyer_street_2: Adresszeile 2 des Käufers (BT-51).
        buyer_street_3: Adresszeile 3 des Käufers (BT-52).
        buyer_country_subdivision: Bundesland Käufer (BT-54, z.B. 'NW').
        buyer_tax_id: USt-IdNr. des Käufers (optional).
        currency: Währungscode (Standard: EUR).
        payment_terms_days: Zahlungsziel in Tagen (optional).
        leitweg_id: Leitweg-ID (optional).
        buyer_reference: Käuferreferenz BT-10 (optional).
        profile: Rechnungsprofil.
        seller_electronic_address: Elektronische Adresse (BT-34).
        seller_electronic_address_scheme: EAS-Code (EM/9930).
        buyer_electronic_address: Elektronische Adresse (BT-49).
        buyer_electronic_address_scheme: EAS-Code (EM/9930).
        seller_contact_name: Ansprechpartner (BT-41).
        seller_contact_email: E-Mail (BT-43).
        seller_contact_phone: Telefon (BT-42).
        buyer_contact_name: Ansprechpartner Käufer (BT-44).
        buyer_contact_email: E-Mail Käufer (BT-47).
        buyer_contact_phone: Telefon Käufer (BT-46).
        seller_iban: IBAN (BT-84).
        seller_bic: BIC (BT-86).
        seller_bank_name: Bankname.
        type_code: Rechnungsart (BT-3): 380/381/384.
        seller_tax_number: Steuernummer (BT-32).
        delivery_party_name: Lieferort Name (BT-70).
        delivery_street: Lieferort Straße (BT-75).
        delivery_city: Lieferort Stadt (BT-77).
        delivery_postal_code: Lieferort PLZ (BT-78).
        delivery_country_code: Lieferort Land (BT-80).
        delivery_date: Lieferdatum (BT-71).
        service_period_start: Leistungszeitraum Beginn (BT-73).
        service_period_end: Leistungszeitraum Ende (BT-74).
        due_date: Fälligkeitsdatum (BT-9, YYYY-MM-DD).
        invoice_note: Freitext-Bemerkung (BT-22).
        payment_terms_text: Zahlungsbedingungen (BT-20).
        purchase_order_reference: Bestellnummer (BT-13).
        sales_order_reference: Auftragsbestätigung (BT-14).
        contract_reference: Vertragsnummer (BT-12).
        project_reference: Projektreferenz (BT-11).
        preceding_invoice_number: Vorige Rechnungsnr. (BT-25).
        despatch_advice_reference: Lieferscheinnummer (BT-16).
        invoiced_object_identifier: Abrechnungsobjekt (BT-18).
        business_process_type: Geschäftsprozesstyp (BT-23).
        seller_registration_id: Handelsregister/GLN (BT-29).
        buyer_registration_id: GLN des Käufers (BT-46).
        buyer_iban: IBAN des Käufers (BT-91, SEPA-Lastschrift).
        mandate_reference_id: SEPA-Mandatsreferenz (BT-89).
        skonto_percent: Skonto-Prozentsatz (z.B. "2.00").
        skonto_days: Skonto-Frist in Tagen.
        skonto_base_amount: Skonto-Basisbetrag (optional).
        payment_means_type_code: Zahlungsart (BT-81, Standard 58).
        remittance_information: Verwendungszweck (BT-83).
        allowances_charges: JSON-Array der Zu-/Abschläge (BG-20/BG-21).
        tax_exemption_reason: Befreiungsgrund Text (BT-120).
        tax_exemption_reason_code: Befreiungsgrund Code (BT-121).
        tender_or_lot_reference: Vergabe-/Losnummer (BT-17).
        seller_trading_name: Handelsname Verkäufer (BT-28).
        buyer_trading_name: Handelsname Käufer (BT-45).
        payee_name: Zahlungsempfänger Name (BT-59).
        payee_id: Kennung des Zahlungsempfängers (BT-60).
        payee_legal_registration_id: Handelsregister (BT-61).
        payment_card_pan: Kartennummer letzte Stellen (BT-87).
        payment_card_holder: Karteninhaber (BT-88).
        seller_tax_rep_name: Steuervertreter Name (BT-62).
        seller_tax_rep_street: Steuervertreter Straße (BT-64).
        seller_tax_rep_city: Steuervertreter Stadt.
        seller_tax_rep_postal_code: Steuervertreter PLZ.
        seller_tax_rep_country_code: Steuervertreter Land.
        seller_tax_rep_tax_id: Steuervertreter USt-IdNr. (BT-63).
        receiving_advice_reference: Wareneingangsreferenz (BT-15).
        delivery_location_id: Lieferort-Kennung (BT-71).
        payment_means_text: Zahlungsart Freitext (BT-82).
        supporting_documents: JSON-Array Belegdokumente (BG-24).
    """
    data = _build_invoice_data(
        invoice_id=invoice_id,
        issue_date=issue_date,
        seller_name=seller_name,
        seller_street=seller_street,
        seller_street_2=seller_street_2,
        seller_street_3=seller_street_3,
        seller_country_subdivision=seller_country_subdivision,
        seller_city=seller_city,
        seller_postal_code=seller_postal_code,
        seller_country_code=seller_country_code,
        seller_tax_id=seller_tax_id,
        buyer_name=buyer_name,
        buyer_street=buyer_street,
        buyer_street_2=buyer_street_2,
        buyer_street_3=buyer_street_3,
        buyer_country_subdivision=buyer_country_subdivision,
        buyer_city=buyer_city,
        buyer_postal_code=buyer_postal_code,
        buyer_country_code=buyer_country_code,
        items_json=items,
        buyer_tax_id=buyer_tax_id,
        currency=currency,
        payment_terms_days=payment_terms_days,
        leitweg_id=leitweg_id,
        buyer_reference=buyer_reference,
        profile=profile,
        seller_electronic_address=seller_electronic_address,
        seller_electronic_address_scheme=seller_electronic_address_scheme,
        buyer_electronic_address=buyer_electronic_address,
        buyer_electronic_address_scheme=buyer_electronic_address_scheme,
        seller_contact_name=seller_contact_name,
        seller_contact_email=seller_contact_email,
        seller_contact_phone=seller_contact_phone,
        buyer_contact_name=buyer_contact_name,
        buyer_contact_email=buyer_contact_email,
        buyer_contact_phone=buyer_contact_phone,
        seller_iban=seller_iban,
        seller_bic=seller_bic,
        seller_bank_name=seller_bank_name,
        type_code=type_code,
        seller_tax_number=seller_tax_number,
        delivery_party_name=delivery_party_name,
        delivery_street=delivery_street,
        delivery_city=delivery_city,
        delivery_postal_code=delivery_postal_code,
        delivery_country_code=delivery_country_code,
        delivery_date=delivery_date,
        service_period_start=service_period_start,
        service_period_end=service_period_end,
        due_date=due_date,
        invoice_note=invoice_note,
        payment_terms_text=payment_terms_text,
        purchase_order_reference=purchase_order_reference,
        sales_order_reference=sales_order_reference,
        contract_reference=contract_reference,
        project_reference=project_reference,
        preceding_invoice_number=preceding_invoice_number,
        despatch_advice_reference=despatch_advice_reference,
        invoiced_object_identifier=invoiced_object_identifier,
        business_process_type=business_process_type,
        seller_registration_id=seller_registration_id,
        buyer_registration_id=buyer_registration_id,
        buyer_iban=buyer_iban,
        mandate_reference_id=mandate_reference_id,
        skonto_percent=skonto_percent,
        skonto_days=skonto_days,
        skonto_base_amount=skonto_base_amount,
        payment_means_type_code=payment_means_type_code,
        remittance_information=remittance_information,
        allowances_charges_json=allowances_charges,
        tax_exemption_reason=tax_exemption_reason,
        tax_exemption_reason_code=tax_exemption_reason_code,
        tender_or_lot_reference=tender_or_lot_reference,
        seller_trading_name=seller_trading_name,
        buyer_trading_name=buyer_trading_name,
        payee_name=payee_name,
        payee_id=payee_id,
        payee_legal_registration_id=payee_legal_registration_id,
        payment_card_pan=payment_card_pan,
        payment_card_holder=payment_card_holder,
        seller_tax_rep_name=seller_tax_rep_name,
        seller_tax_rep_street=seller_tax_rep_street,
        seller_tax_rep_city=seller_tax_rep_city,
        seller_tax_rep_postal_code=seller_tax_rep_postal_code,
        seller_tax_rep_country_code=seller_tax_rep_country_code,
        seller_tax_rep_tax_id=seller_tax_rep_tax_id,
        receiving_advice_reference=receiving_advice_reference,
        delivery_location_id=delivery_location_id,
        payment_means_text=payment_means_text,
        supporting_documents_json=supporting_documents,
    )

    if isinstance(data, str):
        return json.dumps({"success": False, "error": data}, ensure_ascii=False)

    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await generate_zugferd(data, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Tool 5: Parse E-Invoice ---


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=False,
    )
)
async def einvoice_parse(file_content: str, file_type: str = "xml") -> str:
    """Parst eine E-Rechnung (XML oder PDF) und gibt strukturierte Daten zurück.

    Args:
        file_content: XML-String oder Base64-kodierte PDF.
        file_type: Dateityp — "xml" oder "pdf".
    """
    result = await parse_einvoice(file_content, file_type)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Tool 6: Check Compliance ---


@mcp.tool(
    annotations=ToolAnnotations(
        readOnlyHint=True,
        destructiveHint=False,
        idempotentHint=True,
        openWorldHint=True,
    )
)
async def einvoice_check_compliance(
    xml_content: str,
    ctx: Context,
    target_profile: str = "XRECHNUNG",
) -> str:
    """Prüft die Konformität einer E-Rechnung gegen XRechnung oder ZUGFeRD.

    Kombiniert KoSIT-Validierung mit Pflichtfeldprüfung und gibt
    Verbesserungsvorschläge auf Deutsch zurück.

    Args:
        xml_content: Der CII-XML-Inhalt als String.
        target_profile: Zielprofil — "XRECHNUNG" oder "ZUGFERD".
    """
    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await check_compliance(xml_content, kosit, target_profile)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Entry point ---


def main() -> None:
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
