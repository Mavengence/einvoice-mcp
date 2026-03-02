"""CII element extractors for party, line items, and utility conversions."""

import contextlib
import logging
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from drafthorse.models.document import Document

from einvoice_mcp.models import (
    Address,
    ItemAttribute,
    LineAllowanceCharge,
    LineItem,
    Party,
    TaxCategory,
)

logger = logging.getLogger(__name__)


def extract_party(party_obj: object) -> Party | None:
    """Extract a Party from a drafthorse trade party object."""
    try:
        name = str_element(getattr(party_obj, "name", ""))
        if not name:
            return None

        addr_obj = getattr(party_obj, "address", None)
        street_2_val = str_element(getattr(addr_obj, "line_two", "")) or None
        street_3_val = str_element(getattr(addr_obj, "line_three", "")) or None
        subdivision_val = str_element(getattr(addr_obj, "country_subdivision", ""))
        address = Address(
            street=str_element(getattr(addr_obj, "line_one", "")),
            street_2=street_2_val,
            street_3=street_3_val,
            city=str_element(getattr(addr_obj, "city_name", "")),
            postal_code=str_element(getattr(addr_obj, "postcode", "")),
            country_code=str_element(getattr(addr_obj, "country_id", "DE")) or "DE",
            country_subdivision=subdivision_val or None,
        )

        tax_id = None
        tax_number = None
        tax_regs = getattr(party_obj, "tax_registrations", None)
        if tax_regs and hasattr(tax_regs, "children"):
            for reg in tax_regs.children:
                id_elem = getattr(reg, "id", None)
                if id_elem:
                    scheme_id = extract_scheme_id(id_elem)
                    extracted = str_element(id_elem)
                    if not extracted:
                        continue
                    if scheme_id == "FC":
                        tax_number = extracted
                    else:
                        tax_id = extracted

        # Trading name (BT-28/BT-45)
        trading_name = None
        legal_org = getattr(party_obj, "legal_organization", None)
        if legal_org:
            tn = str_element(getattr(legal_org, "trade_name", ""))
            if tn:
                trading_name = tn

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
                ea_str = str_element(uri_id)
                if ea_str and ea_str not in ("()", "None"):
                    electronic_address = ea_str
                    ea_scheme = extract_scheme_id(uri_id)
                    if ea_scheme:
                        electronic_address_scheme = ea_scheme

        # Contact (BT-41, BT-42, BT-43)
        contact_name = None
        contact_phone = None
        contact_email = None
        contact_obj = getattr(party_obj, "contact", None)
        if contact_obj:
            cn = str_element(getattr(contact_obj, "person_name", ""))
            if cn:
                contact_name = cn
            tel_obj = getattr(contact_obj, "telephone", None)
            if tel_obj:
                tel = str_element(getattr(tel_obj, "number", ""))
                if tel:
                    contact_phone = tel
            email_obj = getattr(contact_obj, "email", None)
            if email_obj:
                em = str_element(getattr(email_obj, "address", ""))
                if em:
                    contact_email = em

        return Party(
            name=name,
            trading_name=trading_name,
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


def extract_scheme_id(id_elem: object) -> str:
    """Extract schemeID from a drafthorse IDElement."""
    scheme = getattr(id_elem, "_scheme_id", None)
    if scheme:
        return str(scheme)
    s = str(id_elem).strip()
    if s.endswith(")"):
        paren_idx = s.rfind(" (")
        if paren_idx > 0:
            return s[paren_idx + 2 : -1]
    return ""


def extract_items(doc: Document) -> list[LineItem]:
    """Extract line items from a drafthorse Document."""
    items: list[LineItem] = []
    for li in doc.trade.items.children:
        try:
            description = str_element(getattr(li.product, "name", "")) or "Unbekannt"

            bq = li.delivery.billed_quantity
            quantity = safe_decimal(getattr(bq, "_amount", "1"))
            unit_code = getattr(bq, "_unit_code", "H87") or "H87"

            unit_price = safe_decimal(getattr(li.agreement.net, "amount", "0"))

            tax_rate = Decimal("19.00")
            tax_category = TaxCategory.S
            line_tax = getattr(li.settlement, "trade_tax", None)
            if line_tax:
                rate = getattr(line_tax, "rate_applicable_percent", None)
                if rate is not None:
                    tax_rate = safe_decimal(rate)
                cat = str_element(getattr(line_tax, "category_code", ""))
                if cat in TaxCategory.__members__:
                    tax_category = TaxCategory(cat)

            # Line item note (BT-127)
            item_note = None
            line_notes = getattr(li.document, "notes", None)
            if line_notes and hasattr(line_notes, "children"):
                for note in line_notes.children:
                    content = getattr(note, "content", None)
                    text = str_element(content) if content else str_element(note)
                    if text:
                        item_note = text
                        break

            # Line-level allowances/charges (BG-27/BG-28)
            line_allowances = _extract_line_allowances(li)

            # Product identifiers (BT-155, BT-156, BT-157)
            seller_item_id = str_element(getattr(li.product, "seller_assigned_id", "")) or None
            buyer_item_id = str_element(getattr(li.product, "buyer_assigned_id", "")) or None
            standard_item_id, standard_item_scheme = _extract_standard_item(li)

            # Gross price (BT-148) and price discount (BT-147)
            item_gross_price, item_price_discount = _extract_gross_price(li)

            # Item classification (BT-158)
            item_classification_id, item_classification_scheme, item_classification_version = (
                _extract_classification(li)
            )

            # Item country of origin (BT-159)
            item_country_of_origin = None
            origin_obj = getattr(li.product, "origin", None)
            if origin_obj:
                origin_id = str_element(getattr(origin_obj, "id", ""))
                if origin_id and len(origin_id) == 2:
                    item_country_of_origin = origin_id

            # Item attributes (BG-30, BT-160/BT-161)
            item_attributes = _extract_item_attributes(li)

            # Line-level billing period (BT-134/BT-135)
            line_period_start, line_period_end = _extract_line_period(li)

            # Buyer accounting reference (BT-133)
            buyer_accounting_reference = None
            acct_obj = getattr(li.settlement, "accounting_account", None)
            if acct_obj:
                acct_id = str_element(getattr(acct_obj, "id", ""))
                if acct_id:
                    buyer_accounting_reference = acct_id

            # Line ID (BT-126)
            line_id = str_element(getattr(li.document, "line_id", "")) or None

            # Line object identifier (BT-128) — AdditionalReferencedDocument
            line_object_identifier = None
            line_object_identifier_scheme = "AWV"
            line_add_ref = getattr(li.settlement, "additional_referenced_document", None)
            if line_add_ref:
                ltc = str_element(getattr(line_add_ref, "type_code", ""))
                lref_id = str_element(getattr(line_add_ref, "issuer_assigned_id", ""))
                if ltc == "130" and lref_id:
                    line_object_identifier = lref_id

            # Line purchase order reference (BT-132)
            line_purchase_order_reference = None
            line_inv_refs = getattr(li.settlement, "invoice_referenced_document", None)
            if line_inv_refs and hasattr(line_inv_refs, "children"):
                for liref in line_inv_refs.children:
                    liref_id = str_element(getattr(liref, "issuer_assigned_id", ""))
                    if liref_id:
                        line_purchase_order_reference = liref_id
                        break

            # Preserve magnitude for negative quantities (credit notes)
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
                    line_id=line_id,
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
                    item_gross_price=item_gross_price,
                    item_price_discount=item_price_discount,
                    item_classification_id=item_classification_id,
                    item_classification_scheme=item_classification_scheme,
                    item_classification_version=item_classification_version,
                    allowances_charges=line_allowances,
                    buyer_accounting_reference=buyer_accounting_reference,
                    line_period_start=line_period_start,
                    line_period_end=line_period_end,
                    item_country_of_origin=item_country_of_origin,
                    attributes=item_attributes,
                    line_object_identifier=line_object_identifier,
                    line_object_identifier_scheme=line_object_identifier_scheme,
                    line_purchase_order_reference=line_purchase_order_reference,
                )
            )
        except Exception:
            logger.warning("Failed to parse line item", exc_info=True)
    return items


def _extract_line_allowances(li: Any) -> list[LineAllowanceCharge]:
    """Extract line-level allowances/charges (BG-27/BG-28)."""
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
            lac_amount = safe_decimal(getattr(lac_item, "actual_amount", "0"))
            lac_reason = str_element(getattr(lac_item, "reason", ""))
            line_allowances.append(
                LineAllowanceCharge(charge=lac_is_charge, amount=lac_amount, reason=lac_reason)
            )
    return line_allowances


def _extract_standard_item(li: Any) -> tuple[str | None, str]:
    """Extract standard item ID (BT-157) and scheme."""
    standard_item_id = None
    standard_item_scheme = "0160"
    gid = getattr(li.product, "global_id", None)
    if gid:
        gid_str = str_element(gid)
        if gid_str:
            standard_item_id = gid_str
            gid_scheme = extract_scheme_id(gid)
            if gid_scheme:
                standard_item_scheme = gid_scheme
    return standard_item_id, standard_item_scheme


def _extract_gross_price(li: Any) -> tuple[Decimal | None, Decimal | None]:
    """Extract gross price (BT-148) and price discount (BT-147)."""
    item_gross_price = None
    item_price_discount = None
    gross_obj = getattr(li.agreement, "gross", None)
    if gross_obj:
        gp = safe_decimal(getattr(gross_obj, "amount", "0"))
        if gp > 0:
            item_gross_price = gp
            charge_container = getattr(gross_obj, "charge", None)
            if charge_container and hasattr(charge_container, "children"):
                for ch in charge_container.children:
                    disc = safe_decimal(getattr(ch, "actual_amount", "0"))
                    if disc > 0:
                        item_price_discount = disc
                        break
    return item_gross_price, item_price_discount


def _extract_classification(li: Any) -> tuple[str | None, str, str]:
    """Extract item classification (BT-158)."""
    item_classification_id = None
    item_classification_scheme = "STL"
    item_classification_version = ""
    cls_container = getattr(li.product, "classifications", None)
    if cls_container and hasattr(cls_container, "children"):
        for cls_item in cls_container.children:
            cc = getattr(cls_item, "class_code", None)
            if cc:
                cc_text = getattr(cc, "_text", None)
                if cc_text:
                    item_classification_id = str(cc_text).strip()
                    cc_list_id = getattr(cc, "_list_id", "")
                    if cc_list_id:
                        item_classification_scheme = str(cc_list_id).strip()
                    cc_version = getattr(cc, "_list_version_id", "")
                    if cc_version:
                        item_classification_version = str(cc_version).strip()
                    break
    return item_classification_id, item_classification_scheme, item_classification_version


def _extract_item_attributes(li: Any) -> list[ItemAttribute]:
    """Extract item attributes (BG-30, BT-160/BT-161)."""
    item_attributes: list[ItemAttribute] = []
    char_container = getattr(li.product, "characteristics", None)
    if char_container and hasattr(char_container, "children"):
        for char_item in char_container.children:
            attr_name = str_element(getattr(char_item, "type_code", ""))
            attr_value = str_element(getattr(char_item, "value", ""))
            if attr_name and attr_value:
                item_attributes.append(ItemAttribute(name=attr_name, value=attr_value))
    return item_attributes


def _extract_line_period(li: Any) -> tuple[date | None, date | None]:
    """Extract line-level billing period (BT-134/BT-135)."""
    line_period_start: date | None = None
    line_period_end: date | None = None
    line_period = getattr(li.settlement, "period", None)
    if line_period:
        lps = getattr(line_period, "start", None)
        if lps:
            lps_val = str(lps).strip()
            if lps_val and lps_val != "None":
                with contextlib.suppress(ValueError):
                    line_period_start = date.fromisoformat(lps_val[:10])
        lpe = getattr(line_period, "end", None)
        if lpe:
            lpe_val = str(lpe).strip()
            if lpe_val and lpe_val != "None":
                with contextlib.suppress(ValueError):
                    line_period_end = date.fromisoformat(lpe_val[:10])
    return line_period_start, line_period_end


def str_element(value: object) -> str:
    """Convert a drafthorse element to a clean string.

    IDElement.__str__ returns "text (schemeID)" where schemeID is a short
    uppercase code like "VA", "EM", "9930". Only strip this pattern — do NOT
    strip arbitrary parenthetical text from descriptions or names.
    """
    if value is None:
        return ""
    s = str(value).strip()
    if s == "()":
        return ""
    if s.endswith(")"):
        paren_idx = s.rfind(" (")
        if paren_idx > 0:
            scheme = s[paren_idx + 2 : -1]
            if not scheme or (
                len(scheme) <= 10
                and scheme.isascii()
                and scheme.isalnum()
                and scheme == scheme.upper()
            ):
                s = s[:paren_idx]
    return s


def safe_decimal(value: object) -> Decimal:
    """Convert a drafthorse element to a Decimal safely."""
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    if hasattr(value, "_value"):
        raw = getattr(value, "_value", None)
        if isinstance(raw, Decimal):
            return raw
        if raw is None:
            return Decimal("0")
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
