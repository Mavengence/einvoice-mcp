"""Generate visual PDF invoices and embed XML for ZUGFeRD."""

import io
import logging
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle

from einvoice_mcp.errors import InvoiceGenerationError
from einvoice_mcp.models import InvoiceData, InvoiceProfile

logger = logging.getLogger(__name__)


def generate_invoice_pdf(data: InvoiceData) -> bytes:
    """Generate a visual PDF invoice using reportlab."""
    try:
        return _build_pdf(data)
    except InvoiceGenerationError:
        raise
    except Exception as exc:
        logger.warning("PDF generation failed: %s", exc, exc_info=True)
        raise InvoiceGenerationError() from exc


_PROFILE_LEVEL_MAP = {
    InvoiceProfile.XRECHNUNG: "en16931",
    InvoiceProfile.ZUGFERD_EN16931: "en16931",
    InvoiceProfile.ZUGFERD_BASIC: "basic",
    InvoiceProfile.ZUGFERD_EXTENDED: "extended",
}


def embed_xml_in_pdf(
    pdf_bytes: bytes,
    xml_bytes: bytes,
    profile: InvoiceProfile = InvoiceProfile.ZUGFERD_EN16931,
) -> bytes:
    """Embed CII XML into a PDF to create a ZUGFeRD/Factur-X hybrid PDF."""
    try:
        from facturx import generate_from_binary

        level = _PROFILE_LEVEL_MAP.get(profile, "en16931")

        result: bytes = generate_from_binary(
            pdf_file=pdf_bytes,
            xml=xml_bytes,
            flavor="factur-x",
            level=level,
            check_xsd=False,
        )
        return result
    except ImportError as exc:
        raise InvoiceGenerationError("factur-x library not installed") from exc
    except Exception as exc:
        logger.warning("PDF/XML embedding failed: %s", exc, exc_info=True)
        raise InvoiceGenerationError() from exc


def _build_pdf(data: InvoiceData) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
    )

    elements: list[object] = []

    # Header
    doc_title = "GUTSCHRIFT" if data.type_code == "381" else "RECHNUNG"
    header_data = [
        [doc_title, "", f"Nr. {data.invoice_id}"],
        ["", "", f"Datum: {data.issue_date.isoformat()}"],
    ]
    if data.delivery_date:
        header_data.append(["", "", f"Lieferdatum: {data.delivery_date.isoformat()}"])
    elif data.service_period_start and data.service_period_end:
        period = f"{data.service_period_start.isoformat()} — {data.service_period_end.isoformat()}"
        header_data.append(["", "", f"Leistungszeitraum: {period}"])
    if data.due_date:
        header_data.append(["", "", f"Fällig: {data.due_date.isoformat()}"])
    header_table = Table(header_data, colWidths=[60 * mm, 50 * mm, 60 * mm])
    header_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (0, 0), 16),
                ("ALIGN", (2, 0), (2, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    # Preceding invoice reference (BT-25) for credit notes
    if data.type_code == "381" and data.preceding_invoice_number:
        header_data.append(
            ["", "", f"Bezug: {data.preceding_invoice_number}"]
        )

    elements.append(header_table)
    elements.append(Spacer(1, 10 * mm))

    # Seller / Buyer
    party_data = [
        ["Verkäufer:", "Käufer:"],
        [data.seller.name, data.buyer.name],
        [data.seller.address.street, data.buyer.address.street],
    ]
    if data.seller.address.street_2 or data.buyer.address.street_2:
        party_data.append([
            data.seller.address.street_2 or "",
            data.buyer.address.street_2 or "",
        ])
    if data.seller.address.street_3 or data.buyer.address.street_3:
        party_data.append([
            data.seller.address.street_3 or "",
            data.buyer.address.street_3 or "",
        ])
    party_data.append([
        f"{data.seller.address.postal_code} {data.seller.address.city}",
        f"{data.buyer.address.postal_code} {data.buyer.address.city}",
    ])
    if data.seller.tax_id:
        buyer_tax = f"USt-IdNr.: {data.buyer.tax_id}" if data.buyer.tax_id else ""
        party_data.append([f"USt-IdNr.: {data.seller.tax_id}", buyer_tax])
    elif data.seller.tax_number:
        party_data.append([f"Steuernummer: {data.seller.tax_number}", ""])

    # Contact info
    seller_contact = data.seller_contact_name or data.seller.contact_name
    buyer_contact = data.buyer_contact_name or data.buyer.contact_name
    if seller_contact or buyer_contact:
        party_data.append([
            f"Kontakt: {seller_contact}" if seller_contact else "",
            f"Kontakt: {buyer_contact}" if buyer_contact else "",
        ])
    seller_phone = data.seller_contact_phone or data.seller.contact_phone
    seller_email = data.seller_contact_email or data.seller.contact_email
    buyer_phone = data.buyer_contact_phone or data.buyer.contact_phone
    buyer_email = data.buyer_contact_email or data.buyer.contact_email
    if seller_phone or buyer_phone:
        party_data.append([
            f"Tel.: {seller_phone}" if seller_phone else "",
            f"Tel.: {buyer_phone}" if buyer_phone else "",
        ])
    if seller_email or buyer_email:
        party_data.append([
            seller_email or "",
            buyer_email or "",
        ])

    party_table = Table(party_data, colWidths=[85 * mm, 85 * mm])
    party_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(party_table)
    elements.append(Spacer(1, 10 * mm))

    # Delivery location (BT-70..BT-80)
    if data.delivery_party_name or data.delivery_street:
        delivery_data: list[list[str]] = [["Lieferort:"]]
        if data.delivery_party_name:
            delivery_data.append([data.delivery_party_name])
        if data.delivery_street:
            delivery_data.append([data.delivery_street])
        parts: list[str] = []
        if data.delivery_postal_code:
            parts.append(data.delivery_postal_code)
        if data.delivery_city:
            parts.append(data.delivery_city)
        if parts:
            delivery_data.append([" ".join(parts)])
        delivery_table = Table(delivery_data, colWidths=[170 * mm])
        delivery_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(delivery_table)
        elements.append(Spacer(1, 6 * mm))

    # Line items table
    items_header = ["Pos.", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "USt %", "Netto"]
    items_data = [items_header]

    for idx, item in enumerate(data.items, 1):
        net = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        desc = item.description
        if item.seller_item_id:
            desc = f"[{item.seller_item_id}] {desc}"
        items_data.append(
            [
                str(idx),
                desc,
                str(item.quantity),
                item.unit_code,
                f"{item.unit_price:.2f} {data.currency}",
                f"{item.tax_rate:.1f}%",
                f"{net:.2f} {data.currency}",
            ]
        )

    items_table = Table(
        items_data,
        colWidths=[12 * mm, 55 * mm, 18 * mm, 15 * mm, 25 * mm, 18 * mm, 27 * mm],
    )
    items_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f0f0")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    elements.append(items_table)
    elements.append(Spacer(1, 8 * mm))

    # Document-level allowances/charges
    if data.allowances_charges:
        ac_header = ["", "Zu-/Abschläge", ""]
        ac_data = [ac_header]
        for ac in data.allowances_charges:
            label = ac.reason or ("Zuschlag" if ac.charge else "Rabatt")
            sign = "+" if ac.charge else "-"
            ac_data.append(["", label, f"{sign}{ac.amount:.2f} {data.currency}"])
        ac_table = Table(ac_data, colWidths=[100 * mm, 35 * mm, 35 * mm])
        ac_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (1, 0), (1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ]
            )
        )
        elements.append(ac_table)
        elements.append(Spacer(1, 4 * mm))

    # Totals
    net_total = data.total_net().quantize(Decimal("0.01"))
    tax_basis = data.tax_basis().quantize(Decimal("0.01"))
    tax_total = data.total_tax().quantize(Decimal("0.01"))
    gross_total = data.total_gross().quantize(Decimal("0.01"))

    totals_data: list[list[str]] = [
        ["", "Zwischensumme Positionen:", f"{net_total:.2f} {data.currency}"],
    ]
    if data.allowances_charges:
        totals_data.append(
            ["", "Steuerbemessungsgrundlage:", f"{tax_basis:.2f} {data.currency}"]
        )
    totals_data.extend([
        ["", "Umsatzsteuer:", f"{tax_total:.2f} {data.currency}"],
        ["", "Gesamtbetrag:", f"{gross_total:.2f} {data.currency}"],
    ])
    last_row = len(totals_data) - 1
    totals_table = Table(totals_data, colWidths=[100 * mm, 35 * mm, 35 * mm])
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (1, last_row), (-1, last_row), "Helvetica-Bold"),
                ("LINEABOVE", (1, last_row), (-1, last_row), 1, colors.black),
            ]
        )
    )
    elements.append(totals_table)

    # Bank details
    if data.seller_iban:
        elements.append(Spacer(1, 8 * mm))
        bank_rows: list[list[str]] = [["Bankverbindung:", ""]]
        bank_rows.append(["IBAN:", data.seller_iban])
        if data.seller_bic:
            bank_rows.append(["BIC:", data.seller_bic])
        if data.seller_bank_name:
            bank_rows.append(["Bank:", data.seller_bank_name])
        bank_table = Table(bank_rows, colWidths=[30 * mm, 140 * mm])
        bank_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(bank_table)

    # Remittance information (BT-83) / Verwendungszweck
    if data.remittance_information:
        elements.append(Spacer(1, 4 * mm))
        ref_data = [["Verwendungszweck:", data.remittance_information]]
        ref_table = Table(ref_data, colWidths=[35 * mm, 135 * mm])
        ref_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                ]
            )
        )
        elements.append(ref_table)

    # Payment terms (BT-20) and Skonto
    payment_text = data.payment_terms_text
    if not payment_text and data.payment_terms_days is not None:
        payment_text = f"Zahlbar innerhalb von {data.payment_terms_days} Tagen netto."
    if (
        not payment_text
        and data.skonto_percent is not None
        and data.skonto_days is not None
    ):
        payment_text = (
            f"{data.skonto_percent:.1f}% Skonto bei Zahlung innerhalb von "
            f"{data.skonto_days} Tagen."
        )
    if payment_text:
        elements.append(Spacer(1, 8 * mm))
        terms_data = [[payment_text]]
        terms_table = Table(terms_data, colWidths=[170 * mm])
        terms_table.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8)]))
        elements.append(terms_table)

    # Invoice note (BT-22)
    if data.invoice_note:
        elements.append(Spacer(1, 6 * mm))
        note_data = [["Bemerkung:", data.invoice_note]]
        note_table = Table(note_data, colWidths=[30 * mm, 140 * mm])
        note_table.setStyle(
            TableStyle(
                [
                    ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ]
            )
        )
        elements.append(note_table)

    doc.build(elements)
    return buf.getvalue()
