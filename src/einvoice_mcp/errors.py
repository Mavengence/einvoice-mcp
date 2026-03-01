"""Custom exceptions with German error messages."""


class EInvoiceError(Exception):
    """Base exception for e-invoice operations."""

    def __init__(self, message: str, message_de: str | None = None) -> None:
        super().__init__(message)
        self.message_de = message_de or message


class KoSITConnectionError(EInvoiceError):
    """KoSIT validator is unreachable."""

    def __init__(self, detail: str = "") -> None:
        msg = f"KoSIT validator unreachable: {detail}" if detail else "KoSIT validator unreachable"
        msg_de = (
            f"Fehler: KoSIT-Validator nicht erreichbar. {detail}"
            if detail
            else "Fehler: KoSIT-Validator nicht erreichbar. Bitte prüfen Sie die Verbindung."
        )
        super().__init__(msg, msg_de)


class KoSITValidationError(EInvoiceError):
    """KoSIT validation processing failed."""

    def __init__(self, detail: str = "") -> None:
        msg = f"KoSIT validation failed: {detail}" if detail else "KoSIT validation failed"
        msg_de = (
            f"Fehler: KoSIT-Validierung fehlgeschlagen. {detail}"
            if detail
            else "Fehler: KoSIT-Validierung fehlgeschlagen."
        )
        super().__init__(msg, msg_de)


class InvoiceGenerationError(EInvoiceError):
    """Error during invoice XML/PDF generation."""

    def __init__(self, detail: str = "") -> None:
        msg = f"Invoice generation failed: {detail}" if detail else "Invoice generation failed"
        msg_de = (
            f"Fehler: Rechnungserstellung fehlgeschlagen. {detail}"
            if detail
            else "Fehler: Rechnungserstellung fehlgeschlagen."
        )
        super().__init__(msg, msg_de)


class InvoiceParsingError(EInvoiceError):
    """Error parsing invoice XML or PDF."""

    def __init__(self, detail: str = "") -> None:
        msg = f"Invoice parsing failed: {detail}" if detail else "Invoice parsing failed"
        msg_de = (
            f"Fehler: Rechnung konnte nicht gelesen werden. {detail}"
            if detail
            else "Fehler: Rechnung konnte nicht gelesen werden."
        )
        super().__init__(msg, msg_de)
