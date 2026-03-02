"""Parse CII XML and extract from ZUGFeRD PDFs."""

import logging
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden
from drafthorse.models.document import Document

from einvoice_mcp.errors import InvoiceParsingError
from einvoice_mcp.models import (
    Address,
    LineAllowanceCharge,
    LineItem,
    ParsedAllowanceCharge,
    ParsedInvoice,
    Party,
    TaxBreakdown,
    TaxCategory,
    Totals,
)

logger = logging.getLogger(__name__)


def parse_xml(xml_bytes: bytes) -> ParsedInvoice:
    """Parse CII XML bytes into a ParsedInvoice.

    Pre-screens with defusedxml to block XXE/DTD attacks before
    passing to drafthorse (which uses lxml without entity protection).
    """
    # Pre-screen for XXE, DTD, and entity expansion attacks
    try:
        ElementTree.fromstring(xml_bytes)
    except (EntitiesForbidden, DTDForbidden, ExternalReferenceForbidden) as exc:
        raise InvoiceParsingError() from exc
    except ElementTree.ParseError as exc:
        raise InvoiceParsingError() from exc

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
    seller = _extract_party(doc.trade.agreement.seller)
    buyer = _extract_party(doc.trade.agreement.buyer)
    items = _extract_items(doc)
    tax_breakdown = _extract_tax_breakdown(doc)
    totals = _extract_totals(doc)

    issue_date = ""
    if doc.header.issue_date_time:
        issue_date = str(doc.header.issue_date_time)

    profile = _str_element(doc.context.guideline_parameter.id)

    # Delivery location (BT-70..BT-80)
    delivery_party_name = ""
    delivery_street = ""
    delivery_city = ""
    delivery_postal_code = ""
    delivery_country_code = ""
    try:
        ship_to = doc.trade.delivery.ship_to
        dn = _str_element(getattr(ship_to, "name", ""))
        if dn:
            delivery_party_name = dn
        addr = getattr(ship_to, "address", None)
        if addr:
            ds = _str_element(getattr(addr, "line_one", ""))
            if ds:
                delivery_street = ds
            dc = _str_element(getattr(addr, "city_name", ""))
            if dc:
                delivery_city = dc
            dp = _str_element(getattr(addr, "postcode", ""))
            if dp:
                delivery_postal_code = dp
            dcc = _str_element(getattr(addr, "country_id", ""))
            if dcc:
                delivery_country_code = dcc
    except Exception:
        pass

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
        pass

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
        pass

    # Invoice note (BT-22)
    invoice_note = ""
    try:
        notes = getattr(doc.header, "notes", None)
        if notes and hasattr(notes, "children"):
            for note in notes.children:
                content = getattr(note, "content", None)
                text = _str_element(content) if content else _str_element(note)
                if text:
                    invoice_note = text
                    break
    except Exception:
        pass

    # Payment terms (BT-20) and due date (BT-9)
    payment_terms = ""
    due_date = ""
    try:
        terms = doc.trade.settlement.terms
        if hasattr(terms, "children"):
            for term in terms.children:
                desc = _str_element(getattr(term, "description", ""))
                if desc:
                    payment_terms = desc
                due_obj = getattr(term, "due", None)
                if due_obj:
                    due_val = str(due_obj).strip()
                    if due_val and due_val != "None":
                        due_date = due_val
                if payment_terms or due_date:
                    break
    except Exception:
        pass

    # Purchase order reference (BT-13)
    purchase_order_reference = ""
    try:
        po_id = doc.trade.agreement.buyer_order.issuer_assigned_id
        val = _str_element(po_id)
        if val:
            purchase_order_reference = val
    except Exception:
        pass

    # Sales order reference (BT-14)
    sales_order_reference = ""
    try:
        so_id = doc.trade.agreement.seller_order.issuer_assigned_id
        val = _str_element(so_id)
        if val:
            sales_order_reference = val
    except Exception:
        pass

    # Contract reference (BT-12)
    contract_reference = ""
    try:
        ct_id = doc.trade.agreement.contract.issuer_assigned_id
        val = _str_element(ct_id)
        if val:
            contract_reference = val
    except Exception:
        pass

    # Project reference (BT-11)
    project_reference = ""
    try:
        pr_id = doc.trade.agreement.procuring_project_type.id
        val = _str_element(pr_id)
        if val:
            project_reference = val
    except Exception:
        pass

    # Despatch advice reference (BT-16)
    despatch_advice_reference = ""
    try:
        da_id = doc.trade.delivery.despatch_advice.issuer_assigned_id
        val = _str_element(da_id)
        if val:
            despatch_advice_reference = val
    except Exception:
        pass

    # Invoiced object identifier (BT-18) — AdditionalReferencedDocument TypeCode=130
    invoiced_object_identifier = ""
    try:
        add_refs = doc.trade.agreement.additional_references
        if hasattr(add_refs, "children"):
            for ref in add_refs.children:
                tc = _str_element(getattr(ref, "type_code", ""))
                if tc == "130":
                    oid = _str_element(getattr(ref, "issuer_assigned_id", ""))
                    if oid:
                        invoiced_object_identifier = oid
                        break
    except Exception:
        pass

    # Business process type (BT-23)
    business_process_type = ""
    try:
        bp_id = doc.context.business_parameter.id
        val = _str_element(bp_id)
        if val:
            business_process_type = val
    except Exception:
        pass

    # Preceding invoice number (BT-25)
    preceding_invoice_number = ""
    try:
        inv_ref = doc.trade.settlement.invoice_referenced_document
        ref_id = getattr(inv_ref, "issuer_assigned_id", None)
        if ref_id:
            val = _str_element(ref_id)
            if val:
                preceding_invoice_number = val
    except Exception:
        pass

    # Remittance information (BT-83) / Verwendungszweck
    remittance_information = ""
    try:
        pay_ref = doc.trade.settlement.payment_reference
        val = _str_element(pay_ref)
        if val:
            remittance_information = val
    except Exception:
        pass

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
                amount = _safe_decimal(getattr(ac_item, "actual_amount", "0"))
                reason = _str_element(getattr(ac_item, "reason", ""))
                ac_tax_rate = Decimal("0")
                ac_tax_cat = "S"
                tax_container = getattr(ac_item, "trade_tax", None)
                if tax_container and hasattr(tax_container, "children"):
                    for tax_child in tax_container.children:
                        rate_val = _safe_decimal(
                            getattr(tax_child, "rate_applicable_percent", "0")
                        )
                        cat_val = _str_element(
                            getattr(tax_child, "category_code", "S")
                        ) or "S"
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
        pass

    # IBAN / BIC / Bank name (BT-84, BT-86)
    seller_iban = ""
    seller_bic = ""
    seller_bank_name = ""
    try:
        pm_container = doc.trade.settlement.payment_means
        if hasattr(pm_container, "children"):
            for pm in pm_container.children:
                acct = getattr(pm, "payee_account", None)
                if acct:
                    iban_val = _str_element(getattr(acct, "iban", ""))
                    if iban_val:
                        seller_iban = iban_val
                    bank_name = _str_element(getattr(acct, "account_name", ""))
                    if bank_name:
                        seller_bank_name = bank_name
                inst = getattr(pm, "payee_institution", None)
                if inst:
                    bic_val = _str_element(getattr(inst, "bic", ""))
                    if bic_val:
                        seller_bic = bic_val
                if seller_iban:
                    break
    except Exception:
        pass

    return ParsedInvoice(
        invoice_id=_str_element(doc.header.id),
        type_code=_str_element(doc.header.type_code) or "380",
        issue_date=issue_date,
        seller=seller,
        buyer=buyer,
        items=items,
        totals=totals,
        tax_breakdown=tax_breakdown,
        currency=_str_element(doc.trade.settlement.currency_code) or "EUR",
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
        payment_terms=payment_terms,
        purchase_order_reference=purchase_order_reference,
        sales_order_reference=sales_order_reference,
        contract_reference=contract_reference,
        project_reference=project_reference,
        preceding_invoice_number=preceding_invoice_number,
        despatch_advice_reference=despatch_advice_reference,
        invoiced_object_identifier=invoiced_object_identifier,
        business_process_type=business_process_type,
        remittance_information=remittance_information,
        allowances_charges=allowances_charges,
        seller_iban=seller_iban,
        seller_bic=seller_bic,
        seller_bank_name=seller_bank_name,
    )


def _extract_party(party_obj: object) -> Party | None:
    try:
        name = _str_element(getattr(party_obj, "name", ""))
        if not name:
            return None

        addr_obj = getattr(party_obj, "address", None)
        street_2_val = _str_element(getattr(addr_obj, "line_two", "")) or None
        street_3_val = _str_element(getattr(addr_obj, "line_three", "")) or None
        address = Address(
            street=_str_element(getattr(addr_obj, "line_one", "")),
            street_2=street_2_val,
            street_3=street_3_val,
            city=_str_element(getattr(addr_obj, "city_name", "")),
            postal_code=_str_element(getattr(addr_obj, "postcode", "")),
            country_code=_str_element(getattr(addr_obj, "country_id", "DE")) or "DE",
        )

        tax_id = None
        tax_number = None
        tax_regs = getattr(party_obj, "tax_registrations", None)
        if tax_regs and hasattr(tax_regs, "children"):
            for reg in tax_regs.children:
                id_elem = getattr(reg, "id", None)
                if id_elem:
                    # drafthorse IDElement stores schemeID: check raw tuple/attr
                    scheme_id = _extract_scheme_id(id_elem)
                    extracted = _str_element(id_elem)
                    if not extracted:
                        continue
                    if scheme_id == "FC":
                        tax_number = extracted
                    else:
                        # VA or unknown schemeID → treat as USt-IdNr.
                        tax_id = extracted

        # Global ID / Registration ID (BT-29)
        registration_id = None
        global_id_container = getattr(party_obj, "global_id", None)
        if global_id_container and hasattr(global_id_container, "children"):
            for gid_entry in global_id_container.children:
                if isinstance(gid_entry, tuple) and len(gid_entry) == 2:
                    registration_id = str(gid_entry[1]).strip() or None
                    break

        # Electronic address (BT-34/BT-49)
        electronic_address = None
        electronic_address_scheme = "EM"
        ea_obj = getattr(party_obj, "electronic_address", None)
        if ea_obj:
            uri_id = getattr(ea_obj, "uri_ID", None)
            if uri_id:
                ea_str = _str_element(uri_id)
                # Filter out empty/placeholder values like "()" or "None"
                if ea_str and ea_str not in ("()", "None"):
                    electronic_address = ea_str
                    ea_scheme = _extract_scheme_id(uri_id)
                    if ea_scheme:
                        electronic_address_scheme = ea_scheme

        # Seller/Buyer contact (BT-41, BT-42, BT-43)
        contact_name = None
        contact_phone = None
        contact_email = None
        contact_obj = getattr(party_obj, "contact", None)
        if contact_obj:
            cn = _str_element(getattr(contact_obj, "person_name", ""))
            if cn:
                contact_name = cn
            tel_obj = getattr(contact_obj, "telephone", None)
            if tel_obj:
                tel = _str_element(getattr(tel_obj, "number", ""))
                if tel:
                    contact_phone = tel
            email_obj = getattr(contact_obj, "email", None)
            if email_obj:
                em = _str_element(getattr(email_obj, "address", ""))
                if em:
                    contact_email = em

        return Party(
            name=name,
            address=address,
            tax_id=tax_id,
            tax_number=tax_number,
            registration_id=registration_id,
            electronic_address=electronic_address,
            electronic_address_scheme=electronic_address_scheme,
            contact_name=contact_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
        )
    except Exception:
        logger.warning("Failed to extract party data", exc_info=True)
        return None


def _extract_scheme_id(id_elem: object) -> str:
    """Extract schemeID from a drafthorse IDElement."""
    # drafthorse stores schemeID in _scheme_id attribute
    scheme = getattr(id_elem, "_scheme_id", None)
    if scheme:
        return str(scheme)
    # Fallback: check the string representation for " (XX)" pattern
    s = str(id_elem).strip()
    if s.endswith(")"):
        paren_idx = s.rfind(" (")
        if paren_idx > 0:
            return s[paren_idx + 2 : -1]
    return ""


def _extract_items(doc: Document) -> list[LineItem]:
    items: list[LineItem] = []
    for li in doc.trade.items.children:
        try:
            description = _str_element(getattr(li.product, "name", "")) or "Unbekannt"

            # Billed quantity
            bq = li.delivery.billed_quantity
            quantity = _safe_decimal(getattr(bq, "_amount", "1"))
            unit_code = getattr(bq, "_unit_code", "H87") or "H87"

            # Net unit price
            unit_price = _safe_decimal(getattr(li.agreement.net, "amount", "0"))

            # Tax from line item (single ApplicableTradeTax, not a container)
            tax_rate = Decimal("19.00")
            tax_category = TaxCategory.S
            line_tax = getattr(li.settlement, "trade_tax", None)
            if line_tax:
                rate = getattr(line_tax, "rate_applicable_percent", None)
                if rate is not None:
                    tax_rate = _safe_decimal(rate)
                cat = _str_element(getattr(line_tax, "category_code", ""))
                if cat in TaxCategory.__members__:
                    tax_category = TaxCategory(cat)

            # Line item note (BT-127)
            item_note = None
            line_notes = getattr(li.document, "notes", None)
            if line_notes and hasattr(line_notes, "children"):
                for note in line_notes.children:
                    content = getattr(note, "content", None)
                    text = _str_element(content) if content else _str_element(note)
                    if text:
                        item_note = text
                        break

            # Line-level allowances/charges (BG-27/BG-28)
            line_allowances: list[LineAllowanceCharge] = []
            line_ac_container = getattr(li.settlement, "allowance_charge", None)
            if line_ac_container and hasattr(line_ac_container, "children"):
                for lac_item in line_ac_container.children:
                    lac_indicator = getattr(lac_item, "indicator", None)
                    lac_val = getattr(lac_indicator, "_value", None)
                    if lac_val is not None:
                        lac_is_charge = bool(lac_val)
                    else:
                        lac_is_charge = bool(lac_indicator) if lac_indicator is not None else False
                    lac_amount = _safe_decimal(getattr(lac_item, "actual_amount", "0"))
                    lac_reason = _str_element(getattr(lac_item, "reason", ""))
                    line_allowances.append(
                        LineAllowanceCharge(
                            charge=lac_is_charge,
                            amount=lac_amount,
                            reason=lac_reason,
                        )
                    )

            # Product identifiers (BT-155, BT-156, BT-157)
            seller_item_id = _str_element(
                getattr(li.product, "seller_assigned_id", "")
            ) or None
            buyer_item_id = _str_element(
                getattr(li.product, "buyer_assigned_id", "")
            ) or None
            standard_item_id = None
            standard_item_scheme = "0160"
            gid = getattr(li.product, "global_id", None)
            if gid:
                gid_str = _str_element(gid)
                if gid_str:
                    standard_item_id = gid_str
                    gid_scheme = _extract_scheme_id(gid)
                    if gid_scheme:
                        standard_item_scheme = gid_scheme

            # Preserve magnitude for negative quantities (credit notes, TypeCode 381);
            # only fall back to 0.01 when the parsed quantity is exactly zero.
            if quantity < 0:
                logger.warning(
                    "Negative quantity %s in line item '%s' — using absolute value",
                    quantity,
                    description,
                )
                quantity = abs(quantity)
            if quantity == 0:
                quantity = Decimal("0.01")

            items.append(
                LineItem(
                    description=description,
                    quantity=quantity,
                    unit_code=unit_code,
                    unit_price=unit_price,
                    tax_rate=tax_rate,
                    tax_category=tax_category,
                    seller_item_id=seller_item_id,
                    buyer_item_id=buyer_item_id,
                    standard_item_id=standard_item_id,
                    standard_item_scheme=standard_item_scheme,
                    item_note=item_note,
                    allowances_charges=line_allowances,
                )
            )
        except Exception:
            logger.warning("Failed to parse line item", exc_info=True)
    return items


def _extract_tax_breakdown(doc: Document) -> list[TaxBreakdown]:
    breakdown: list[TaxBreakdown] = []
    trade_tax_container = doc.trade.settlement.trade_tax
    if not hasattr(trade_tax_container, "children"):
        return breakdown

    for tax in trade_tax_container.children:
        try:
            breakdown.append(
                TaxBreakdown(
                    tax_rate=_safe_decimal(getattr(tax, "rate_applicable_percent", "0")),
                    tax_category=_str_element(getattr(tax, "category_code", "S")) or "S",
                    taxable_amount=_safe_decimal(getattr(tax, "basis_amount", "0")),
                    tax_amount=_safe_decimal(getattr(tax, "calculated_amount", "0")),
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
        tax_total = _safe_decimal(getattr(ms, "tax_total", "0"))
        if tax_total == Decimal("0"):
            tax_total = _extract_tax_total_fallback(ms)

        return Totals(
            net_total=_safe_decimal(getattr(ms, "tax_basis_total", "0")),
            tax_total=tax_total,
            gross_total=_safe_decimal(getattr(ms, "grand_total", "0")),
            due_payable=_safe_decimal(getattr(ms, "due_amount", "0")),
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


def _str_element(value: object) -> str:
    """Convert a drafthorse element to a clean string.

    IDElement.__str__ returns "text (schemeID)" where schemeID is a short
    uppercase code like "VA", "EM", "9930". Only strip this pattern — do NOT
    strip arbitrary parenthetical text from descriptions or names.
    """
    if value is None:
        return ""
    s = str(value).strip()
    # drafthorse empty IDElements produce "()" — treat as empty
    if s == "()":
        return ""
    # Only strip trailing " (XX)" where XX is 1-10 ASCII alphanumeric chars
    # without any lowercase letters.  This matches schemeID patterns like
    # (VA), (EM), (9930) but NOT description text like "Reisekosten (pauschal)"
    # or German abbreviations like "(3Ü)".
    if s.endswith(")"):
        paren_idx = s.rfind(" (")
        if paren_idx > 0:
            scheme = s[paren_idx + 2 : -1]
            # Strip " ()" (empty schemeID) or " (XX)" where XX is
            # uppercase alphanumeric (schemeID pattern).
            if not scheme or (
                len(scheme) <= 10
                and scheme.isascii()
                and scheme.isalnum()
                and scheme == scheme.upper()
            ):
                s = s[:paren_idx]
    return s


def _safe_decimal(value: object) -> Decimal:
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    # drafthorse DecimalElement: ._value is Decimal
    if hasattr(value, "_value"):
        raw = getattr(value, "_value", None)
        if isinstance(raw, Decimal):
            return raw
        if raw is None:
            return Decimal("0")
    # drafthorse CurrencyElement / QuantityElement: ._amount is Decimal or str
    if hasattr(value, "_amount"):
        raw = getattr(value, "_amount", None)
        if isinstance(raw, Decimal):
            return raw
        if raw is not None:
            try:
                return Decimal(str(raw))
            except (InvalidOperation, ValueError):
                pass
    try:
        s = repr(value) if not isinstance(value, str) else value
        s = s.strip()
        if s.endswith(" ()"):
            s = s[:-3]
        if not s:
            return Decimal("0")
        return Decimal(s)
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
