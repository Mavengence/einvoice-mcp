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
from einvoice_mcp.models import AllowanceCharge, InvoiceData, InvoiceProfile, LineItem
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.tools.compliance import check_compliance
from einvoice_mcp.tools.generate import generate_xrechnung, generate_zugferd
from einvoice_mcp.tools.parse import parse_einvoice
from einvoice_mcp.tools.validate import validate_xrechnung, validate_zugferd

logging.basicConfig(level=settings.log_level)
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


@mcp.resource("einvoice://schemas/invoice-data")
def schema_invoice_data() -> str:
    """Vollständiges JSON-Schema für InvoiceData.

    Zeigt alle verfügbaren Felder mit Typen, Beschreibungen und
    Validierungsregeln für die Rechnungserstellung.
    """
    return json.dumps(InvoiceData.model_json_schema(), ensure_ascii=False, indent=2)


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
    buyer_street_2: str = "",
    buyer_street_3: str = "",
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
    payment_means_type_code: str = "58",
    remittance_information: str = "",
    allowances_charges_json: str = "",
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
                    },
                    "tax_id": seller_tax_id or None,
                    "tax_number": seller_tax_number or None,
                    "electronic_address": seller_electronic_address or None,
                    "electronic_address_scheme": seller_electronic_address_scheme,
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
                    },
                    "tax_id": buyer_tax_id or None,
                    "electronic_address": buyer_electronic_address or None,
                    "electronic_address_scheme": buyer_electronic_address_scheme,
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
                "payment_means_type_code": payment_means_type_code,
                "remittance_information": remittance_information or None,
            }
        )
    except PydanticValidationError as exc:
        errors = "; ".join(e["msg"] for e in exc.errors()[:3])
        return f"Fehler: Ungültige Rechnungsdaten — {errors}"


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
    buyer_street_2: str = "",
    buyer_street_3: str = "",
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
    payment_means_type_code: str = "58",
    remittance_information: str = "",
    allowances_charges: str = "",
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
        buyer_street_2: Adresszeile 2 des Käufers (BT-51).
        buyer_street_3: Adresszeile 3 des Käufers (BT-52).
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
        payment_means_type_code: Zahlungsart (BT-81, Standard 58).
        remittance_information: Verwendungszweck (BT-83).
        allowances_charges: JSON-Array der Zu-/Abschläge (BG-20/BG-21).
    """
    data = _build_invoice_data(
        invoice_id=invoice_id,
        issue_date=issue_date,
        seller_name=seller_name,
        seller_street=seller_street,
        seller_street_2=seller_street_2,
        seller_street_3=seller_street_3,
        seller_city=seller_city,
        seller_postal_code=seller_postal_code,
        seller_country_code=seller_country_code,
        seller_tax_id=seller_tax_id,
        buyer_name=buyer_name,
        buyer_street=buyer_street,
        buyer_street_2=buyer_street_2,
        buyer_street_3=buyer_street_3,
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
        payment_means_type_code=payment_means_type_code,
        remittance_information=remittance_information,
        allowances_charges_json=allowances_charges,
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
    buyer_street_2: str = "",
    buyer_street_3: str = "",
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
    payment_means_type_code: str = "58",
    remittance_information: str = "",
    allowances_charges: str = "",
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
        buyer_street_2: Adresszeile 2 des Käufers (BT-51).
        buyer_street_3: Adresszeile 3 des Käufers (BT-52).
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
        payment_means_type_code: Zahlungsart (BT-81, Standard 58).
        remittance_information: Verwendungszweck (BT-83).
        allowances_charges: JSON-Array der Zu-/Abschläge (BG-20/BG-21).
    """
    data = _build_invoice_data(
        invoice_id=invoice_id,
        issue_date=issue_date,
        seller_name=seller_name,
        seller_street=seller_street,
        seller_street_2=seller_street_2,
        seller_street_3=seller_street_3,
        seller_city=seller_city,
        seller_postal_code=seller_postal_code,
        seller_country_code=seller_country_code,
        seller_tax_id=seller_tax_id,
        buyer_name=buyer_name,
        buyer_street=buyer_street,
        buyer_street_2=buyer_street_2,
        buyer_street_3=buyer_street_3,
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
        payment_means_type_code=payment_means_type_code,
        remittance_information=remittance_information,
        allowances_charges_json=allowances_charges,
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
