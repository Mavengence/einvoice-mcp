"""Build CII XML invoices using drafthorse."""

import logging
from decimal import Decimal

from drafthorse.models.accounting import (
    ApplicableTradeTax,
    CategoryTradeTax,
    TradeAllowanceCharge,
)
from drafthorse.models.document import Document
from drafthorse.models.note import IncludedNote
from drafthorse.models.party import TaxRegistration
from drafthorse.models.payment import PaymentMeans, PaymentTerms
from drafthorse.models.references import AdditionalReferencedDocument
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

    # Business process type (BT-23)
    if data.business_process_type:
        doc.context.business_parameter.id = data.business_process_type

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
    if data.seller.address.street_2:
        doc.trade.agreement.seller.address.line_two = data.seller.address.street_2
    if data.seller.address.street_3:
        doc.trade.agreement.seller.address.line_three = data.seller.address.street_3
    doc.trade.agreement.seller.address.postcode = data.seller.address.postal_code
    doc.trade.agreement.seller.address.city_name = data.seller.address.city
    doc.trade.agreement.seller.address.country_id = data.seller.address.country_code

    # Seller trading name (BT-28)
    if data.seller.trading_name:
        doc.trade.agreement.seller.legal_organization.trade_name = (
            data.seller.trading_name
        )

    # Seller global ID (BT-29) — Handelsregisternummer or GLN
    if data.seller.registration_id:
        doc.trade.agreement.seller.global_id.add(
            ("0088", data.seller.registration_id)
        )

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
    if data.buyer.address.street_2:
        doc.trade.agreement.buyer.address.line_two = data.buyer.address.street_2
    if data.buyer.address.street_3:
        doc.trade.agreement.buyer.address.line_three = data.buyer.address.street_3
    doc.trade.agreement.buyer.address.postcode = data.buyer.address.postal_code
    doc.trade.agreement.buyer.address.city_name = data.buyer.address.city
    doc.trade.agreement.buyer.address.country_id = data.buyer.address.country_code

    # Buyer trading name (BT-45)
    if data.buyer.trading_name:
        doc.trade.agreement.buyer.legal_organization.trade_name = (
            data.buyer.trading_name
        )

    # Buyer global ID (BT-46) — GLN or other identifier
    if data.buyer.registration_id:
        doc.trade.agreement.buyer.global_id.add(
            ("0088", data.buyer.registration_id)
        )

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

    # Buyer contact (BT-44, BT-46, BT-47)
    if data.buyer_contact_name:
        doc.trade.agreement.buyer.contact.person_name = data.buyer_contact_name
    if data.buyer_contact_email:
        doc.trade.agreement.buyer.contact.email.address = data.buyer_contact_email
    if data.buyer_contact_phone:
        doc.trade.agreement.buyer.contact.telephone.number = data.buyer_contact_phone

    # Seller tax representative (BG-11, BT-62..BT-65)
    if data.seller_tax_representative:
        rep = doc.trade.agreement.seller_tax_representative_party
        rep.name = data.seller_tax_representative.name
        rep.address.line_one = data.seller_tax_representative.address.street
        if data.seller_tax_representative.address.street_2:
            rep.address.line_two = data.seller_tax_representative.address.street_2
        if data.seller_tax_representative.address.street_3:
            rep.address.line_three = data.seller_tax_representative.address.street_3
        rep.address.postcode = data.seller_tax_representative.address.postal_code
        rep.address.city_name = data.seller_tax_representative.address.city
        rep.address.country_id = data.seller_tax_representative.address.country_code
        if data.seller_tax_representative.tax_id:
            rep_tax = TaxRegistration()
            rep_tax.id = ("VA", data.seller_tax_representative.tax_id)
            rep.tax_registrations.add(rep_tax)

    # Buyer reference (BT-10) — required for XRechnung
    buyer_ref = data.buyer_reference or data.leitweg_id
    if buyer_ref:
        doc.trade.agreement.buyer_reference = buyer_ref

    # Purchase order reference (BT-13)
    if data.purchase_order_reference:
        doc.trade.agreement.buyer_order.issuer_assigned_id = (
            data.purchase_order_reference
        )

    # Sales order reference (BT-14)
    if data.sales_order_reference:
        doc.trade.agreement.seller_order.issuer_assigned_id = (
            data.sales_order_reference
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

    # Tender or lot reference (BT-17) — AdditionalReferencedDocument TypeCode=50
    if data.tender_or_lot_reference:
        tender_ref = AdditionalReferencedDocument()
        tender_ref.issuer_assigned_id = data.tender_or_lot_reference
        tender_ref.type_code = "50"
        doc.trade.agreement.additional_references.add(tender_ref)

    # Invoiced object identifier (BT-18) — AdditionalReferencedDocument TypeCode=130
    if data.invoiced_object_identifier:
        obj_ref = AdditionalReferencedDocument()
        obj_ref.issuer_assigned_id = data.invoiced_object_identifier
        obj_ref.type_code = "130"
        doc.trade.agreement.additional_references.add(obj_ref)

    # Preceding invoice reference (BT-25) — for credit notes (381)
    if data.preceding_invoice_number:
        doc.trade.settlement.invoice_referenced_document.issuer_assigned_id = (
            data.preceding_invoice_number
        )

    # Delivery location (BT-70..BT-80) — ShipToTradeParty
    if data.delivery_party_name or data.delivery_street:
        if data.delivery_party_name:
            doc.trade.delivery.ship_to.name = data.delivery_party_name
        if data.delivery_street:
            doc.trade.delivery.ship_to.address.line_one = data.delivery_street
        if data.delivery_city:
            doc.trade.delivery.ship_to.address.city_name = data.delivery_city
        if data.delivery_postal_code:
            doc.trade.delivery.ship_to.address.postcode = data.delivery_postal_code
        if data.delivery_country_code:
            doc.trade.delivery.ship_to.address.country_id = data.delivery_country_code

    # Despatch advice reference (BT-16)
    if data.despatch_advice_reference:
        doc.trade.delivery.despatch_advice.issuer_assigned_id = (
            data.despatch_advice_reference
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
        # Line item note (BT-127)
        if item.item_note:
            line_note = IncludedNote()
            line_note.content = item.item_note
            li.document.notes.add(line_note)

        li.product.name = item.description
        if item.seller_item_id:
            li.product.seller_assigned_id = item.seller_item_id
        if item.buyer_item_id:
            li.product.buyer_assigned_id = item.buyer_item_id
        if item.standard_item_id:
            li.product.global_id = (item.standard_item_scheme, item.standard_item_id)
        li.agreement.net.amount = item.unit_price
        li.agreement.net.basis_quantity._amount = str(Decimal("1"))
        li.agreement.net.basis_quantity._unit_code = item.unit_code

        # Gross price (BT-148) and price discount (BT-147)
        if item.item_gross_price is not None:
            li.agreement.gross.amount = item.item_gross_price
            li.agreement.gross.basis_quantity._amount = str(Decimal("1"))
            li.agreement.gross.basis_quantity._unit_code = item.unit_code
            if item.item_price_discount is not None:
                from drafthorse.models.tradelines import AllowanceCharge as LineAC
                price_ac = LineAC()
                price_ac.actual_amount = item.item_price_discount
                li.agreement.gross.charge.add(price_ac)

        # Item classification (BT-158)
        if item.item_classification_id:
            from drafthorse.models.product import ProductClassification
            cls = ProductClassification()
            cls.class_code = (
                item.item_classification_scheme,
                item.item_classification_version,
                item.item_classification_id,
            )
            li.product.classifications.add(cls)
        li.delivery.billed_quantity._amount = str(item.quantity)
        li.delivery.billed_quantity._unit_code = item.unit_code

        net_amount = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        li.settlement.monetary_summation.total_amount = net_amount

        # Line-level allowances/charges (BG-27/BG-28)
        for lac in item.allowances_charges:
            line_ac = TradeAllowanceCharge()
            line_ac.indicator = lac.charge
            line_ac.actual_amount = lac.amount
            if lac.reason:
                line_ac.reason = lac.reason
            li.settlement.allowance_charge.add(line_ac)

        # Line-level billing period (BT-134/BT-135)
        if item.line_period_start:
            li.settlement.period.start = item.line_period_start
        if item.line_period_end:
            li.settlement.period.end = item.line_period_end

        # Buyer accounting reference (BT-133)
        if item.buyer_accounting_reference:
            li.settlement.accounting_account.id = item.buyer_accounting_reference

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
    # SEPA direct debit (BG-19): buyer's IBAN
    if data.buyer_iban:
        pm.payer_account.iban = data.buyer_iban
    doc.trade.settlement.payment_means.add(pm)

    # Payment card (BG-18, BT-87/BT-88)
    if data.payment_card_pan:
        pm.financial_card.id = data.payment_card_pan
        if data.payment_card_holder:
            pm.financial_card.cardholder_name = data.payment_card_holder

    # Payee party (BG-10, BT-59..BT-61)
    if data.payee_name:
        doc.trade.settlement.payee.name = data.payee_name
        if data.payee_id:
            doc.trade.settlement.payee.global_id.add(("0088", data.payee_id))
        if data.payee_legal_registration_id:
            doc.trade.settlement.payee.legal_organization.id = (
                data.payee_legal_registration_id
            )

    # Remittance information (BT-83) / Verwendungszweck
    if data.remittance_information:
        doc.trade.settlement.payment_reference = (
            data.remittance_information
        )

    # Document-level allowances/charges (BG-20/BG-21)
    for ac in data.allowances_charges:
        tac = TradeAllowanceCharge()
        tac.indicator = ac.charge
        tac.actual_amount = ac.amount
        if ac.reason:
            tac.reason = ac.reason
        if ac.reason_code:
            tac.reason_code = ac.reason_code
        if ac.base_amount is not None:
            tac.basis_amount = ac.base_amount
        if ac.percentage is not None:
            tac.calculation_percent = ac.percentage

        cat_tax = CategoryTradeTax()
        cat_tax.type_code = "VAT"
        cat_tax.category_code = ac.tax_category.value
        cat_tax.rate_applicable_percent = ac.tax_rate
        tac.trade_tax.add(cat_tax)

        doc.trade.settlement.allowance_charge.add(tac)

    # Trade tax summary (line items + document-level allowances/charges)
    tax_groups: dict[tuple[str, Decimal], Decimal] = {}
    for item in data.items:
        key = (item.tax_category.value, item.tax_rate)
        net = item.quantity * item.unit_price
        tax_groups[key] = tax_groups.get(key, Decimal("0")) + net
    for ac in data.allowances_charges:
        key = (ac.tax_category.value, ac.tax_rate)
        if ac.charge:
            tax_groups[key] = tax_groups.get(key, Decimal("0")) + ac.amount
        else:
            tax_groups[key] = tax_groups.get(key, Decimal("0")) - ac.amount

    for (cat, rate), basis in tax_groups.items():
        trade_tax = ApplicableTradeTax()
        trade_tax.type_code = "VAT"
        trade_tax.category_code = cat
        trade_tax.rate_applicable_percent = rate
        trade_tax.basis_amount = basis
        trade_tax.calculated_amount = (basis * rate / Decimal("100")).quantize(Decimal("0.01"))
        # VAT exemption reason (BT-120/BT-121) — required for E, optional for AE/K/G/Z/O
        if data.tax_exemption_reason and cat in ("E", "AE", "K", "G", "Z", "O"):
            trade_tax.exemption_reason = data.tax_exemption_reason
        if data.tax_exemption_reason_code and cat in ("E", "AE", "K", "G", "Z", "O"):
            trade_tax.exemption_reason_code = data.tax_exemption_reason_code
        doc.trade.settlement.trade_tax.add(trade_tax)

    # Monetary summation
    # BR-CO-14: TaxTotalAmount MUST equal sum of ApplicableTradeTax.CalculatedAmount.
    net_total = data.total_net()
    allowance_total = data.total_allowances()
    charge_total = data.total_charges()
    tax_basis = data.tax_basis()
    tax_total = sum(
        (basis * rate / Decimal("100")).quantize(Decimal("0.01"))
        for (_, rate), basis in tax_groups.items()
    )
    gross_total = (tax_basis + tax_total).quantize(Decimal("0.01"))

    ms = doc.trade.settlement.monetary_summation
    ms.line_total = net_total
    ms.charge_total = charge_total
    ms.allowance_total = allowance_total
    # CurrencyField values require (amount, currencyID) tuple for CII conformance
    ms.tax_basis_total = (tax_basis, data.currency)
    ms.tax_total = (tax_total, data.currency)
    ms.grand_total = (gross_total, data.currency)
    ms.due_amount = gross_total

    # Payment terms (BT-20) and due date (BT-9)
    payment_text = data.payment_terms_text
    if not payment_text and data.payment_terms_days is not None:
        payment_text = f"Zahlbar innerhalb von {data.payment_terms_days} Tagen netto."
    # Auto-generate Skonto text if skonto_percent is set but no explicit text
    if data.skonto_percent is not None and data.skonto_days is not None and not payment_text:
        payment_text = (
            f"{data.skonto_percent:.1f}% Skonto bei Zahlung innerhalb von "
            f"{data.skonto_days} Tagen."
        )
    has_skonto = data.skonto_percent is not None and data.skonto_days is not None
    has_mandate = bool(data.mandate_reference_id)
    if payment_text or data.due_date or has_skonto or has_mandate:
        pt = PaymentTerms()
        if payment_text:
            pt.description = payment_text
        if data.due_date:
            pt.due = data.due_date
        # SEPA mandate reference (BT-89)
        if has_mandate:
            pt.debit_mandate_id = data.mandate_reference_id
        # Structured Skonto (PaymentDiscountTerms)
        if has_skonto:
            pt.discount_terms.calculation_percent = data.skonto_percent
            pt.discount_terms.basis_period_measure = (
                str(data.skonto_days),
                "DAY",
            )
            if data.skonto_base_amount is not None:
                pt.discount_terms.basis_amount = data.skonto_base_amount
        doc.trade.settlement.terms.add(pt)

    # Serialize without local XSD validation — KoSIT validates the full document.
    # drafthorse field ordering may not match strict XSD sequence expectations.
    xml_bytes: bytes = doc.serialize(schema=None)
    return xml_bytes
