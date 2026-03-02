"""Enumerations and constants for invoice models."""

from enum import StrEnum


class InvoiceProfile(StrEnum):
    XRECHNUNG = "XRECHNUNG"
    ZUGFERD_EN16931 = "ZUGFERD_EN16931"
    ZUGFERD_BASIC = "ZUGFERD_BASIC"
    ZUGFERD_EXTENDED = "ZUGFERD_EXTENDED"


class TaxCategory(StrEnum):
    S = "S"  # Standard rate
    Z = "Z"  # Zero rated
    E = "E"  # Exempt
    AE = "AE"  # Reverse charge
    K = "K"  # Intra-community supply
    G = "G"  # Export outside EU
    O = "O"  # Not subject to VAT  # noqa: E741
    L = "L"  # Canary Islands
    M = "M"  # Ceuta and Melilla


# Valid EN 16931 invoice type codes
VALID_TYPE_CODES = frozenset({"380", "381", "384", "389", "875", "876", "877"})

# UN/CEFACT UNTDID 4461 payment means codes used in EN 16931
VALID_PAYMENT_MEANS_CODES = frozenset(
    {
        "1",
        "10",
        "20",
        "30",
        "31",
        "42",
        "48",
        "49",
        "57",
        "58",
        "59",
        "97",
        "ZZZ",  # Mutually defined
    }
)
