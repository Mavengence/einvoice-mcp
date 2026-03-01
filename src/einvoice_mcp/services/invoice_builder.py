"""Build CII XML invoices using drafthorse."""

import logging
from decimal import Decimal

from drafthorse.models.accounting import ApplicableTradeTax
from drafthorse.models.document import Document
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
        raise InvoiceGenerationError(str(exc)) from exc


def _build_document(data: InvoiceData) -> bytes:
    doc = Document()

    # Context / guideline
    guideline = GUIDELINE_MAP.get(data.profile)
    if guideline:
        doc.context.guideline_parameter.id = guideline

    # Header
    doc.header.id = data.invoice_id
    doc.header.type_code = "380"
    doc.header.name = "RECHNUNG"
    doc.header.issue_date_time = data.issue_date
    doc.header.languages.add("de")

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

        net_amount = item.quantity * item.unit_price
        li.settlement.monetary_summation.total_amount = net_amount

        li.settlement.trade_tax.type_code = "VAT"
        li.settlement.trade_tax.category_code = item.tax_category.value
        li.settlement.trade_tax.rate_applicable_percent = item.tax_rate

        doc.trade.items.add(li)

    # Settlement
    doc.trade.settlement.currency_code = data.currency

    # Payment means
    pm = PaymentMeans()
    pm.type_code = "58"  # SEPA credit transfer
    doc.trade.settlement.payment_means.add(pm)

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
    net_total = data.total_net()
    tax_total = data.total_tax().quantize(Decimal("0.01"))
    gross_total = (net_total + tax_total).quantize(Decimal("0.01"))

    ms = doc.trade.settlement.monetary_summation
    ms.line_total = net_total
    ms.charge_total = Decimal("0.00")
    ms.allowance_total = Decimal("0.00")
    ms.tax_basis_total = net_total
    ms.tax_total = tax_total
    ms.grand_total = gross_total
    ms.due_amount = gross_total

    # Payment terms
    if data.payment_terms_days:
        pt = PaymentTerms()
        pt.description = f"Zahlbar innerhalb von {data.payment_terms_days} Tagen."
        doc.trade.settlement.terms.add(pt)

    # Serialize without local XSD validation — KoSIT validates the full document.
    # drafthorse field ordering may not match strict XSD sequence expectations.
    xml_bytes: bytes = doc.serialize(schema=None)
    return xml_bytes
