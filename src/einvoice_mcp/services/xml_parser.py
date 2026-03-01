"""Parse CII XML and extract from ZUGFeRD PDFs."""

import logging
from decimal import Decimal, InvalidOperation

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
    """Parse CII XML bytes into a ParsedInvoice."""
    try:
        doc = Document.parse(xml_bytes)
        return _extract_invoice(doc)
    except InvoiceParsingError:
        raise
    except Exception as exc:
        raise InvoiceParsingError(str(exc)) from exc


def extract_xml_from_pdf(pdf_bytes: bytes) -> bytes:
    """Extract embedded XML from a ZUGFeRD/Factur-X PDF."""
    try:
        from facturx import get_xml_from_pdf

        _filename, xml_bytes = get_xml_from_pdf(pdf_bytes, check_xsd=False)
        return bytes(xml_bytes)
    except ImportError as exc:
        raise InvoiceParsingError("factur-x library not installed") from exc
    except Exception as exc:
        raise InvoiceParsingError(f"PDF-Extraktion fehlgeschlagen: {exc}") from exc


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
        tax_regs = getattr(party_obj, "tax_registrations", None)
        if tax_regs and hasattr(tax_regs, "children"):
            for reg in tax_regs.children:
                id_elem = getattr(reg, "id", None)
                if id_elem and hasattr(id_elem, "_text") and id_elem._text:
                    tax_id = id_elem._text
                    break

        return Party(name=name, address=address, tax_id=tax_id)
    except Exception:
        logger.warning("Failed to extract party data", exc_info=True)
        return None


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

            items.append(
                LineItem(
                    description=description,
                    quantity=max(quantity, Decimal("0.01")),
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
    """Convert a drafthorse element to a clean string."""
    if value is None:
        return ""
    s = str(value).strip()
    # IDElement.__str__ returns "text (schemeID)" — strip the scheme suffix
    # e.g. "DE123456789 (VA)" → "DE123456789", "email@example.de (EM)" → "email@example.de"
    if s.endswith(")"):
        paren_idx = s.rfind(" (")
        if paren_idx > 0:
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
