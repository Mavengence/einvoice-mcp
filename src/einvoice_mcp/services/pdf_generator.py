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
    header_data = [
        ["RECHNUNG", "", f"Nr. {data.invoice_id}"],
        ["", "", f"Datum: {data.issue_date.isoformat()}"],
    ]
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
    elements.append(header_table)
    elements.append(Spacer(1, 10 * mm))

    # Seller / Buyer
    party_data = [
        ["Verkäufer:", "Käufer:"],
        [data.seller.name, data.buyer.name],
        [data.seller.address.street, data.buyer.address.street],
        [
            f"{data.seller.address.postal_code} {data.seller.address.city}",
            f"{data.buyer.address.postal_code} {data.buyer.address.city}",
        ],
    ]
    if data.seller.tax_id:
        party_data.append([f"USt-IdNr.: {data.seller.tax_id}", ""])

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

    # Line items table
    items_header = ["Pos.", "Beschreibung", "Menge", "Einheit", "Einzelpreis", "USt %", "Netto"]
    items_data = [items_header]

    for idx, item in enumerate(data.items, 1):
        net = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
        items_data.append(
            [
                str(idx),
                item.description,
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

    # Totals
    net_total = data.total_net().quantize(Decimal("0.01"))
    tax_total = data.total_tax().quantize(Decimal("0.01"))
    gross_total = data.total_gross().quantize(Decimal("0.01"))

    totals_data = [
        ["", "Nettobetrag:", f"{net_total:.2f} {data.currency}"],
        ["", "Umsatzsteuer:", f"{tax_total:.2f} {data.currency}"],
        ["", "Gesamtbetrag:", f"{gross_total:.2f} {data.currency}"],
    ]
    totals_table = Table(totals_data, colWidths=[100 * mm, 35 * mm, 35 * mm])
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("FONTNAME", (1, 2), (-1, 2), "Helvetica-Bold"),
                ("LINEABOVE", (1, 2), (-1, 2), 1, colors.black),
            ]
        )
    )
    elements.append(totals_table)

    # Payment terms
    if data.payment_terms_days is not None:
        elements.append(Spacer(1, 8 * mm))
        terms_data = [[f"Zahlbar innerhalb von {data.payment_terms_days} Tagen netto."]]
        terms_table = Table(terms_data, colWidths=[170 * mm])
        terms_table.setStyle(TableStyle([("FONTSIZE", (0, 0), (-1, -1), 8)]))
        elements.append(terms_table)

    doc.build(elements)
    return buf.getvalue()
