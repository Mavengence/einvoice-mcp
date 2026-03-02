"""Parsing tool for XRechnung XML and ZUGFeRD PDF invoices."""

import base64
import logging
from typing import Any

from einvoice_mcp.config import MAX_PDF_BASE64_SIZE, MAX_PDF_DECODED_SIZE, MAX_XML_SIZE
from einvoice_mcp.errors import EInvoiceError
from einvoice_mcp.services.xml_parser import extract_xml_from_pdf, parse_xml

logger = logging.getLogger(__name__)

_ALLOWED_FILE_TYPES = frozenset({"xml", "pdf"})


async def parse_einvoice(file_content: str, file_type: str = "xml") -> dict[str, Any]:
    """Parse an e-invoice (XML or PDF) and return structured data.

    Args:
        file_content: XML string or base64-encoded PDF.
        file_type: Either "xml" or "pdf".

    Returns:
        Parsed invoice data as dictionary.
    """
    file_type = file_type.lower().strip()

    if file_type not in _ALLOWED_FILE_TYPES:
        return {
            "success": False,
            "error": "Fehler: Unbekannter Dateityp. Erlaubt: 'xml' oder 'pdf'.",
        }

    if file_type == "pdf":
        return await _parse_pdf(file_content)
    return await _parse_xml(file_content)


async def _parse_xml(xml_content: str) -> dict[str, Any]:
    if not xml_content or not xml_content.strip():
        return {
            "success": False,
            "error": "Fehler: XML-Inhalt darf nicht leer sein.",
        }

    if len(xml_content) > MAX_XML_SIZE:
        return {
            "success": False,
            "error": "Fehler: XML-Inhalt überschreitet das Größenlimit (10 MB).",
        }

    try:
        xml_bytes = xml_content.encode("utf-8")
        invoice = parse_xml(xml_bytes)
        return {"success": True, "invoice": invoice.model_dump()}
    except EInvoiceError as exc:
        return {"success": False, "error": exc.message_de}


async def _parse_pdf(pdf_base64: str) -> dict[str, Any]:
    if not pdf_base64 or not pdf_base64.strip():
        return {
            "success": False,
            "error": "Fehler: PDF-Base64-Inhalt darf nicht leer sein.",
        }

    if len(pdf_base64) > MAX_PDF_BASE64_SIZE:
        return {
            "success": False,
            "error": "Fehler: PDF-Datei überschreitet das Größenlimit (50 MB).",
        }

    try:
        pdf_bytes = base64.b64decode(pdf_base64, validate=True)
    except Exception:
        return {
            "success": False,
            "error": "Fehler: Ungültige Base64-Kodierung der PDF-Datei.",
        }

    if len(pdf_bytes) > MAX_PDF_DECODED_SIZE:
        return {
            "success": False,
            "error": "Fehler: Dekodierte PDF überschreitet das Größenlimit (50 MB).",
        }

    try:
        xml_bytes = extract_xml_from_pdf(pdf_bytes)
        invoice = parse_xml(xml_bytes)
        return {"success": True, "invoice": invoice.model_dump()}
    except EInvoiceError as exc:
        return {"success": False, "error": exc.message_de}
