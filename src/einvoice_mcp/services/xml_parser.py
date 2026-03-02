"""Parse CII XML and extract from ZUGFeRD PDFs."""

import logging
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden
from drafthorse.models.document import Document

from einvoice_mcp.errors import InvoiceParsingError
from einvoice_mcp.models import (
    ParsedAllowanceCharge,
    ParsedInvoice,
    SupportingDocument,
    TaxBreakdown,
    Totals,
)
from einvoice_mcp.services.cii_extractors import (
    extract_items,
    extract_party,
    safe_decimal,
    str_element,
)

logger = logging.getLogger(__name__)


_UBL_NAMESPACES = frozenset(
    {
        "urn:oasis:names:specification:ubl:schema:xsd:Invoice-2",
        "urn:oasis:names:specification:ubl:schema:xsd:CreditNote-2",
    }
)


def parse_xml(xml_bytes: bytes) -> ParsedInvoice:
    """Parse CII XML bytes into a ParsedInvoice.

    Pre-screens with defusedxml to block XXE/DTD attacks before
    passing to drafthorse (which uses lxml without entity protection).
    Detects UBL format and returns a clear error — only CII is supported.
    """
    # Pre-screen for XXE, DTD, and entity expansion attacks
    try:
        root = ElementTree.fromstring(xml_bytes)
    except (EntitiesForbidden, DTDForbidden, ExternalReferenceForbidden) as exc:
        raise InvoiceParsingError() from exc
    except ElementTree.ParseError as exc:
        raise InvoiceParsingError() from exc

    # Detect UBL format — this server only supports CII (Cross Industry Invoice)
    ns = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
    if ns in _UBL_NAMESPACES:
        raise InvoiceParsingError(
            "UBL-Format erkannt. Dieses Tool unterstützt nur CII "
            "(Cross Industry Invoice / ZUGFeRD / XRechnung CII). "
            "UBL-Rechnungen können mit dem EN 16931 XSLT-Converter "
            "(https://github.com/ConnectingEurope/eInvoicing-EN16931) "
            "oder Saxon nach CII konvertiert werden.",
            controlled=True,
        )

    try:
        doc = Document.parse(xml_bytes)
        return _extract_invoice(doc)
    except InvoiceParsingError:
        raise
    except Exception as exc:
        logger.warning("XML parsing error: %s", exc, exc_info=True)
        raise InvoiceParsingError() from exc


def extract_xml_from_pdf(pdf_bytes: bytes) -> bytes:
    """Extract embedded XML from a ZUGFeRD/Factur-X PDF."""
    try:
        from facturx import get_xml_from_pdf

        _filename, xml_bytes = get_xml_from_pdf(pdf_bytes, check_xsd=False)
        return bytes(xml_bytes)
    except ImportError as exc:
        raise InvoiceParsingError("factur-x library not installed") from exc
    except Exception as exc:
        logger.warning("PDF XML extraction failed: %s", exc, exc_info=True)
        raise InvoiceParsingError() from exc


def _extract_invoice(doc: Document) -> ParsedInvoice:
    seller = extract_party(doc.trade.agreement.seller)
    buyer = extract_party(doc.trade.agreement.buyer)
    items = extract_items(doc)
    tax_breakdown = _extract_tax_breakdown(doc)
    totals = _extract_totals(doc)

    issue_date = ""
    if doc.header.issue_date_time:
        issue_date = str(doc.header.issue_date_time)

    profile = str_element(doc.context.guideline_parameter.id)

    # Buyer reference / Leitweg-ID (BT-10)
    buyer_reference = ""
    try:
        br_val = str_element(getattr(doc.trade.agreement, "buyer_reference", ""))
        if br_val:
            buyer_reference = br_val
    except Exception:
        logger.debug("Failed to extract buyer reference (BT-10)", exc_info=True)

    # Delivery location (BT-70..BT-80)
    delivery_party_name = ""
    delivery_street = ""
    delivery_city = ""
    delivery_postal_code = ""
    delivery_country_code = ""
    try:
        ship_to = doc.trade.delivery.ship_to
        dn = str_element(getattr(ship_to, "name", ""))
        if dn:
            delivery_party_name = dn
        addr = getattr(ship_to, "address", None)
        if addr:
            ds = str_element(getattr(addr, "line_one", ""))
            if ds:
                delivery_street = ds
            dc = str_element(getattr(addr, "city_name", ""))
            if dc:
                delivery_city = dc
            dp = str_element(getattr(addr, "postcode", ""))
            if dp:
                delivery_postal_code = dp
            dcc = str_element(getattr(addr, "country_id", ""))
            if dcc:
                delivery_country_code = dcc
    except Exception:
        logger.debug("Failed to extract delivery location (BT-70..BT-80)", exc_info=True)

    # Delivery date (BT-71) — §14 Abs. 4 Nr. 6 UStG
    delivery_date = ""
    try:
        event = doc.trade.delivery.event
        occurrence = getattr(event, "occurrence", None)
        if occurrence:
            val = str(occurrence).strip()
            if val and val != "None":
                delivery_date = val
    except Exception:
        logger.debug("Failed to extract delivery date (BT-72)", exc_info=True)

    # Service period (BT-73/BT-74)
    service_period_start = ""
    service_period_end = ""
    try:
        period = doc.trade.settlement.period
        period_start = getattr(period, "start", None)
        if period_start:
            val = str(period_start).strip()
            if val and val != "None":
                service_period_start = val
        period_end = getattr(period, "end", None)
        if period_end:
            val = str(period_end).strip()
            if val and val != "None":
                service_period_end = val
    except Exception:
        logger.debug("Failed to extract service period (BT-73/BT-74)", exc_info=True)

    # Invoice notes (BG-1, BT-22) — collect all
    invoice_note = ""
    invoice_notes: list[str] = []
    try:
        notes = getattr(doc.header, "notes", None)
        if notes and hasattr(notes, "children"):
            for note in notes.children:
                content = getattr(note, "content", None)
                text = str_element(content) if content else str_element(note)
                if text:
                    invoice_notes.append(text)
        if invoice_notes:
            invoice_note = invoice_notes[0]
    except Exception:
        logger.debug("Failed to extract invoice notes (BT-22)", exc_info=True)

    # Payment terms (BT-20) and due date (BT-9) and Skonto
    payment_terms = ""
    due_date = ""
    skonto_percent = ""
    skonto_days = ""
    try:
        terms = doc.trade.settlement.terms
        if hasattr(terms, "children"):
            for term in terms.children:
                desc = str_element(getattr(term, "description", ""))
                if desc:
                    payment_terms = desc
                due_obj = getattr(term, "due", None)
                if due_obj:
                    due_val = str(due_obj).strip()
                    if due_val and due_val != "None":
                        due_date = due_val
                # Skonto (PaymentDiscountTerms)
                dt = getattr(term, "discount_terms", None)
                if dt:
                    pct = safe_decimal(getattr(dt, "calculation_percent", "0"))
                    if pct > 0:
                        skonto_percent = str(pct)
                    bpm = getattr(dt, "basis_period_measure", None)
                    if bpm:
                        bpm_str = str_element(bpm)
                        if bpm_str:
                            skonto_days = bpm_str
                if payment_terms or due_date:
                    break
    except Exception:
        logger.debug("Failed to extract payment terms (BT-20)", exc_info=True)

    # Purchase order reference (BT-13)
    purchase_order_reference = ""
    try:
        po_id = doc.trade.agreement.buyer_order.issuer_assigned_id
        val = str_element(po_id)
        if val:
            purchase_order_reference = val
    except Exception:
        logger.debug("Failed to extract purchase order reference (BT-13)", exc_info=True)

    # Sales order reference (BT-14)
    sales_order_reference = ""
    try:
        so_id = doc.trade.agreement.seller_order.issuer_assigned_id
        val = str_element(so_id)
        if val:
            sales_order_reference = val
    except Exception:
        logger.debug("Failed to extract sales order reference (BT-14)", exc_info=True)

    # Contract reference (BT-12)
    contract_reference = ""
    try:
        ct_id = doc.trade.agreement.contract.issuer_assigned_id
        val = str_element(ct_id)
        if val:
            contract_reference = val
    except Exception:
        logger.debug("Failed to extract contract reference (BT-12)", exc_info=True)

    # Project reference (BT-11)
    project_reference = ""
    try:
        pr_id = doc.trade.agreement.procuring_project_type.id
        val = str_element(pr_id)
        if val:
            project_reference = val
    except Exception:
        logger.debug("Failed to extract project reference (BT-11)", exc_info=True)

    # Despatch advice reference (BT-16)
    despatch_advice_reference = ""
    try:
        da_id = doc.trade.delivery.despatch_advice.issuer_assigned_id
        val = str_element(da_id)
        if val:
            despatch_advice_reference = val
    except Exception:
        logger.debug("Failed to extract despatch advice reference (BT-16)", exc_info=True)

    # Receiving advice reference (BT-15)
    receiving_advice_reference = ""
    try:
        ra_id = doc.trade.delivery.receiving_advice.issuer_assigned_id
        val = str_element(ra_id)
        if val:
            receiving_advice_reference = val
    except Exception:
        logger.debug("Failed to extract receiving advice reference (BT-15)", exc_info=True)

    # Delivery location identifier (BT-71)
    delivery_location_id = ""
    try:
        loc_id = doc.trade.delivery.ship_to.id
        val = str_element(loc_id)
        if val:
            delivery_location_id = val
    except Exception:
        logger.debug("Failed to extract delivery location ID", exc_info=True)

    # Payment means type code (BT-81) and text (BT-82)
    payment_means_type_code = ""
    payment_means_text = ""
    try:
        pm_container = doc.trade.settlement.payment_means
        if hasattr(pm_container, "children"):
            for pm in pm_container.children:
                # BT-81: type code (e.g. "58" for SEPA)
                tc = str_element(getattr(pm, "type_code", ""))
                if tc and not payment_means_type_code:
                    payment_means_type_code = tc
                # BT-82: information text
                info_container = getattr(pm, "information", None)
                if info_container and hasattr(info_container, "children"):
                    for info_val in info_container.children:
                        text = str(info_val).strip() if info_val else ""
                        if text:
                            payment_means_text = text
                            break
                if payment_means_text:
                    break
    except Exception:
        logger.debug("Failed to extract payment means (BT-81/BT-82)", exc_info=True)

    # Tender/lot reference (BT-17) and Invoiced object identifier (BT-18)
    # Both stored as AdditionalReferencedDocument — TypeCode=50 for BT-17, 130 for BT-18
    tender_or_lot_reference = ""
    invoiced_object_identifier = ""
    try:
        add_refs = doc.trade.agreement.additional_references
        if hasattr(add_refs, "children"):
            for ref in add_refs.children:
                tc = str_element(getattr(ref, "type_code", ""))
                ref_id = str_element(getattr(ref, "issuer_assigned_id", ""))
                if tc == "50" and ref_id and not tender_or_lot_reference:
                    tender_or_lot_reference = ref_id
                elif tc == "130" and ref_id and not invoiced_object_identifier:
                    invoiced_object_identifier = ref_id
    except Exception:
        logger.debug("Failed to extract tender/lot reference (BT-17/BT-18)", exc_info=True)

    # Supporting documents (BG-24, BT-122..BT-125) — TypeCode=916
    supporting_documents: list[SupportingDocument] = []
    try:
        add_refs = doc.trade.agreement.additional_references
        if hasattr(add_refs, "children"):
            for ref in add_refs.children:
                tc = str_element(getattr(ref, "type_code", ""))
                if tc == "916":
                    ref_id = str_element(getattr(ref, "issuer_assigned_id", ""))
                    if ref_id:
                        desc = str_element(getattr(ref, "name", ""))
                        uri = str_element(getattr(ref, "uri_id", "")) or None
                        content_b64 = None
                        mime = "application/pdf"
                        fname = ""
                        ao = getattr(ref, "attached_object", None)
                        if ao:
                            txt = getattr(ao, "_text", None)
                            if txt:
                                content_b64 = str(txt)
                            mc = getattr(ao, "_mime_code", "")
                            if mc:
                                mime = str(mc)
                            fn = getattr(ao, "_filename", "")
                            if fn:
                                fname = str(fn)
                        supporting_documents.append(
                            SupportingDocument(
                                id=ref_id,
                                description=desc,
                                uri=uri,
                                mime_type=mime,
                                filename=fname,
                                content_base64=content_b64,
                            )
                        )
    except Exception:
        logger.debug("Failed to extract supporting documents (BG-24)", exc_info=True)

    # Seller tax representative (BG-11, BT-62..BT-65)
    seller_tax_representative = None
    try:
        rep_party = doc.trade.agreement.seller_tax_representative_party
        rep_name = str_element(getattr(rep_party, "name", ""))
        if rep_name:
            seller_tax_representative = extract_party(rep_party)
    except Exception:
        logger.debug("Failed to extract seller tax representative (BG-11)", exc_info=True)

    # Seller additional legal information (BT-33)
    seller_additional_legal_info = ""
    try:
        desc = str_element(getattr(doc.trade.agreement.seller, "description", ""))
        if desc:
            seller_additional_legal_info = desc
    except Exception:
        logger.debug("Failed to extract seller legal info (BT-33)", exc_info=True)

    # Creditor reference ID (BT-90)
    creditor_reference_id = ""
    try:
        cri = str_element(getattr(doc.trade.settlement, "creditor_reference_id", ""))
        if cri:
            creditor_reference_id = cri
    except Exception:
        logger.debug("Failed to extract creditor reference (BT-90)", exc_info=True)

    # Buyer accounting reference (BT-19) — document level
    buyer_accounting_reference = ""
    try:
        acct = getattr(doc.trade.settlement, "accounting_account", None)
        if acct:
            acct_id = str_element(getattr(acct, "id", ""))
            if acct_id:
                buyer_accounting_reference = acct_id
    except Exception:
        logger.debug("Failed to extract buyer accounting ref (BT-19)", exc_info=True)

    # Business process type (BT-23)
    business_process_type = ""
    try:
        bp_id = doc.context.business_parameter.id
        val = str_element(bp_id)
        if val:
            business_process_type = val
    except Exception:
        logger.debug("Failed to extract business process type (BT-23)", exc_info=True)

    # VAT exemption reason (BT-120/BT-121) and VAT point date code (BT-8)
    tax_exemption_reason = ""
    tax_exemption_reason_code = ""
    vat_point_date_code = ""
    try:
        trade_tax_container = doc.trade.settlement.trade_tax
        if hasattr(trade_tax_container, "children"):
            for tax_entry in trade_tax_container.children:
                er = str_element(getattr(tax_entry, "exemption_reason", ""))
                erc = str_element(getattr(tax_entry, "exemption_reason_code", ""))
                if er:
                    tax_exemption_reason = er
                if erc:
                    tax_exemption_reason_code = erc
                # BT-8: DueDateTypeCode (UNTDID 2005)
                ddc = str_element(getattr(tax_entry, "due_date_type_code", ""))
                if ddc and not vat_point_date_code:
                    vat_point_date_code = ddc
                if tax_exemption_reason or tax_exemption_reason_code:
                    break
    except Exception:
        logger.debug("Failed to extract VAT exemption reason (BT-120/BT-121)", exc_info=True)

    # Preceding invoice number (BT-25) and date (BT-26)
    preceding_invoice_number = ""
    preceding_invoice_date = ""
    try:
        inv_ref = doc.trade.settlement.invoice_referenced_document
        prec_ref_id: object = getattr(inv_ref, "issuer_assigned_id", None)
        if prec_ref_id:
            val = str_element(prec_ref_id)
            if val:
                preceding_invoice_number = val
        prec_ref_dt: object = getattr(inv_ref, "issue_date_time", None)
        if prec_ref_dt is not None:
            dt_val = str_element(prec_ref_dt)
            if dt_val and dt_val != "None":
                preceding_invoice_date = dt_val
    except Exception:
        logger.debug("Failed to extract preceding invoice (BT-25/BT-26)", exc_info=True)

    # Remittance information (BT-83) / Verwendungszweck
    remittance_information = ""
    try:
        pay_ref = doc.trade.settlement.payment_reference
        val = str_element(pay_ref)
        if val:
            remittance_information = val
    except Exception:
        logger.debug("Failed to extract remittance information (BT-83)", exc_info=True)

    # Document-level allowances/charges (BG-20/BG-21)
    allowances_charges: list[ParsedAllowanceCharge] = []
    try:
        ac_container = doc.trade.settlement.allowance_charge
        if hasattr(ac_container, "children"):
            for ac_item in ac_container.children:
                indicator = getattr(ac_item, "indicator", None)
                # drafthorse IndicatorElement wraps the bool in ._value
                indicator_value = getattr(indicator, "_value", None)
                if indicator_value is not None:
                    is_charge = bool(indicator_value)
                else:
                    is_charge = bool(indicator) if indicator is not None else False
                amount = safe_decimal(getattr(ac_item, "actual_amount", "0"))
                reason = str_element(getattr(ac_item, "reason", ""))
                ac_tax_rate = Decimal("0")
                ac_tax_cat = "S"
                tax_container = getattr(ac_item, "trade_tax", None)
                if tax_container and hasattr(tax_container, "children"):
                    for tax_child in tax_container.children:
                        rate_val = safe_decimal(getattr(tax_child, "rate_applicable_percent", "0"))
                        cat_val = str_element(getattr(tax_child, "category_code", "S")) or "S"
                        ac_tax_rate = rate_val
                        ac_tax_cat = cat_val
                        break
                allowances_charges.append(
                    ParsedAllowanceCharge(
                        charge=is_charge,
                        amount=amount,
                        reason=reason,
                        tax_rate=ac_tax_rate,
                        tax_category=ac_tax_cat,
                    )
                )
    except Exception:
        logger.debug("Failed to extract allowances/charges (BG-20/BG-21)", exc_info=True)

    # Payment card (BT-87/BT-88)
    payment_card_pan = ""
    payment_card_holder = ""
    try:
        pm_container = doc.trade.settlement.payment_means
        if hasattr(pm_container, "children"):
            for pm in pm_container.children:
                fc = getattr(pm, "financial_card", None)
                if fc:
                    card_id = str_element(getattr(fc, "id", ""))
                    if card_id:
                        payment_card_pan = card_id
                    ch = str_element(getattr(fc, "cardholder_name", ""))
                    if ch:
                        payment_card_holder = ch
                if payment_card_pan:
                    break
    except Exception:
        logger.debug("Failed to extract payment card (BT-87/BT-88)", exc_info=True)

    # Payee party (BG-10, BT-59..BT-61)
    payee_name = ""
    payee_id = ""
    payee_legal_registration_id = ""
    try:
        payee_obj = doc.trade.settlement.payee
        pn = str_element(getattr(payee_obj, "name", ""))
        if pn:
            payee_name = pn
            # Global ID (BT-60)
            gid_container = getattr(payee_obj, "global_id", None)
            if gid_container and hasattr(gid_container, "children"):
                for gid_entry in gid_container.children:
                    if isinstance(gid_entry, tuple) and len(gid_entry) == 2:
                        payee_id = str(gid_entry[1]).strip()
                        break
            # Legal organization ID (BT-61)
            legal_org = getattr(payee_obj, "legal_organization", None)
            if legal_org:
                lo_id = str_element(getattr(legal_org, "id", ""))
                if lo_id:
                    payee_legal_registration_id = lo_id
    except Exception:
        logger.debug("Failed to extract payee party (BG-10)", exc_info=True)

    # IBAN / BIC / Bank name (BT-84, BT-86) and buyer IBAN (BT-91)
    seller_iban = ""
    seller_bic = ""
    seller_bank_name = ""
    buyer_iban = ""
    try:
        pm_container = doc.trade.settlement.payment_means
        if hasattr(pm_container, "children"):
            for pm in pm_container.children:
                acct = getattr(pm, "payee_account", None)
                if acct:
                    iban_val = str_element(getattr(acct, "iban", ""))
                    if iban_val:
                        seller_iban = iban_val
                    bank_name = str_element(getattr(acct, "account_name", ""))
                    if bank_name:
                        seller_bank_name = bank_name
                inst = getattr(pm, "payee_institution", None)
                if inst:
                    bic_val = str_element(getattr(inst, "bic", ""))
                    if bic_val:
                        seller_bic = bic_val
                # Buyer/payer IBAN (BT-91) for SEPA direct debit
                payer = getattr(pm, "payer_account", None)
                if payer:
                    payer_iban = str_element(getattr(payer, "iban", ""))
                    if payer_iban:
                        buyer_iban = payer_iban
                if seller_iban:
                    break
    except Exception:
        logger.debug("Failed to extract IBAN/BIC/bank (BT-84/BT-86)", exc_info=True)

    # SEPA mandate reference (BT-89)
    mandate_reference_id = ""
    try:
        terms = doc.trade.settlement.terms
        if hasattr(terms, "children"):
            for term in terms.children:
                mid = str_element(getattr(term, "debit_mandate_id", ""))
                if mid:
                    mandate_reference_id = mid
                    break
    except Exception:
        logger.debug("Failed to extract SEPA mandate reference (BT-89)", exc_info=True)

    return ParsedInvoice(
        invoice_id=str_element(doc.header.id),
        type_code=str_element(doc.header.type_code) or "380",
        issue_date=issue_date,
        seller=seller,
        buyer=buyer,
        items=items,
        totals=totals,
        tax_breakdown=tax_breakdown,
        currency=str_element(doc.trade.settlement.currency_code) or "EUR",
        profile=profile,
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
        invoice_notes=invoice_notes,
        payment_terms=payment_terms,
        tax_exemption_reason=tax_exemption_reason,
        tax_exemption_reason_code=tax_exemption_reason_code,
        vat_point_date_code=vat_point_date_code,
        skonto_percent=skonto_percent,
        skonto_days=skonto_days,
        purchase_order_reference=purchase_order_reference,
        sales_order_reference=sales_order_reference,
        contract_reference=contract_reference,
        project_reference=project_reference,
        preceding_invoice_number=preceding_invoice_number,
        preceding_invoice_date=preceding_invoice_date,
        despatch_advice_reference=despatch_advice_reference,
        tender_or_lot_reference=tender_or_lot_reference,
        invoiced_object_identifier=invoiced_object_identifier,
        business_process_type=business_process_type,
        remittance_information=remittance_information,
        allowances_charges=allowances_charges,
        buyer_iban=buyer_iban,
        mandate_reference_id=mandate_reference_id,
        seller_tax_representative=seller_tax_representative,
        payee_name=payee_name,
        payee_id=payee_id,
        payee_legal_registration_id=payee_legal_registration_id,
        payment_card_pan=payment_card_pan,
        payment_card_holder=payment_card_holder,
        seller_iban=seller_iban,
        seller_bic=seller_bic,
        seller_bank_name=seller_bank_name,
        receiving_advice_reference=receiving_advice_reference,
        delivery_location_id=delivery_location_id,
        payment_means_type_code=payment_means_type_code,
        payment_means_text=payment_means_text,
        buyer_reference=buyer_reference,
        supporting_documents=supporting_documents,
        seller_additional_legal_info=seller_additional_legal_info,
        creditor_reference_id=creditor_reference_id,
        buyer_accounting_reference=buyer_accounting_reference,
    )


def _extract_tax_breakdown(doc: Document) -> list[TaxBreakdown]:
    breakdown: list[TaxBreakdown] = []
    trade_tax_container = doc.trade.settlement.trade_tax
    if not hasattr(trade_tax_container, "children"):
        return breakdown

    for tax in trade_tax_container.children:
        try:
            breakdown.append(
                TaxBreakdown(
                    tax_rate=safe_decimal(getattr(tax, "rate_applicable_percent", "0")),
                    tax_category=str_element(getattr(tax, "category_code", "S")) or "S",
                    taxable_amount=safe_decimal(getattr(tax, "basis_amount", "0")),
                    tax_amount=safe_decimal(getattr(tax, "calculated_amount", "0")),
                )
            )
        except Exception:
            logger.warning("Failed to parse tax breakdown entry", exc_info=True)
    return breakdown


def _extract_totals(doc: Document) -> Totals | None:
    try:
        ms = doc.trade.settlement.monetary_summation

        # drafthorse routes TaxTotalAmount to tax_total_other_currency (MultiCurrencyField)
        # instead of tax_total (CurrencyField) — check both sources.
        tax_total = safe_decimal(getattr(ms, "tax_total", "0"))
        if tax_total == Decimal("0"):
            tax_total = _extract_tax_total_fallback(ms)

        return Totals(
            net_total=safe_decimal(getattr(ms, "line_total", "0")),
            tax_basis_total=safe_decimal(getattr(ms, "tax_basis_total", "0")),
            tax_total=tax_total,
            gross_total=safe_decimal(getattr(ms, "grand_total", "0")),
            prepaid_amount=safe_decimal(getattr(ms, "prepaid_total", "0")),
            due_payable=safe_decimal(getattr(ms, "due_amount", "0")),
        )
    except Exception:
        logger.warning("Failed to extract totals", exc_info=True)
        return None


def _extract_tax_total_fallback(ms: object) -> Decimal:
    """Extract tax total from tax_total_other_currency (MultiCurrencyField fallback)."""
    container = getattr(ms, "tax_total_other_currency", None)
    if container is None:
        return Decimal("0")
    for child in getattr(container, "children", []):
        if isinstance(child, tuple) and len(child) >= 1:
            try:
                return Decimal(str(child[0]))
            except (InvalidOperation, ValueError):
                continue
    return Decimal("0")
