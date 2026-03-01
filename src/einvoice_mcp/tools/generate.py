"""Generation tools for XRechnung XML and ZUGFeRD PDF invoices."""

import base64
import logging
from typing import Any

from einvoice_mcp.errors import EInvoiceError
from einvoice_mcp.models import InvoiceData
from einvoice_mcp.services.invoice_builder import build_xml
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.services.pdf_generator import embed_xml_in_pdf, generate_invoice_pdf

logger = logging.getLogger(__name__)


def _compute_totals(data: InvoiceData) -> dict[str, str]:
    """Compute invoice totals using per-group tax rounding (BR-CO-14).

    InvoiceData.total_tax() uses per-group rounding, matching the XML builder.
    """
    net_total = data.total_net()
    tax_total = data.total_tax()
    gross_total = data.total_gross()

    return {
        "net": str(net_total),
        "tax": str(tax_total),
        "gross": str(gross_total),
        "currency": data.currency,
    }


async def generate_xrechnung(data: InvoiceData, kosit: KoSITClient) -> dict[str, Any]:
    """Generate an XRechnung-compliant CII XML invoice.

    The generated XML is automatically validated against the KoSIT validator.

    Args:
        data: Structured invoice data.
        kosit: KoSIT client instance.

    Returns:
        Dictionary with xml_content, validation result, and totals.
    """
    try:
        xml_bytes = build_xml(data)
        xml_string = xml_bytes.decode("utf-8")
    except EInvoiceError as exc:
        return {"success": False, "error": exc.message_de}

    validation = None
    try:
        result = await kosit.validate(xml_bytes)
        validation = result.model_dump()
    except EInvoiceError as exc:
        logger.warning("Post-generation validation failed: %s", exc)
        validation = {"valid": False, "errors": [{"message": exc.message_de}], "warnings": []}

    return {
        "success": True,
        "xml_content": xml_string,
        "validation": validation,
        "totals": _compute_totals(data),
    }


async def generate_zugferd(data: InvoiceData, kosit: KoSITClient) -> dict[str, Any]:
    """Generate a ZUGFeRD hybrid PDF (visual PDF + embedded CII XML).

    Args:
        data: Structured invoice data.
        kosit: KoSIT client instance.

    Returns:
        Dictionary with base64-encoded PDF, validation result, and totals.
    """
    try:
        xml_bytes = build_xml(data)
    except EInvoiceError as exc:
        return {"success": False, "error": exc.message_de}

    try:
        pdf_bytes = generate_invoice_pdf(data)
    except EInvoiceError as exc:
        return {"success": False, "error": exc.message_de}

    try:
        hybrid_pdf = embed_xml_in_pdf(pdf_bytes, xml_bytes, profile=data.profile)
    except EInvoiceError as exc:
        return {"success": False, "error": exc.message_de}

    validation = None
    try:
        result = await kosit.validate(xml_bytes)
        validation = result.model_dump()
    except EInvoiceError as exc:
        logger.warning("Post-generation validation failed: %s", exc)
        validation = {"valid": False, "errors": [{"message": exc.message_de}], "warnings": []}

    pdf_base64 = base64.b64encode(hybrid_pdf).decode("ascii")

    return {
        "success": True,
        "pdf_base64": pdf_base64,
        "pdf_size_bytes": len(hybrid_pdf),
        "validation": validation,
        "totals": _compute_totals(data),
    }
