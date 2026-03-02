"""FastMCP server entry point for the e-invoice MCP."""

import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import Context, FastMCP
from mcp.types import ToolAnnotations

from einvoice_mcp.config import settings
from einvoice_mcp.prompts import (
    abschlagsrechnung_guide,
    b2b_pflicht_2027,
    bauleistungen_13b_guide,
    dauerrechnung_guide,
    differenzbesteuerung_25a_guide,
    drittlandlieferung_guide,
    gutschrift_erstellen,
    gutschriftverfahren_389_guide,
    handwerkerrechnung_35a,
    innergemeinschaftliche_deep_dive,
    innergemeinschaftliche_lieferung_guide,
    kleinunternehmer_guide,
    korrekturrechnung_erstellen,
    proforma_rechnung_guide,
    ratenzahlung_rechnung,
    rechnungsberichtigung_vs_storno,
    reiseleistungen_25_guide,
    reverse_charge_checkliste,
    reverse_charge_steuervertreter_combined,
    schlussrechnung_nach_abschlag,
    skonto_berechnung_guide,
    steuernummer_vs_ustidnr_guide,
    steuerprüfung_checkliste,
    stornobuchung_workflow,
    teilrechnung_workflow,
    typecode_entscheidungshilfe,
    xrechnung_schnellstart,
)
from einvoice_mcp.resources import (
    br_de_rules,
    business_process_identifiers,
    cpv_classification_codes,
    credit_note_reasons,
    e_rechnung_pflichten,
    example_line_items,
    leitweg_id_format,
    reference_currency_codes,
    reference_eas_codes,
    reference_payment_means_codes,
    reference_tax_categories,
    reference_type_codes,
    reference_unit_codes,
    reference_vatex_codes,
    schema_allowance_charge,
    schema_invoice_data,
    schema_item_attribute,
    schema_line_item,
    schema_supporting_document,
    sepa_mandate_type_codes,
    skr03_mapping,
    skr04_mapping,
    tax_category_decision_tree,
    uncl_5189_allowance_reason_codes,
    vat_exemption_reason_texts,
)
from einvoice_mcp.services.invoice_data_builder import build_invoice_data
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
    logger.info(
        "einvoice-mcp ready: 6 tools, %d resources, %d prompts",
        len(mcp._resource_manager._resources),
        len(mcp._prompt_manager._prompts),
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


# Resources — schemas, code tables, compliance
mcp.resource("einvoice://schemas/line-item")(schema_line_item)
mcp.resource("einvoice://schemas/allowance-charge")(schema_allowance_charge)
mcp.resource("einvoice://schemas/item-attribute")(schema_item_attribute)
mcp.resource("einvoice://schemas/supporting-document")(schema_supporting_document)
mcp.resource("einvoice://schemas/invoice-data")(schema_invoice_data)
mcp.resource("einvoice://reference/type-codes")(reference_type_codes)
mcp.resource("einvoice://reference/payment-means-codes")(reference_payment_means_codes)
mcp.resource("einvoice://reference/tax-categories")(reference_tax_categories)
mcp.resource("einvoice://reference/unit-codes")(reference_unit_codes)
mcp.resource("einvoice://reference/eas-codes")(reference_eas_codes)
mcp.resource("einvoice://reference/currency-codes")(reference_currency_codes)
mcp.resource("einvoice://examples/line-items")(example_line_items)
mcp.resource("einvoice://reference/e-rechnung-pflichten")(e_rechnung_pflichten)
mcp.resource("einvoice://reference/br-de-rules")(br_de_rules)
mcp.resource("einvoice://reference/skr03-mapping")(skr03_mapping)
mcp.resource("einvoice://reference/skr04-mapping")(skr04_mapping)
mcp.resource("einvoice://reference/vatex-codes")(reference_vatex_codes)
mcp.resource("einvoice://reference/credit-note-reasons")(credit_note_reasons)
mcp.resource("einvoice://reference/leitweg-id-format")(leitweg_id_format)
mcp.resource("einvoice://reference/tax-category-decision-tree")(
    tax_category_decision_tree,
)
mcp.resource("einvoice://reference/sepa-mandate-type-codes")(sepa_mandate_type_codes)
mcp.resource("einvoice://reference/cpv-classification-codes")(cpv_classification_codes)
mcp.resource("einvoice://reference/business-process-identifiers")(
    business_process_identifiers,
)
mcp.resource("einvoice://reference/vat-exemption-reason-texts")(
    vat_exemption_reason_texts,
)
mcp.resource("einvoice://reference/uncl-5189-allowance-reason-codes")(
    uncl_5189_allowance_reason_codes,
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


mcp.prompt()(steuerprüfung_checkliste)
mcp.prompt()(b2b_pflicht_2027)
mcp.prompt()(gutschrift_erstellen)
mcp.prompt()(reverse_charge_checkliste)
mcp.prompt()(xrechnung_schnellstart)
mcp.prompt()(korrekturrechnung_erstellen)
mcp.prompt()(abschlagsrechnung_guide)
mcp.prompt()(ratenzahlung_rechnung)
mcp.prompt()(handwerkerrechnung_35a)
mcp.prompt()(typecode_entscheidungshilfe)
mcp.prompt()(kleinunternehmer_guide)
mcp.prompt()(bauleistungen_13b_guide)
mcp.prompt()(differenzbesteuerung_25a_guide)
mcp.prompt()(stornobuchung_workflow)
mcp.prompt()(reiseleistungen_25_guide)
mcp.prompt()(innergemeinschaftliche_lieferung_guide)
mcp.prompt()(dauerrechnung_guide)
mcp.prompt()(steuernummer_vs_ustidnr_guide)
mcp.prompt()(schlussrechnung_nach_abschlag)
mcp.prompt()(proforma_rechnung_guide)
mcp.prompt()(drittlandlieferung_guide)
mcp.prompt()(gutschriftverfahren_389_guide)
mcp.prompt()(rechnungsberichtigung_vs_storno)
mcp.prompt()(reverse_charge_steuervertreter_combined)
mcp.prompt()(teilrechnung_workflow)
mcp.prompt()(innergemeinschaftliche_deep_dive)
mcp.prompt()(skonto_berechnung_guide)


def _collect_generate_params(local_vars: dict[str, Any]) -> dict[str, Any]:
    """Rename MCP tool param names to build_invoice_data kwarg names."""
    params = {k: v for k, v in local_vars.items() if k != "ctx"}
    params["items_json"] = params.pop("items")
    params["allowances_charges_json"] = params.pop("allowances_charges")
    params["supporting_documents_json"] = params.pop("supporting_documents")
    return params


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
    preceding_invoice_date: str = "",
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
    prepaid_amount: str = "",
    vat_point_date_code: str = "",
    seller_additional_legal_info: str = "",
    creditor_reference_id: str = "",
    buyer_accounting_reference: str = "",
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
        preceding_invoice_date: Datum der vorigen Rechnung (BT-26, YYYY-MM-DD).
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
        prepaid_amount: Bereits gezahlter Betrag (BT-113, z.B. Abschlagszahlungen).
        vat_point_date_code: Steuerzeitpunkt-Code (BT-8, UNTDID 2005).
            3=Rechnungsdatum, 35=Lieferdatum, 432=Zahlungsdatum.
        seller_additional_legal_info: Zusaetzliche rechtl. Info (BT-33).
        creditor_reference_id: Glaeubigeridentifikationsnr. (BT-90).
        buyer_accounting_reference: Kontierung Kaeufer (BT-19).
    """
    data = build_invoice_data(**_collect_generate_params(locals()))

    if isinstance(data, str):
        return json.dumps({"success": False, "error": data}, ensure_ascii=False)

    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await generate_xrechnung(data, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


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
    preceding_invoice_date: str = "",
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
    prepaid_amount: str = "",
    vat_point_date_code: str = "",
    seller_additional_legal_info: str = "",
    creditor_reference_id: str = "",
    buyer_accounting_reference: str = "",
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
        preceding_invoice_date: Datum der vorigen Rechnung (BT-26, YYYY-MM-DD).
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
        prepaid_amount: Bereits gezahlter Betrag (BT-113, z.B. Abschlagszahlungen).
        vat_point_date_code: Steuerzeitpunkt-Code (BT-8, UNTDID 2005).
            3=Rechnungsdatum, 35=Lieferdatum, 432=Zahlungsdatum.
        seller_additional_legal_info: Zusaetzliche rechtl. Info (BT-33).
        creditor_reference_id: Glaeubigeridentifikationsnr. (BT-90).
        buyer_accounting_reference: Kontierung Kaeufer (BT-19).
    """
    data = build_invoice_data(**_collect_generate_params(locals()))

    if isinstance(data, str):
        return json.dumps({"success": False, "error": data}, ensure_ascii=False)

    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await generate_zugferd(data, kosit)
    return json.dumps(result, ensure_ascii=False, indent=2)


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

    Unterstützt CII-XML (XRechnung) und ZUGFeRD/Factur-X PDFs.
    Gibt JSON mit allen extrahierten Feldern zurück:
    - Kopfdaten: invoice_id, issue_date, type_code, currency, profile
    - Parteien: seller, buyer (Name, Adresse, USt-IdNr., Kontakt)
    - Positionen: items[] mit Beschreibung, Menge, Preis, Steuersatz
    - Summen: totals (BT-106 net, BT-109 tax_basis, BT-112 gross, BT-113 prepaid)
    - Steuer: tax_breakdown[], tax_exemption_reason
    - Referenzen: purchase_order, contract, project, preceding_invoice
    - Zahlung: IBAN, BIC, payment_means, skonto
    - Lieferung: delivery_date, service_period, delivery_address

    Args:
        file_content: XML-String oder Base64-kodierte PDF.
        file_type: Dateityp — "xml" oder "pdf".
    """
    result = await parse_einvoice(file_content, file_type)
    return json.dumps(result, ensure_ascii=False, indent=2)


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

    Geprüfte Regeln:
    - EN 16931 Pflichtfelder (BT-1..BT-55)
    - BR-DE-1..BR-DE-26 (XRechnung-Geschäftsregeln)
    - BR-DE-8..BR-DE-13 (Datumsformat-Prüfung)
    - BR-DE-25 (Bruttobetrag >= 0)
    - Steuerkategorie-Regeln (Reverse Charge, ig. Lieferung, Export, §19)
    - SEPA-Prüfungen (IBAN, Mandatsreferenz, BIC)
    - EAS-Code-Validierung (BR-DE-16/21/22)
    - Leitweg-ID Format (XRechnung)

    Args:
        xml_content: Der CII-XML-Inhalt als String.
        target_profile: Zielprofil — "XRECHNUNG" oder "ZUGFERD".
    """
    kosit: KoSITClient = ctx.request_context.lifespan_context["kosit"]
    result = await check_compliance(xml_content, kosit, target_profile)
    return json.dumps(result, ensure_ascii=False, indent=2)


def main() -> None:
    """Run the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
