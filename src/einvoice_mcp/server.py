"""FastMCP server entry point for the e-invoice MCP."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import Context, FastMCP

from einvoice_mcp.config import settings
from einvoice_mcp.models import InvoiceData, InvoiceProfile
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
async def app_lifespan(server: FastMCP) -> AsyncIterator[dict]:
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
    buyer_tax_id: str = "",
    currency: str = "EUR",
    payment_terms_days: int | None = None,
    leitweg_id: str = "",
    buyer_reference: str = "",
    profile: str = "XRECHNUNG",
) -> InvoiceData | str:
    """Build InvoiceData from flat MCP tool parameters.

    Returns InvoiceData on success, or a German error string on failure.
    """
    try:
        items_list = json.loads(items_json)
    except json.JSONDecodeError:
        return "Fehler: 'items' muss ein gültiges JSON-Array sein."

    try:
        invoice_profile = InvoiceProfile(profile)
    except ValueError:
        return f"Fehler: Ungültiges Profil. Erlaubt: {_VALID_PROFILES}."

    return InvoiceData(
        invoice_id=invoice_id,
        issue_date=issue_date,
        seller={
            "name": seller_name,
            "address": {
                "street": seller_street,
                "city": seller_city,
                "postal_code": seller_postal_code,
                "country_code": seller_country_code,
            },
            "tax_id": seller_tax_id or None,
        },
        buyer={
            "name": buyer_name,
            "address": {
                "street": buyer_street,
                "city": buyer_city,
                "postal_code": buyer_postal_code,
                "country_code": buyer_country_code,
            },
            "tax_id": buyer_tax_id or None,
        },
        items=items_list,
        currency=currency,
        payment_terms_days=payment_terms_days,
        leitweg_id=leitweg_id or None,
        buyer_reference=buyer_reference or None,
        profile=invoice_profile,
    )


# --- Tool 1: Validate XRechnung ---


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
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
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
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
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
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
    buyer_tax_id: str = "",
    currency: str = "EUR",
    payment_terms_days: int | None = None,
    leitweg_id: str = "",
    buyer_reference: str = "",
    profile: str = "XRECHNUNG",
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
        items: JSON-Array der Positionen. Felder pro Position:
            description (str), quantity (number), unit_price (number),
            tax_rate (number), unit_code (str, optional),
            tax_category (str, optional).
        buyer_tax_id: USt-IdNr. des Käufers (optional).
        currency: Währungscode (Standard: "EUR").
        payment_terms_days: Zahlungsziel in Tagen (optional).
        leitweg_id: Leitweg-ID für öffentliche Auftraggeber (optional).
        buyer_reference: Käuferreferenz / Bestellnummer BT-10 (optional).
        profile: Rechnungsprofil — XRECHNUNG, ZUGFERD_EN16931, ZUGFERD_BASIC, ZUGFERD_EXTENDED.
    """
    data = _build_invoice_data(
        invoice_id=invoice_id,
        issue_date=issue_date,
        seller_name=seller_name,
        seller_street=seller_street,
        seller_city=seller_city,
        seller_postal_code=seller_postal_code,
        seller_country_code=seller_country_code,
        seller_tax_id=seller_tax_id,
        buyer_name=buyer_name,
        buyer_street=buyer_street,
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
    )

    if isinstance(data, str):
        return json.dumps({"success": False, "error": data}, ensure_ascii=False)

    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await generate_xrechnung(data, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Tool 4: Generate ZUGFeRD ---


@mcp.tool(
    annotations={
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
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
    buyer_tax_id: str = "",
    currency: str = "EUR",
    payment_terms_days: int | None = None,
    leitweg_id: str = "",
    buyer_reference: str = "",
    profile: str = "ZUGFERD_EN16931",
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
        items: JSON-Array der Positionen (wie bei generate_xrechnung).
        buyer_tax_id: USt-IdNr. des Käufers (optional).
        currency: Währungscode (Standard: EUR).
        payment_terms_days: Zahlungsziel in Tagen (optional).
        leitweg_id: Leitweg-ID (optional).
        buyer_reference: Käuferreferenz BT-10 (optional).
        profile: Profil — ZUGFERD_EN16931, ZUGFERD_BASIC, ZUGFERD_EXTENDED, XRECHNUNG.
    """
    data = _build_invoice_data(
        invoice_id=invoice_id,
        issue_date=issue_date,
        seller_name=seller_name,
        seller_street=seller_street,
        seller_city=seller_city,
        seller_postal_code=seller_postal_code,
        seller_country_code=seller_country_code,
        seller_tax_id=seller_tax_id,
        buyer_name=buyer_name,
        buyer_street=buyer_street,
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
    )

    if isinstance(data, str):
        return json.dumps({"success": False, "error": data}, ensure_ascii=False)

    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await generate_zugferd(data, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


# --- Tool 5: Parse E-Invoice ---


@mcp.tool(
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }
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
    annotations={
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    }
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
