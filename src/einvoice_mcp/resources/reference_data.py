"""Reference code tables for AI agents."""

import json


def reference_type_codes() -> str:
    """Rechnungsart-Codes (BT-3) gemäß UNTDID 1001 / EN 16931.

    Zeigt alle gültigen Codes mit deutscher Beschreibung.
    """
    return json.dumps(
        {
            "380": "Handelsrechnung (Standard)",
            "381": "Gutschrift / Credit Note",
            "384": "Korrekturrechnung",
            "389": "Selbstfakturierte Rechnung (Self-billed)",
            "875": "Teilrechnung (Partial invoice)",
            "876": "Teilschlussrechnung (Partial final invoice)",
            "877": "Schlussrechnung (Final invoice)",
        },
        ensure_ascii=False,
        indent=2,
    )


def reference_payment_means_codes() -> str:
    """Zahlungsart-Codes (BT-81) gemäß UNTDID 4461 / EN 16931.

    Die häufigsten Codes für den deutschen Markt.
    """
    return json.dumps(
        {
            "1": "Nicht definiert (Instrument not defined)",
            "10": "Bar (Cash)",
            "20": "Scheck (Cheque)",
            "30": "Überweisung (Credit transfer)",
            "31": "Lastschrift (Debit transfer)",
            "42": "Zahlung an Bankkonto (Payment to bank account)",
            "48": "Kreditkarte (Bank card / credit card)",
            "49": "Lastschrift (Direct debit)",
            "57": "Dauerauftrag (Standing agreement)",
            "58": "SEPA-Überweisung (SEPA credit transfer) — STANDARD",
            "59": "SEPA-Lastschrift (SEPA direct debit)",
            "97": "Clearing zwischen Partnern (Clearing between partners)",
            "ZZZ": "Vereinbarte Zahlungsart (Mutually defined)",
        },
        ensure_ascii=False,
        indent=2,
    )


def reference_tax_categories() -> str:
    """Steuerkategorie-Codes (BT-151) gemäß UNTDID 5305 / EN 16931.

    Alle 9 gültigen Kategorien mit deutschen Erklärungen und typischen Steuersätzen.
    """
    return json.dumps(
        {
            "S": {
                "name": "Normaler Steuersatz (Standard rate)",
                "typical_rates": ["19.00", "7.00"],
                "usage": "Standardfall für B2B-Rechnungen in Deutschland",
            },
            "Z": {
                "name": "Nullsatz (Zero rated)",
                "typical_rates": ["0.00"],
                "usage": "Selten in DE — für spezielle EU-Regelungen",
            },
            "E": {
                "name": "Steuerbefreit (Exempt)",
                "typical_rates": ["0.00"],
                "usage": "§19 UStG (Kleinunternehmer), §4 UStG (steuerbefreite Umsätze)",
                "note": "BT-120 (ExemptionReason) ist Pflicht",
            },
            "AE": {
                "name": "Reverse Charge (§13b UStG)",
                "typical_rates": ["0.00"],
                "usage": "Steuerschuldnerschaft des Leistungsempfängers",
                "note": "BT-31 und BT-48 (USt-IdNr.) sind Pflicht",
            },
            "K": {
                "name": "Innergemeinschaftliche Lieferung (§4 Nr. 1b UStG)",
                "typical_rates": ["0.00"],
                "usage": "Lieferung an Unternehmer in anderen EU-Ländern",
                "note": "BT-48 (Käufer-USt-IdNr.) ist Pflicht",
            },
            "G": {
                "name": "Ausfuhrlieferung / Export (§4 Nr. 1a UStG)",
                "typical_rates": ["0.00"],
                "usage": "Lieferung in Drittländer (außerhalb EU)",
            },
            "O": {
                "name": "Nicht steuerbar (Not subject to VAT)",
                "typical_rates": ["0.00"],
                "usage": "Umsätze außerhalb des Steuergebiets",
            },
            "L": {
                "name": "IGIC (Kanarische Inseln)",
                "typical_rates": ["7.00"],
                "usage": "Kanarische Inseln Steuer",
            },
            "M": {
                "name": "IPSI (Ceuta und Melilla)",
                "typical_rates": ["4.00"],
                "usage": "Ceuta und Melilla Steuer",
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def reference_unit_codes() -> str:
    """Häufige Mengeneinheiten-Codes (BT-130) gemäß UN/ECE Recommendation 20.

    Die in deutschen Rechnungen am häufigsten verwendeten Einheiten.
    """
    return json.dumps(
        {
            "H87": "Stück (Piece)",
            "HUR": "Stunde (Hour)",
            "DAY": "Tag (Day)",
            "MON": "Monat (Month)",
            "ANN": "Jahr (Year)",
            "KGM": "Kilogramm",
            "GRM": "Gramm",
            "TNE": "Tonne",
            "MTR": "Meter",
            "KTM": "Kilometer",
            "MTK": "Quadratmeter",
            "LTR": "Liter",
            "MTQ": "Kubikmeter",
            "SET": "Satz / Set",
            "PR": "Paar (Pair)",
            "BX": "Karton / Box",
            "C62": "Einheit / one (generic unit)",
            "XPK": "Paket (Package)",
            "MIN": "Minute",
            "SEC": "Sekunde",
            "WEE": "Woche (Week)",
            "KWH": "Kilowattstunde",
            "MWH": "Megawattstunde",
        },
        ensure_ascii=False,
        indent=2,
    )


def reference_eas_codes() -> str:
    """Electronic Address Scheme Codes (BT-34-1/BT-49-1).

    Identifizierungsschema für elektronische Adressen in XRechnung.
    """
    return json.dumps(
        {
            "EM": "E-Mail-Adresse — STANDARD für deutsche Unternehmen",
            "9930": "USt-IdNr. als elektronische Adresse (DE + Nummer)",
            "0088": "EAN Location Number (GLN)",
            "0204": "Leitweg-ID (deutsche öffentliche Verwaltung)",
            "9906": "IT Codice Fiscale",
            "9925": "IT Partita IVA",
            "0007": "Organisationskennung (DUNS)",
            "0060": "DUNS+4 Nummer",
            "0190": "Dutch Originator's Identification Number",
            "0191": "Centre of Registers and Information Systems, Estonia",
            "0192": "Finnish OVT code",
            "0195": "Singapore UEN",
            "0196": "Icelandic kennitala",
            "0198": "Danish CVR number",
            "0199": "LEI (Legal Entity Identifier)",
            "0200": "Lithuanian juridinio asmens kodas",
            "0201": "LT KPV number for natural persons",
            "0208": "Belgian enterprise number (KBO/BCE)",
        },
        ensure_ascii=False,
        indent=2,
    )
