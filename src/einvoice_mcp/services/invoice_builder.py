"""Build CII XML invoices using drafthorse."""

import logging
from decimal import Decimal

from drafthorse.models.accounting import ApplicableTradeTax
from drafthorse.models.document import Document
from drafthorse.models.note import IncludedNote
from drafthorse.models.party import TaxRegistration
from drafthorse.models.payment import PaymentMeans, PaymentTerms
from drafthorse.models.tradelines import LineItem as DHLineItem

from einvoice_mcp.errors import InvoiceGenerationError
from einvoice_mcp.models import InvoiceData, InvoiceProfile

logger = logging.getLogger(__name__)

GUIDELINE_MAP = {
    InvoiceProfile.XRECHNUNG: (
        "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0"
    ),
    InvoiceProfile.ZUGFERD_EN16931: "urn:cen.eu:en16931:2017",
    InvoiceProfile.ZUGFERD_BASIC: ("urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic"),
    # EXTENDED uses #conformant# (not #compliant#) per Factur-X spec —
    # it is a conformant extension of EN 16931, not a CIUS-compliant profile.
    InvoiceProfile.ZUGFERD_EXTENDED: (
        "urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended"
    ),
}


def build_xml(data: InvoiceData) -> bytes:
    """Build a CII XML document from InvoiceData."""
    try:
        return _build_document(data)
    except InvoiceGenerationError:
        raise
    except Exception as exc:
        logger.warning("XML build error: %s", exc, exc_info=True)
        raise InvoiceGenerationError() from exc


def _build_document(data: InvoiceData) -> bytes:
    doc = Document()

    # Context / guideline
    guideline = GUIDELINE_MAP.get(data.profile)
    if guideline:
        doc.context.guideline_parameter.id = guideline

    # Header
    doc.header.id = data.invoice_id
    doc.header.type_code = data.type_code
    doc.header.name = "GUTSCHRIFT" if data.type_code == "381" else "RECHNUNG"
    doc.header.issue_date_time = data.issue_date
    doc.header.languages.add("de")

    # Invoice note (BT-22)
    if data.invoice_note:
        note = IncludedNote()
        note.content = data.invoice_note
        doc.header.notes.add(note)

    # Seller
    doc.trade.agreement.seller.name = data.seller.name
    doc.trade.agreement.seller.address.line_one = data.seller.address.street
    doc.trade.agreement.seller.address.postcode = data.seller.address.postal_code
    doc.trade.agreement.seller.address.city_name = data.seller.address.city
    doc.trade.agreement.seller.address.country_id = data.seller.address.country_code

    if data.seller.tax_id:
        seller_tax = TaxRegistration()
        seller_tax.id = ("VA", data.seller.tax_id)
        doc.trade.agreement.seller.tax_registrations.add(seller_tax)

    # BT-32: Steuernummer (schemeID=FC) — alternative to USt-IdNr. per §14 Abs. 4 Nr. 2 UStG
    if data.seller.tax_number:
        seller_tax_num = TaxRegistration()
        seller_tax_num.id = ("FC", data.seller.tax_number)
        doc.trade.agreement.seller.tax_registrations.add(seller_tax_num)

    # Seller electronic address (BT-34) — mandatory for XRechnung 3.0
    if data.seller.electronic_address:
        doc.trade.agreement.seller.electronic_address.uri_ID = (
            data.seller.electronic_address_scheme,
            data.seller.electronic_address,
        )

    # Seller contact (BR-DE-5, BR-DE-7)
    if data.seller_contact_name:
        doc.trade.agreement.seller.contact.person_name = data.seller_contact_name
    if data.seller_contact_email:
        doc.trade.agreement.seller.contact.email.address = data.seller_contact_email
    if data.seller_contact_phone:
        doc.trade.agreement.seller.contact.telephone.number = data.seller_contact_phone

    # Buyer
    doc.trade.agreement.buyer.name = data.buyer.name
    doc.trade.agreement.buyer.address.line_one = data.buyer.address.street
    doc.trade.agreement.buyer.address.postcode = data.buyer.address.postal_code
    doc.trade.agreement.buyer.address.city_name = data.buyer.address.city
    doc.trade.agreement.buyer.address.country_id = data.buyer.address.country_code

    if data.buyer.tax_id:
        buyer_tax = TaxRegistration()
        buyer_tax.id = ("VA", data.buyer.tax_id)
        doc.trade.agreement.buyer.tax_registrations.add(buyer_tax)

    # Buyer electronic address (BT-49) — mandatory for XRechnung 3.0
    if data.buyer.electronic_address:
        doc.trade.agreement.buyer.electronic_address.uri_ID = (
            data.buyer.electronic_address_scheme,
            data.buyer.electronic_address,
        )

    # Buyer reference (BT-10) — required for XRechnung
    buyer_ref = data.buyer_reference or data.leitweg_id
    if buyer_ref:
        doc.trade.agreement.buyer_reference = buyer_ref

    # Purchase order reference (BT-13)
    if data.purchase_order_reference:
        doc.trade.agreement.buyer_order.issuer_assigned_id = (
            data.purchase_order_reference
        )

    # Contract reference (BT-12)
    if data.contract_reference:
        doc.trade.agreement.contract.issuer_assigned_id = (
            data.contract_reference
        )

    # Project reference (BT-11)
    if data.project_reference:
        doc.trade.agreement.procuring_project_type.id = (
            data.project_reference
        )
        doc.trade.agreement.procuring_project_type.name = ""

    # Preceding invoice reference (BT-25) — for credit notes (381)
    if data.preceding_invoice_number:
        doc.trade.settlement.invoice_referenced_document.issuer_assigned_id = (
            data.preceding_invoice_number
        )

    # Delivery date (BT-71) — §14 Abs. 4 Nr. 6 UStG
    if data.delivery_date:
        doc.trade.delivery.event.occurrence = data.delivery_date

    # Billing period (BT-73/BT-74) — service period
    if data.service_period_start:
        doc.trade.settlement.period.start = data.service_period_start
    if data.service_period_end:
        doc.trade.settlement.period.end = data.service_period_end

    # Line items
    for idx, item in enumerate(data.items, 1):
        li = DHLineItem()
        li.document.line_id = str(idx)
        li.product.name = item.description
        li.agreement.net.amount = item.unit_price
        li.agreement.net.basis_quantity._amount = str(Decimal("1"))
        li.agreement.net.basis_quantity._unit_code = item.unit_code
        li.delivery.billed_quantity._amount = str(item.quantity)
        li.delivery.billed_quantity._unit_code = item.unit_code

        net_amount = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        li.settlement.monetary_summation.total_amount = net_amount

        li.settlement.trade_tax.type_code = "VAT"
        li.settlement.trade_tax.category_code = item.tax_category.value
        li.settlement.trade_tax.rate_applicable_percent = item.tax_rate

        doc.trade.items.add(li)

    # Settlement
    doc.trade.settlement.currency_code = data.currency

    # Payment means (BT-81)
    pm = PaymentMeans()
    pm.type_code = data.payment_means_type_code
    if data.seller_iban:
        pm.payee_account.iban = data.seller_iban
        if data.seller_bank_name:
            pm.payee_account.account_name = data.seller_bank_name
    if data.seller_bic:
        pm.payee_institution.bic = data.seller_bic
    doc.trade.settlement.payment_means.add(pm)

    # Remittance information (BT-83) / Verwendungszweck
    if data.remittance_information:
        doc.trade.settlement.payment_reference = (
            data.remittance_information
        )

    # Trade tax summary
    tax_groups: dict[tuple[str, Decimal], Decimal] = {}
    for item in data.items:
        key = (item.tax_category.value, item.tax_rate)
        net = item.quantity * item.unit_price
        tax_groups[key] = tax_groups.get(key, Decimal("0")) + net

    for (cat, rate), basis in tax_groups.items():
        trade_tax = ApplicableTradeTax()
        trade_tax.type_code = "VAT"
        trade_tax.category_code = cat
        trade_tax.rate_applicable_percent = rate
        trade_tax.basis_amount = basis
        trade_tax.calculated_amount = (basis * rate / Decimal("100")).quantize(Decimal("0.01"))
        doc.trade.settlement.trade_tax.add(trade_tax)

    # Monetary summation
    # BR-CO-14: TaxTotalAmount MUST equal sum of ApplicableTradeTax.CalculatedAmount.
    # Derive tax_total from per-group calculated amounts (same rounding as above)
    # to avoid per-item vs per-group rounding divergence.
    net_total = data.total_net()
    tax_total = sum(
        (basis * rate / Decimal("100")).quantize(Decimal("0.01"))
        for (_, rate), basis in tax_groups.items()
    )
    gross_total = (net_total + tax_total).quantize(Decimal("0.01"))

    ms = doc.trade.settlement.monetary_summation
    ms.line_total = net_total
    ms.charge_total = Decimal("0.00")
    ms.allowance_total = Decimal("0.00")
    # CurrencyField values require (amount, currencyID) tuple for CII conformance
    ms.tax_basis_total = (net_total, data.currency)
    ms.tax_total = (tax_total, data.currency)
    ms.grand_total = (gross_total, data.currency)
    ms.due_amount = gross_total

    # Payment terms (BT-20)
    payment_text = data.payment_terms_text
    if not payment_text and data.payment_terms_days is not None:
        payment_text = f"Zahlbar innerhalb von {data.payment_terms_days} Tagen netto."
    if payment_text:
        pt = PaymentTerms()
        pt.description = payment_text
        doc.trade.settlement.terms.add(pt)

    # Serialize without local XSD validation — KoSIT validates the full document.
    # drafthorse field ordering may not match strict XSD sequence expectations.
    xml_bytes: bytes = doc.serialize(schema=None)
    return xml_bytes
