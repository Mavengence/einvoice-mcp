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
    codes = {
        "_hinweis": (
            "Peppol EAS v9.5 — vollständige Liste. "
            "Für deutsche Unternehmen ist 'EM' (E-Mail) der Standard."
        ),
        # Empfohlene Codes für Deutschland
        "EM": "E-Mail-Adresse — STANDARD für deutsche Unternehmen",
        "0204": "Leitweg-ID (deutsche öffentliche Verwaltung)",
        "9930": "USt-IdNr. DE als elektronische Adresse",
        # Internationale Identifikatoren
        "0007": "Organisationskennung (DUNS)",
        "0060": "DUNS+4 Nummer",
        "0088": "EAN/GLN Location Code",
        "0199": "LEI (Legal Entity Identifier)",
        "0209": "GS1 Identification Keys",
        # EU-Nachbarländer (häufige Handelspartner)
        "0002": "SIRENE (Frankreich)",
        "0009": "SIRET (Frankreich)",
        "9957": "Französische USt-IdNr.",
        "0106": "Niederländische KvK (Handelskammer)",
        "0190": "Dutch Originator's Identification Number",
        "0217": "Niederländische KvK Niederlassungsnr.",
        "9944": "Niederländische USt-IdNr.",
        "0208": "Belgische Unternehmensnummer (KBO/BCE)",
        "0193": "UBL.BE Party Identifier (Belgien)",
        "9925": "Belgische USt-IdNr.",
        "9914": "Österreichische USt-IdNr.",
        "9915": "Österreichische Verwaltungskennz.",
        "0183": "Schweizer UID",
        "9927": "Schweizer USt-IdNr.",
        "0192": "Brønnøysund-Register (Norwegen)",
        "0151": "Australian Business Number (ABN)",
        # Italien
        "0201": "Codice Univoco (IT ipa)",
        "0202": "PEC-Adresse (Italien)",
        "0210": "Codice Fiscale (Italien)",
        "0211": "Partita IVA (Italien)",
        # Nordische / Baltische Länder
        "0037": "LY-tunnus (Finnland)",
        "0096": "Dänische Handelskammer (EDIRA)",
        "0184": "DIGSTORG (Dänemark)",
        "0191": "Estnisches Registers-Center",
        "0196": "Kennitala (Island)",
        "0198": "ERSTORG (Dänemark)",
        "0200": "Jurid. Kodas (Litauen)",
        "0212": "Finnische Organisations-ID",
        "0213": "Finnische USt-ID",
        "0215": "Net Service ID (Finnland)",
        "0216": "OVT-Code (Finnland)",
        "0218": "Einheitl. Registrierungsnr. (Lettland)",
        # Weitere EU/EWR USt-IdNr.
        "9920": "Spanische USt-IdNr.",
        "9922": "Andorra USt-IdNr.",
        "9923": "Albanische USt-IdNr.",
        "9924": "Bosnische USt-IdNr.",
        "9926": "Bulgarische USt-IdNr.",
        "9928": "Zyprische USt-IdNr.",
        "9929": "Tschechische USt-IdNr.",
        "9931": "Estnische USt-IdNr.",
        "9932": "Britische USt-IdNr.",
        "9933": "Griechische USt-IdNr.",
        "9934": "Kroatische USt-IdNr.",
        "9935": "Irische USt-IdNr.",
        "9936": "Liechtensteinische USt-IdNr.",
        "9937": "Litauische USt-IdNr.",
        "9938": "Luxemburgische USt-IdNr.",
        "9939": "Lettische USt-IdNr.",
        "9940": "Monegassische USt-IdNr.",
        "9941": "Montenegrinische USt-IdNr.",
        "9942": "Mazedonische USt-IdNr.",
        "9943": "Maltesische USt-IdNr.",
        "9945": "Polnische USt-IdNr.",
        "9946": "Portugiesische USt-IdNr.",
        "9947": "Rumänische USt-IdNr.",
        "9948": "Serbische USt-IdNr.",
        "9949": "Slowenische USt-IdNr.",
        "9950": "Slowakische USt-IdNr.",
        "9951": "San-Marinesische USt-IdNr.",
        "9952": "Türkische USt-IdNr.",
        "9953": "Vatikanische USt-IdNr.",
        "9959": "EIN (USA Employer Identification Number)",
        # Sonstige
        "0097": "FTI Ediforum Italia",
        "0130": "Europäische Kommission",
        "0135": "SIA Object Identifiers",
        "0142": "SECETI Object Identifiers",
        "0147": "Standard Company Code",
        "0154": "IČO (Tschechien)",
        "0158": "IČO Statistik (Tschechien)",
        "0170": "Teikoku Company Code (Japan)",
        "0177": "Odette International",
        "0188": "Corporate Number (Japan)",
        "0194": "KOIOS Open Technical Dictionary",
        "0195": "Singapore UEN",
        "0203": "eDelivery Network Participant ID",
        "0205": "CODDEST",
        "0221": "Japanese Qualified Invoice Issuer",
        "0225": "FRCTC Electronic Address (Frankreich)",
        "0230": "National e-Invoicing Framework (Malaysia)",
        "0235": "UAE Tax Identification Number",
        "0240": "Répertoire des personnes morales (Luxemburg)",
        "9910": "Ungarische USt-IdNr.",
        "9913": "Business Registers Network",
        "9918": "SWIFT/BIC",
        "9919": "Unternehmensregister-Kennziffer",
    }
    return json.dumps(codes, ensure_ascii=False, indent=2)


def reference_vatex_codes() -> str:
    """Steuerbefreiungsgründe (BT-121) — VATEX-Codes gemäß EN 16931.

    Codes für tax_exemption_reason_code, z.B. bei Steuerbefreiung,
    Reverse Charge, innergemeinschaftlicher Lieferung, Export.
    """
    return json.dumps(
        {
            "_hinweis": (
                "Diese Codes werden für BT-121 (tax_exemption_reason_code) verwendet, "
                "wenn tax_category S, E, AE, K, G, O, L, M oder ähnlich ist. "
                "Für Kategorie S (Standard-Steuersatz) ist kein Code nötig."
            ),
            "vatex-eu-ae": {
                "description": "Reverse Charge — Steuerschuldnerschaft des Leistungsempfängers",
                "tax_category": "AE",
                "legal_basis": "Art. 196 MwStSystRL / §13b UStG",
                "example": "IT-Dienstleistungen aus dem EU-Ausland",
            },
            "vatex-eu-d": {
                "description": "Innergemeinschaftlicher Fernverkauf (Distance Selling)",
                "tax_category": "K",
                "legal_basis": "Art. 33 MwStSystRL",
                "example": "Onlineverkauf an Privatpersonen in anderem EU-Land",
            },
            "vatex-eu-f": {
                "description": "Innergemeinschaftliche Lieferung",
                "tax_category": "K",
                "legal_basis": "Art. 138 MwStSystRL / §4 Nr. 1b UStG",
                "example": "Warenlieferung DE → FR an Unternehmer mit USt-IdNr.",
            },
            "vatex-eu-g": {
                "description": "Export / Ausfuhr in Drittland",
                "tax_category": "G",
                "legal_basis": "Art. 146/147 MwStSystRL / §4 Nr. 1a UStG",
                "example": "Warenlieferung DE → USA",
            },
            "vatex-eu-i": {
                "description": (
                    "Innergemeinschaftlicher Erwerb neuer Fahrzeuge"
                ),
                "tax_category": "K",
                "legal_basis": "Art. 138(2)(a) MwStSystRL",
                "example": "Neuwagen-Lieferung DE → AT",
            },
            "vatex-eu-j": {
                "description": "Margenbesteuerung — Kunstgegenstände / Sammlerstücke",
                "tax_category": "O",
                "legal_basis": "Art. 316 MwStSystRL / §25a UStG",
                "example": "Gebrauchtwarenhandel, Antiquitäten",
            },
            "vatex-eu-o": {
                "description": "Nicht steuerbar — außerhalb des Anwendungsbereichs der MwSt",
                "tax_category": "O",
                "legal_basis": "Art. 2 MwStSystRL",
                "example": "Schadensersatz, Mitgliedsbeiträge, echte Zuschüsse",
            },
            "vatex-eu-79-c": {
                "description": "Preisnachlass / Rabatt — nicht in Steuerbemessungsgrundlage",
                "tax_category": "E",
                "legal_basis": "Art. 79(c) MwStSystRL",
                "example": "Durchlaufende Posten, Preisnachlässe",
            },
            "vatex-eu-132": {
                "description": "Steuerbefreiung — Tätigkeiten im öffentlichen Interesse",
                "tax_category": "E",
                "legal_basis": "Art. 132 MwStSystRL / §4 Nr. 14/16/20-25 UStG",
                "example": "Medizin, Post, Kultur, Bildung, Soziales, Sport",
            },
            "vatex-eu-132-1a": {
                "description": "Steuerbefreiung — Postdienstleistungen",
                "tax_category": "E",
                "legal_basis": "Art. 132(1)(a) MwStSystRL / §4 Nr. 11b UStG",
                "example": "Universalpostdienst",
            },
            "vatex-eu-132-1b": {
                "description": "Steuerbefreiung — Krankenhausbehandlung / ärztliche Heilbehandlung",
                "tax_category": "E",
                "legal_basis": "Art. 132(1)(b) MwStSystRL / §4 Nr. 14 UStG",
                "example": "Krankenhausleistungen, ärztliche Behandlung",
            },
            "vatex-eu-132-1i": {
                "description": "Steuerbefreiung — Erziehung / Unterricht",
                "tax_category": "E",
                "legal_basis": "Art. 132(1)(i) MwStSystRL / §4 Nr. 21 UStG",
                "example": "Schulen, Hochschulen, Berufsbildung",
            },
            "vatex-eu-135": {
                "description": "Steuerbefreiung — Versicherungen und Finanzgeschäfte",
                "tax_category": "E",
                "legal_basis": "Art. 135 MwStSystRL / §4 Nr. 8/10/11 UStG",
                "example": "Versicherungsvermittlung, Kreditgewährung, Wertpapierhandel",
            },
            "vatex-eu-143": {
                "description": "Steuerbefreiung — Einfuhr bestimmter Gegenstände",
                "tax_category": "G",
                "legal_basis": "Art. 143 MwStSystRL",
                "example": "Steuerfreie Einfuhr mit anschließender ig. Lieferung",
            },
            "vatex-eu-148": {
                "description": "Steuerbefreiung — Lieferungen für Schiffe/Flugzeuge",
                "tax_category": "E",
                "legal_basis": "Art. 148 MwStSystRL / §8 UStG",
                "example": "Bordversorgung, Ausrüstung für Seeschiffe",
            },
            "vatex-eu-151": {
                "description": "Steuerbefreiung — diplomatische/konsularische Einrichtungen",
                "tax_category": "E",
                "legal_basis": "Art. 151 MwStSystRL / §4 Nr. 7 UStG",
                "example": "Lieferungen an Botschaften, NATO, UN",
            },
            "vatex-eu-309": {
                "description": "Reiseleistungen — Margenbesteuerung",
                "tax_category": "O",
                "legal_basis": "Art. 309 MwStSystRL / §25 UStG",
                "example": "Pauschalreisen, Reiseveranstalter",
            },
            "vatex-eu-136": {
                "description": "Steuerbefreiung — Wiederverkauf gebrauchter Gegenstände",
                "tax_category": "E",
                "legal_basis": "Art. 136 MwStSystRL",
                "example": "Weiterverkauf ohne Vorsteuerabzug",
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def example_line_items() -> str:
    """Praxisbeispiele für items_json — die häufigsten Szenarien.

    Zeigt korrekte JSON-Arrays für verschiedene Steuerszenarien.
    AI-Agenten können diese Beispiele als Vorlage verwenden.
    """
    return json.dumps(
        {
            "standard_19_prozent": {
                "beschreibung": "Standardrechnung mit 19% MwSt",
                "items": [
                    {
                        "description": "Webentwicklung",
                        "quantity": "40",
                        "unit_code": "HUR",
                        "unit_price": "120.00",
                        "tax_rate": "19.00",
                        "tax_category": "S",
                    },
                    {
                        "description": "Domain-Hosting (12 Monate)",
                        "quantity": "1",
                        "unit_code": "C62",
                        "unit_price": "59.88",
                        "tax_rate": "19.00",
                        "tax_category": "S",
                    },
                ],
            },
            "ermaessigt_7_prozent": {
                "beschreibung": "Ermäßigter Steuersatz 7% (Lebensmittel, Bücher, etc.)",
                "items": [
                    {
                        "description": "Fachbuch: Python für Data Engineers",
                        "quantity": "5",
                        "unit_code": "C62",
                        "unit_price": "49.90",
                        "tax_rate": "7.00",
                        "tax_category": "S",
                    },
                ],
            },
            "gemischte_steuersaetze": {
                "beschreibung": "Rechnung mit 19% und 7% Positionen",
                "items": [
                    {
                        "description": "IT-Beratung",
                        "quantity": "8",
                        "unit_code": "HUR",
                        "unit_price": "150.00",
                        "tax_rate": "19.00",
                        "tax_category": "S",
                    },
                    {
                        "description": "Schulungsunterlagen (Buch)",
                        "quantity": "10",
                        "unit_code": "C62",
                        "unit_price": "29.90",
                        "tax_rate": "7.00",
                        "tax_category": "S",
                    },
                ],
            },
            "reverse_charge_13b": {
                "beschreibung": "Reverse Charge (§13b UStG) — Bauleistungen",
                "hinweis": (
                    "tax_category='AE', tax_rate='0.00'. "
                    "Käufer und Verkäufer brauchen USt-IdNr. "
                    "Freitext: 'Steuerschuldnerschaft des Leistungsempfängers'"
                ),
                "items": [
                    {
                        "description": "Elektroinstallation Bürogebäude",
                        "quantity": "1",
                        "unit_code": "C62",
                        "unit_price": "15000.00",
                        "tax_rate": "0.00",
                        "tax_category": "AE",
                    },
                ],
            },
            "kleinunternehmer_19_ustg": {
                "beschreibung": "Kleinunternehmer (§19 UStG) — keine MwSt",
                "hinweis": (
                    "tax_category='E', tax_rate='0.00'. "
                    "tax_exemption_reason='Gemäß §19 UStG wird keine "
                    "Umsatzsteuer berechnet (Kleinunternehmerregelung).'"
                ),
                "items": [
                    {
                        "description": "Grafikdesign Logo",
                        "quantity": "1",
                        "unit_code": "C62",
                        "unit_price": "800.00",
                        "tax_rate": "0.00",
                        "tax_category": "E",
                    },
                ],
            },
            "innergemeinschaftlich_k": {
                "beschreibung": (
                    "Innergemeinschaftliche Lieferung "
                    "(§4 Nr. 1b UStG) — steuerfreie EU-Lieferung"
                ),
                "hinweis": (
                    "tax_category='K', tax_rate='0.00'. "
                    "Käufer braucht gültige USt-IdNr. aus anderem EU-Land."
                ),
                "items": [
                    {
                        "description": "Maschine Typ X-500",
                        "quantity": "1",
                        "unit_code": "C62",
                        "unit_price": "25000.00",
                        "tax_rate": "0.00",
                        "tax_category": "K",
                    },
                ],
            },
            "mit_rabatt": {
                "beschreibung": "Position mit Zeilenrabatt (BG-27)",
                "items": [
                    {
                        "description": "Serverraum-Wartung (Jahresvertrag)",
                        "quantity": "12",
                        "unit_code": "MON",
                        "unit_price": "500.00",
                        "tax_rate": "19.00",
                        "tax_category": "S",
                        "allowances_charges": [
                            {
                                "charge": False,
                                "amount": "600.00",
                                "reason": "Jahresrabatt 10%",
                            }
                        ],
                    },
                ],
            },
            "einheitencodes": {
                "beschreibung": "Häufige UN/ECE Einheitencodes",
                "codes": {
                    "C62": "Stück (Standardeinheit)",
                    "HUR": "Stunde",
                    "DAY": "Tag",
                    "MON": "Monat",
                    "KGM": "Kilogramm",
                    "MTR": "Meter",
                    "LTR": "Liter",
                    "MTK": "Quadratmeter",
                    "SET": "Set / Satz",
                    "XPK": "Paket",
                    "H87": "Stück (alternativ)",
                },
            },
        },
        ensure_ascii=False,
        indent=2,
    )


def reference_currency_codes() -> str:
    """ISO 4217 Währungscodes — häufig verwendete Codes für deutschen/EU-Handel.

    Standard: EUR. Weitere Codes für Exporteure und internationale Rechnungen.
    """
    return json.dumps(
        {
            "EUR": "Euro (Standard)",
            "USD": "US-Dollar",
            "GBP": "Britisches Pfund",
            "CHF": "Schweizer Franken",
            "PLN": "Polnischer Zloty",
            "CZK": "Tschechische Krone",
            "SEK": "Schwedische Krone",
            "DKK": "Dänische Krone",
            "NOK": "Norwegische Krone",
            "HUF": "Ungarischer Forint",
            "RON": "Rumänischer Leu",
            "BGN": "Bulgarischer Lew",
            "HRK": "Kroatische Kuna",
            "TRY": "Türkische Lira",
            "JPY": "Japanischer Yen",
            "CNY": "Chinesischer Yuan",
            "CAD": "Kanadischer Dollar",
            "AUD": "Australischer Dollar",
            "INR": "Indische Rupie",
            "BRL": "Brasilianischer Real",
            "hinweis": (
                "Währung wird in BT-5 (Rechnungswährung) angegeben. "
                "Für EN 16931 muss die Währung ein gültiger ISO 4217 Code "
                "in Großbuchstaben sein (3 Zeichen)."
            ),
        },
        ensure_ascii=False,
        indent=2,
    )


def leitweg_id_format() -> str:
    """Leitweg-ID Format und Aufbau (BT-10).

    Struktur, Validierungsregeln und Beispiele fuer die Leitweg-ID,
    die bei XRechnung an oeffentliche Auftraggeber zwingend ist.
    """
    return json.dumps(
        {
            "titel": "Leitweg-ID — Format und Aufbau (BT-10)",
            "beschreibung": (
                "Die Leitweg-ID identifiziert den Rechnungsempfänger "
                "bei öffentlichen Auftraggebern (Bund, Länder, Kommunen). "
                "Sie ist Pflichtfeld (BT-10) in jeder XRechnung."
            ),
            "aufbau": {
                "schema": "Grobadressat-Feinadressat-Prüfziffer",
                "format": "[0-9]{2,12}-[0-9A-Z]{1,30}-[0-9]{2}",
                "beispiel": "04011000-12345-67",
                "teile": {
                    "grobadressat": {
                        "laenge": "2-12 Ziffern",
                        "beschreibung": (
                            "Identifiziert die übergeordnete Stelle "
                            "(Bund, Land, Kommune)"
                        ),
                        "beispiele": {
                            "bund": "991-00000-00 (Bundesministerien)",
                            "bayern": "09 (Freistaat Bayern)",
                            "nrw": "05 (Nordrhein-Westfalen)",
                            "berlin": "11 (Land Berlin)",
                        },
                    },
                    "feinadressat": {
                        "laenge": "1-30 Zeichen (Ziffern + Großbuchstaben)",
                        "beschreibung": (
                            "Identifiziert die konkrete Organisationseinheit "
                            "oder Kostenstelle"
                        ),
                    },
                    "pruefziffer": {
                        "laenge": "2 Ziffern",
                        "beschreibung": "Modulo-97-Prüfziffer (ISO 7064)",
                        "berechnung": (
                            "98 - (Grobadressat + Feinadressat als Zahl "
                            "mod 97)"
                        ),
                    },
                },
            },
            "validierung": {
                "regex": r"^\d{2,12}-[0-9A-Z]{1,30}-\d{2}$",
                "pflicht": "Nur bei XRechnung-Profil (nicht ZUGFeRD)",
                "hinweis": (
                    "Der MCP-Server prüft das Format automatisch "
                    "(LW-FMT advisory check). "
                    "Eine inhaltliche Prüfung der Leitweg-ID gegen "
                    "das E-Rechnungsportal ist nicht möglich."
                ),
            },
            "bezugsquellen": [
                "E-Rechnungsportal des Bundes: "
                "https://xrechnung.bund.de",
                "Rechnungsempfänger-Verzeichnis der Länder",
                "Kommunale Auftraggeber: "
                "beim jeweiligen Vergabeamt erfragen",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def tax_category_decision_tree() -> str:
    """Steuerkategorie-Entscheidungsbaum (BT-151).

    Szenario-basierter Leitfaden zur Wahl der richtigen
    Steuerkategorie in EN 16931.
    """
    return json.dumps(
        {
            "titel": "Steuerkategorie — Entscheidungsbaum (BT-151)",
            "kategorien": {
                "S": {
                    "name": "Standard-Besteuerung",
                    "steuersatz": "7% oder 19%",
                    "wann": [
                        "Normaler B2B-/B2C-Inlandsumsatz",
                        "Lieferung oder Leistung innerhalb Deutschlands",
                        "Steuersatz 19% (Regelsteuersatz) "
                        "oder 7% (ermäßigt)",
                    ],
                    "beispiel": (
                        "Beratungsleistung an deutschen Kunden, "
                        "Warenlieferung innerhalb DE"
                    ),
                },
                "Z": {
                    "name": "Nullsteuersatz",
                    "steuersatz": "0%",
                    "wann": [
                        "Gesetzlich mit 0% besteuerte Umsätze",
                        "In Deutschland selten (z.B. bestimmte "
                        "Photovoltaik-Anlagen §12 Abs. 3 UStG)",
                    ],
                    "beispiel": "Lieferung Photovoltaikanlage ≤30 kWp",
                },
                "E": {
                    "name": "Steuerbefreit (mit Vorsteuerabzug)",
                    "steuersatz": "0%",
                    "wann": [
                        "Umsätze nach §4 UStG (echte Befreiung)",
                        "Kleinunternehmer §19 UStG "
                        "(freiwillige Anwendung)",
                        "Medizinische Leistungen, "
                        "Bildungsleistungen, Versicherungen",
                    ],
                    "beispiel": (
                        "Arztleistung (§4 Nr. 14 UStG), "
                        "Kleinunternehmer-Rechnung"
                    ),
                    "pflichtfelder": [
                        "BT-120: Befreiungsgrund angeben",
                        "BT-121: VATEX-Code angeben",
                    ],
                },
                "AE": {
                    "name": "Reverse Charge (Umkehr der Steuerschuld)",
                    "steuersatz": "0%",
                    "wann": [
                        "Bauleistungen §13b Abs. 2 Nr. 4 UStG",
                        "Sonstige Leistungen §13b (Schrott, "
                        "CO2-Zertifikate)",
                        "Leistungen ausländischer Unternehmer "
                        "§13b Abs. 1 UStG",
                    ],
                    "beispiel": (
                        "Subunternehmer-Rechnung Bau, "
                        "IT-Dienstleistung aus USA an DE-Kunde"
                    ),
                    "pflichtfelder": [
                        "BT-31: Verkäufer USt-IdNr.",
                        "BT-48: Käufer USt-IdNr.",
                        "BT-120/121: Hinweis auf §13b UStG",
                    ],
                },
                "K": {
                    "name": "Innergemeinschaftliche Lieferung",
                    "steuersatz": "0%",
                    "wann": [
                        "Warenlieferung an Unternehmer in "
                        "anderem EU-Staat",
                        "Käufer hat gültige USt-IdNr.",
                        "Ware gelangt physisch in anderen "
                        "Mitgliedstaat",
                    ],
                    "beispiel": (
                        "Maschinenverkauf DE → AT, "
                        "Materialsendung DE → FR"
                    ),
                    "pflichtfelder": [
                        "BT-31: Verkäufer USt-IdNr.",
                        "BT-48: Käufer USt-IdNr. (anderes Land!)",
                        "BT-121: VATEX-EU-IC",
                    ],
                },
                "G": {
                    "name": "Ausfuhrlieferung (Drittland-Export)",
                    "steuersatz": "0%",
                    "wann": [
                        "Lieferung in Nicht-EU-Staat",
                        "Ausfuhrnachweis vorhanden "
                        "(Zoll-Ausgangsvermerk)",
                    ],
                    "beispiel": (
                        "Maschinenexport nach USA, "
                        "Warenlieferung in die Schweiz"
                    ),
                    "pflichtfelder": [
                        "BT-31: Verkäufer USt-IdNr.",
                        "BT-121: VATEX-EU-G",
                    ],
                },
                "O": {
                    "name": "Nicht steuerbar",
                    "steuersatz": "0%",
                    "wann": [
                        "Leistungsort nicht in Deutschland",
                        "Kein steuerbarer Umsatz "
                        "(z.B. Schadenersatz)",
                        "Margenbesteuerung §25 UStG "
                        "(Reiseleistungen)",
                    ],
                    "beispiel": (
                        "Pauschalreise §25 UStG, "
                        "Leistung mit Ort im Ausland"
                    ),
                },
                "L": {
                    "name": "IGIC (Kanarische Inseln)",
                    "steuersatz": "7% (Canarias)",
                    "wann": [
                        "Lieferung/Leistung auf den "
                        "Kanarischen Inseln"
                    ],
                    "beispiel": "Warenlieferung nach Teneriffa",
                },
                "M": {
                    "name": "IPSI (Ceuta/Melilla)",
                    "steuersatz": "variabel",
                    "wann": [
                        "Lieferung/Leistung in Ceuta "
                        "oder Melilla"
                    ],
                    "beispiel": "Warenlieferung nach Ceuta",
                },
            },
            "entscheidungslogik": [
                "1. Ist der Umsatz in Deutschland steuerbar? "
                "→ Nein → Kategorie O",
                "2. Ist der Umsatz steuerbefreit (§4 UStG)? "
                "→ Ja → Kategorie E",
                "3. Greift Reverse Charge (§13b UStG)? "
                "→ Ja → Kategorie AE",
                "4. Ist es eine innergemeinschaftliche Lieferung? "
                "→ Ja → Kategorie K",
                "5. Ist es eine Ausfuhrlieferung (Drittland)? "
                "→ Ja → Kategorie G",
                "6. Gilt der Nullsteuersatz (§12 Abs. 3)? "
                "→ Ja → Kategorie Z",
                "7. Standardfall → Kategorie S mit 19% oder 7%",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
