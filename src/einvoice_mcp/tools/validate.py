"""Validation tools for XRechnung and ZUGFeRD invoices."""

import base64
import logging
from typing import Any

from defusedxml import ElementTree
from defusedxml.common import DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden

from einvoice_mcp.config import MAX_PDF_BASE64_SIZE, MAX_PDF_DECODED_SIZE, MAX_XML_SIZE
from einvoice_mcp.errors import EInvoiceError
from einvoice_mcp.services.kosit import KoSITClient
from einvoice_mcp.services.xml_parser import extract_xml_from_pdf

logger = logging.getLogger(__name__)


async def validate_xrechnung(xml_content: str, kosit: KoSITClient) -> dict[str, Any]:
    """Validate an XRechnung XML document against the KoSIT validator.

    Args:
        xml_content: The XRechnung XML as a string.
        kosit: KoSIT client instance.

    Returns:
        Validation result with errors, warnings, and profile info.
    """
    if not xml_content or not xml_content.strip():
        return {
            "valid": False,
            "errors": [{"message": "Fehler: XML-Inhalt darf nicht leer sein."}],
            "warnings": [],
        }

    if len(xml_content) > MAX_XML_SIZE:
        return {
            "valid": False,
            "errors": [{"message": "Fehler: XML-Inhalt überschreitet das Größenlimit (10 MB)."}],
            "warnings": [],
        }

    # Pre-screen: verify content is well-formed XML before sending to KoSIT.
    try:
        xml_bytes = xml_content.encode("utf-8")
        ElementTree.fromstring(xml_bytes)
    except (ElementTree.ParseError, UnicodeEncodeError):
        return {
            "valid": False,
            "errors": [{"message": "Fehler: Der Inhalt ist kein gültiges XML-Dokument."}],
            "warnings": [],
        }
    except (DTDForbidden, EntitiesForbidden, ExternalReferenceForbidden):
        return {
            "valid": False,
            "errors": [{"message": "Fehler: XML enthält unzulässige DTD- oder Entity-Referenzen."}],
            "warnings": [],
        }

    try:
        result = await kosit.validate(xml_bytes)
        return result.model_dump(mode="json")
    except EInvoiceError as exc:
        return {"valid": False, "errors": [{"message": exc.message_de}], "warnings": []}


async def validate_zugferd(pdf_base64: str, kosit: KoSITClient) -> dict[str, Any]:
    """Validate a ZUGFeRD PDF by extracting and validating its embedded XML.

    Args:
        pdf_base64: The ZUGFeRD PDF encoded as base64.
        kosit: KoSIT client instance.

    Returns:
        Validation result with errors, warnings, and profile info.
    """
    if not pdf_base64 or not pdf_base64.strip():
        return {
            "valid": False,
            "errors": [{"message": "Fehler: PDF-Base64-Inhalt darf nicht leer sein."}],
            "warnings": [],
        }

    if len(pdf_base64) > MAX_PDF_BASE64_SIZE:
        return {
            "valid": False,
            "errors": [{"message": "Fehler: PDF-Datei überschreitet das Größenlimit (50 MB)."}],
            "warnings": [],
        }

    try:
        pdf_bytes = base64.b64decode(pdf_base64, validate=True)
    except Exception:
        return {
            "valid": False,
            "errors": [{"message": "Fehler: Ungültige Base64-Kodierung der PDF-Datei."}],
            "warnings": [],
        }

    if len(pdf_bytes) > MAX_PDF_DECODED_SIZE:
        msg = "Fehler: Dekodierte PDF überschreitet das Größenlimit (50 MB)."
        return {"valid": False, "errors": [{"message": msg}], "warnings": []}

    try:
        xml_bytes = extract_xml_from_pdf(pdf_bytes)
        result = await kosit.validate(xml_bytes)
        return result.model_dump(mode="json")
    except EInvoiceError as exc:
        return {"valid": False, "errors": [{"message": exc.message_de}], "warnings": []}
