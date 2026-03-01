"""Parse CII XML and extract from ZUGFeRD PDFs."""

import logging
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden
from drafthorse.models.document import Document

from einvoice_mcp.errors import InvoiceParsingError
from einvoice_mcp.models import (
    Address,
    LineItem,
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
    )


def _extract_party(party_obj: object) -> Party | None:
    try:
        name = _str_element(getattr(party_obj, "name", ""))
        if not name:
            return None

        addr_obj = getattr(party_obj, "address", None)
        address = Address(
            street=_str_element(getattr(addr_obj, "line_one", "")),
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

        return Party(name=name, address=address, tax_id=tax_id, tax_number=tax_number)
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
    # Only strip trailing " (XX)" where XX is 1-10 ASCII alphanumeric chars
    # without any lowercase letters.  This matches schemeID patterns like
    # (VA), (EM), (9930) but NOT description text like "Reisekosten (pauschal)"
    # or German abbreviations like "(3Ü)".
    if s.endswith(")"):
        paren_idx = s.rfind(" (")
        if paren_idx > 0:
            scheme = s[paren_idx + 2 : -1]
            if (
                scheme
                and len(scheme) <= 10
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
