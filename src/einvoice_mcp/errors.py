"""Custom exceptions with German error messages.

SECURITY: User-facing messages (message_de) MUST NOT contain raw exception
details such as hostnames, IP addresses, file paths, or stack traces.
Internal details are logged via the 'detail' parameter but never surfaced
to callers.
"""

import logging

logger = logging.getLogger(__name__)


class EInvoiceError(Exception):
    """Base exception for e-invoice operations."""

    def __init__(self, message: str, message_de: str | None = None) -> None:
        super().__init__(message)
        self.message_de = message_de or message


class KoSITConnectionError(EInvoiceError):
    """KoSIT validator is unreachable."""

    def __init__(self, detail: str = "") -> None:
        msg = f"KoSIT validator unreachable: {detail}" if detail else "KoSIT validator unreachable"
        # Generic user message — never embed raw exception detail
        msg_de = "Fehler: KoSIT-Validator nicht erreichbar. Bitte prüfen Sie die Verbindung."
        if detail:
            logger.warning("KoSIT connection error: %s", detail)
        super().__init__(msg, msg_de)


class KoSITValidationError(EInvoiceError):
    """KoSIT validation processing failed."""

    def __init__(self, detail: str = "", *, controlled: bool = False) -> None:
        msg = f"KoSIT validation failed: {detail}" if detail else "KoSIT validation failed"
        # Only embed detail if explicitly marked as a controlled German message.
        # Raw exception strings (from httpx etc.) are NEVER surfaced to callers.
        if detail and controlled:
            msg_de = f"Fehler: KoSIT-Validierung fehlgeschlagen. {detail}"
        else:
            msg_de = "Fehler: KoSIT-Validierung fehlgeschlagen."
            if detail:
                logger.warning("KoSIT validation error: %s", detail)
        super().__init__(msg, msg_de)


class InvoiceGenerationError(EInvoiceError):
    """Error during invoice XML/PDF generation."""

    def __init__(self, detail: str = "") -> None:
        msg = f"Invoice generation failed: {detail}" if detail else "Invoice generation failed"
        # Generic user message — never embed raw exception detail
        msg_de = "Fehler: Rechnungserstellung fehlgeschlagen."
        if detail:
            logger.warning("Invoice generation error: %s", detail)
        super().__init__(msg, msg_de)


class InvoiceParsingError(EInvoiceError):
    """Error parsing invoice XML or PDF."""

    def __init__(self, detail: str = "", *, controlled: bool = False) -> None:
        msg = f"Invoice parsing failed: {detail}" if detail else "Invoice parsing failed"
        if detail and controlled:
            msg_de = f"Fehler: {detail}"
        else:
            msg_de = "Fehler: Rechnung konnte nicht gelesen werden."
            if detail:
                logger.warning("Invoice parsing error: %s", detail)
        super().__init__(msg, msg_de)
