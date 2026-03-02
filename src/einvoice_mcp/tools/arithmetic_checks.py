"""BR-CO arithmetic integrity checks for CII XML invoices."""

import contextlib
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from einvoice_mcp.models import FieldCheck

CII_NS = {
    "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
    "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
    "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
}


def _safe_amount(el: Element | None) -> Decimal | None:
    """Extract a decimal amount from an XML element, or None."""
    if el is None or not el.text:
        return None
    try:
        return Decimal(el.text.strip())
    except (InvalidOperation, ValueError):
        return None


def check_arithmetic(checks: list[FieldCheck], root: Element) -> None:
    """BR-CO-10..BR-CO-16: Mathematical integrity checks (advisory).

    Verifies that the monetary summation fields are arithmetically consistent.
    Tolerance: 0.05 EUR per rounding.
    """
    ms_prefix = ".//ram:SpecifiedTradeSettlementHeaderMonetarySummation"

    line_total = _safe_amount(root.find(f"{ms_prefix}/ram:LineTotalAmount", CII_NS))
    allowance_total = _safe_amount(
        root.find(f"{ms_prefix}/ram:AllowanceTotalAmount", CII_NS)
    )
    charge_total = _safe_amount(
        root.find(f"{ms_prefix}/ram:ChargeTotalAmount", CII_NS)
    )
    tax_basis = _safe_amount(
        root.find(f"{ms_prefix}/ram:TaxBasisTotalAmount", CII_NS)
    )
    tax_total = _safe_amount(
        root.find(f"{ms_prefix}/ram:TaxTotalAmount", CII_NS)
    )
    grand_total = _safe_amount(
        root.find(f"{ms_prefix}/ram:GrandTotalAmount", CII_NS)
    )
    prepaid = _safe_amount(
        root.find(f"{ms_prefix}/ram:TotalPrepaidAmount", CII_NS)
    )
    due_payable = _safe_amount(
        root.find(f"{ms_prefix}/ram:DuePayableAmount", CII_NS)
    )

    tolerance = Decimal("0.05")

    # BR-CO-10: BT-109 = BT-106 - BT-107 + BT-108
    if line_total is not None and tax_basis is not None:
        expected_basis = line_total - (allowance_total or Decimal("0")) + (
            charge_total or Decimal("0")
        )
        if abs(tax_basis - expected_basis) > tolerance:
            checks.append(FieldCheck(
                field="BR-CO-10",
                name="Steuerbasis = Positionen - Abschläge + Zuschläge",
                present=False,
                value=f"BT-109={tax_basis}, erwartet={expected_basis}",
                required=False,
            ))

    # BR-CO-14: BT-110 = sum of BG-23 tax amounts
    if tax_total is not None:
        tax_entries = root.findall(".//ram:ApplicableTradeTax", CII_NS)
        tax_sum = Decimal("0")
        for te in tax_entries:
            ta_el = te.find("ram:CalculatedAmount", CII_NS)
            if ta_el is not None and ta_el.text:
                with contextlib.suppress(InvalidOperation, ValueError):
                    tax_sum += Decimal(ta_el.text.strip())
        if tax_entries and abs(tax_total - tax_sum) > tolerance:
            checks.append(FieldCheck(
                field="BR-CO-14",
                name="Steuerbetrag = Summe Steueraufschlüsselung",
                present=False,
                value=f"BT-110={tax_total}, Summe={tax_sum}",
                required=False,
            ))

    # BR-CO-15: BT-112 = BT-109 + BT-110
    if tax_basis is not None and grand_total is not None:
        expected_grand = tax_basis + (tax_total or Decimal("0"))
        if abs(grand_total - expected_grand) > tolerance:
            checks.append(FieldCheck(
                field="BR-CO-15",
                name="Brutto = Steuerbasis + Steuer",
                present=False,
                value=f"BT-112={grand_total}, erwartet={expected_grand}",
                required=False,
            ))

    # BR-CO-16: BT-115 = BT-112 - BT-113
    if grand_total is not None and due_payable is not None:
        expected_due = grand_total - (prepaid or Decimal("0"))
        if abs(due_payable - expected_due) > tolerance:
            checks.append(FieldCheck(
                field="BR-CO-16",
                name="Zahlbetrag = Brutto - Vorauszahlung",
                present=False,
                value=f"BT-115={due_payable}, erwartet={expected_due}",
                required=False,
            ))
