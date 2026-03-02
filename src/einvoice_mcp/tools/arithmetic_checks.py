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

    # BR-CO-11: BT-106 = sum of all line net amounts (BT-131)
    line_items = root.findall(
        ".//ram:IncludedSupplyChainTradeLineItem", CII_NS,
    )
    if line_total is not None and line_items:
        line_net_sum = Decimal("0")
        for item in line_items:
            net_el = item.find(
                "ram:SpecifiedLineTradeSettlement"
                "/ram:SpecifiedTradeSettlementLineMonetarySummation"
                "/ram:LineTotalAmount",
                CII_NS,
            )
            net_val = _safe_amount(net_el)
            if net_val is not None:
                line_net_sum += net_val
        if abs(line_total - line_net_sum) > tolerance:
            checks.append(FieldCheck(
                field="BR-CO-11",
                name="Nettosumme = Summe Positionsnetto",
                present=False,
                value=f"BT-106={line_total}, Summe={line_net_sum}",
                required=False,
            ))

    # BR-CO-12: Line net = qty x price - line allowances + line charges
    for idx, item in enumerate(line_items):
        _check_line_arithmetic(checks, item, idx + 1, tolerance)

    # BR-CO-13: Tax amount per group = basis x rate (rounded)
    tax_entries = root.findall(".//ram:ApplicableTradeTax", CII_NS)
    for te in tax_entries:
        basis_el = te.find("ram:BasisAmount", CII_NS)
        rate_el = te.find("ram:RateApplicablePercent", CII_NS)
        calc_el = te.find("ram:CalculatedAmount", CII_NS)
        basis = _safe_amount(basis_el)
        rate = _safe_amount(rate_el)
        calc = _safe_amount(calc_el)
        if basis is not None and rate is not None and calc is not None:
            expected_tax = (basis * rate / Decimal("100")).quantize(
                Decimal("0.01"),
            )
            if abs(calc - expected_tax) > tolerance:
                checks.append(FieldCheck(
                    field="BR-CO-13",
                    name="Steuerbetrag = Basis x Satz",
                    present=False,
                    value=(
                        f"Berechnet={calc}, erwartet={expected_tax} "
                        f"(Basis={basis}, Satz={rate}%)"
                    ),
                    required=False,
                ))

    # BR-CO-14: BT-110 = sum of BG-23 tax amounts
    if tax_total is not None:
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


def _check_line_arithmetic(
    checks: list[FieldCheck],
    item: Element,
    line_num: int,
    tolerance: Decimal,
) -> None:
    """BR-CO-12: Line net amount = qty x unit_price - allowances + charges."""
    settle = item.find("ram:SpecifiedLineTradeSettlement", CII_NS)
    if settle is None:
        return

    line_net_el = settle.find(
        "ram:SpecifiedTradeSettlementLineMonetarySummation"
        "/ram:LineTotalAmount",
        CII_NS,
    )
    line_net = _safe_amount(line_net_el)
    if line_net is None:
        return

    # Quantity (BT-129)
    qty_el = item.find(
        "ram:SpecifiedLineTradeDelivery"
        "/ram:BilledQuantity",
        CII_NS,
    )
    qty = _safe_amount(qty_el)

    # Unit price (BT-146)
    price_el = item.find(
        "ram:SpecifiedLineTradeAgreement"
        "/ram:NetPriceProductTradePrice"
        "/ram:ChargeAmount",
        CII_NS,
    )
    price = _safe_amount(price_el)

    if qty is None or price is None:
        return

    expected = qty * price

    # Line-level allowances/charges (BG-27/BG-28)
    for ac in settle.findall("ram:SpecifiedTradeAllowanceCharge", CII_NS):
        ac_amount = _safe_amount(ac.find("ram:ActualAmount", CII_NS))
        if ac_amount is None:
            continue
        indicator = ac.find("ram:ChargeIndicator/udt:Indicator", CII_NS)
        is_charge = indicator is not None and indicator.text == "true"
        if is_charge:
            expected += ac_amount
        else:
            expected -= ac_amount

    if abs(line_net - expected) > tolerance:
        checks.append(FieldCheck(
            field="BR-CO-12",
            name=f"Position {line_num}: Netto = Menge x Preis ± Zu-/Abschläge",
            present=False,
            value=f"Netto={line_net}, erwartet={expected}",
            required=False,
        ))
