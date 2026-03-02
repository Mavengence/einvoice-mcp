"""Advanced reference resources — Leitweg-ID, tax tree, SEPA, CPV, BT-23, VAT exemptions."""

import json


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


def sepa_mandate_type_codes() -> str:
    """SEPA-Mandatstyp-Codes fuer Lastschriftverfahren.

    Referenzdaten fuer BT-89 (Mandatsreferenz) und die zugehoerigen
    Mandatstypen im SEPA-Lastschriftverfahren.
    """
    return json.dumps(
        {
            "titel": "SEPA-Mandatstyp-Codes (Lastschriftverfahren)",
            "kontext": (
                "Bei Zahlungsart 49 (SEPA Core Direct Debit) oder "
                "59 (SEPA B2B Direct Debit) muss ein SEPA-Mandat "
                "vorliegen. Die Mandatsreferenz wird in BT-89 angegeben."
            ),
            "mandatstypen": {
                "CORE": {
                    "name": "SEPA-Basislastschrift",
                    "payment_means_code": "49",
                    "zielgruppe": "B2C und B2B",
                    "widerrufsfrist": "8 Wochen (autorisiert), 13 Monate (unautorisiert)",
                    "vorlaufzeit_erst": "5 Bankarbeitstage (D-5)",
                    "vorlaufzeit_folge": "2 Bankarbeitstage (D-2)",
                },
                "B2B": {
                    "name": "SEPA-Firmenlastschrift",
                    "payment_means_code": "59",
                    "zielgruppe": "Nur B2B (Unternehmen)",
                    "widerrufsfrist": "Kein Widerrufsrecht",
                    "vorlaufzeit_erst": "1 Bankarbeitstag (D-1)",
                    "vorlaufzeit_folge": "1 Bankarbeitstag (D-1)",
                },
            },
            "sequenz_typen": {
                "FRST": "Erstlastschrift (erstes Einziehen unter neuem Mandat)",
                "RCUR": "Folgelastschrift (wiederkehrend)",
                "OOFF": "Einmallastschrift",
                "FNAL": "Letzte Lastschrift (Mandat wird danach beendet)",
            },
            "pflichtfelder_e_rechnung": {
                "BT-81": "PaymentMeansCode: 49 (Core) oder 59 (B2B)",
                "BT-89": "Mandatsreferenz (eindeutige Kennung, max. 35 Zeichen)",
                "BT-90": "Gläubiger-Identifikationsnummer (Creditor ID, DE...)",
                "BT-91": "IBAN des Zahlungspflichtigen (Käufer-IBAN)",
            },
            "glaeubiger_id": {
                "format": "DExxZZZ0nnnnnnnnnn",
                "laenge": "18 Zeichen",
                "beantragung": "Deutsche Bundesbank (https://www.glaeubiger-id.bundesbank.de)",
                "beispiel": "DE98ZZZ09999999999",
            },
            "hinweise": [
                "Mandatsreferenz + Gläubiger-ID müssen in der Pre-Notification angegeben werden",
                "Pre-Notification: 14 Tage vor Einzug (verkürzt auf 1 Tag per Vereinbarung)",
                "Mandat verfällt nach 36 Monaten ohne Einzug",
                "BT-89 und BT-91 sind BR-DE-24 Pflichtfelder bei Code 59",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def cpv_classification_codes() -> str:
    """Haeufige CPV-Codes fuer oeffentliche Vergaben (BT-158).

    Common Procurement Vocabulary (CPV) Codes, die bei
    XRechnung an oeffentliche Auftraggeber oft benoetigt werden.
    """
    return json.dumps(
        {
            "titel": "CPV-Klassifikationscodes (BT-158) — Öffentliche Vergabe",
            "beschreibung": (
                "Das CPV (Common Procurement Vocabulary) ist das "
                "EU-Standard-Klassifikationssystem für öffentliche "
                "Aufträge. Bei XRechnungen an öffentliche Auftraggeber "
                "kann eine Warenklassifikation (BT-158) gefordert sein."
            ),
            "schema_id": {
                "CPV": "Scheme Identifier für CPV",
                "UNSPSC": "Scheme Identifier für UNSPSC",
                "eClass": "Scheme Identifier für eCl@ss",
            },
            "haeufige_cpv_codes": {
                "IT und Software": {
                    "72000000": "IT-Dienste: Beratung, Software-Entwicklung",
                    "72200000": "Softwareprogrammierung und -beratung",
                    "72300000": "Datendienste",
                    "30200000": "Computeranlagen und Zubehör",
                    "48000000": "Softwarepaket und Informationssysteme",
                },
                "Beratung": {
                    "79400000": "Unternehmens- und Managementberatung",
                    "79410000": "Unternehmens- und Managementberatung",
                    "79200000": "Buchführung, Wirtschaftsprüfung, Steuerberatung",
                },
                "Bau": {
                    "45000000": "Bauarbeiten",
                    "45200000": "Komplett- oder Teilbauleistungen",
                    "45300000": "Bauinstallationsarbeiten",
                    "71300000": "Dienstleistungen von Ingenieurbüros",
                },
                "Büro und Verwaltung": {
                    "22000000": "Druckerzeugnisse",
                    "30100000": "Büromaschinen, -geräte und -bedarf",
                    "79500000": "Bürodienstleistungen",
                    "64100000": "Post- und Kurierdienste",
                },
                "Gesundheit": {
                    "85100000": "Dienstleistungen des Gesundheitswesens",
                    "33100000": "Medizinische Geräte",
                    "85140000": "Diverse Dienstleistungen im Gesundheitswesen",
                },
                "Facility Management": {
                    "90900000": "Reinigungs- und Hygienedienste",
                    "50700000": "Reparatur und Wartung von Gebäudeeinrichtungen",
                    "98300000": "Diverse Dienstleistungen",
                },
            },
            "e_rechnung_felder": {
                "BT-158": "Item classification identifier (CPV-Code)",
                "BT-158-1": "Scheme identifier: 'CPV'",
                "BT-158-2": "Scheme version identifier (optional)",
            },
            "hinweise": [
                "CPV-Codes haben 8 Ziffern + Prüfziffer (z.B. 72000000-5)",
                "In der E-Rechnung nur die 8 Ziffern ohne Prüfziffer angeben",
                "Öffentliche Auftraggeber können CPV als Pflichtfeld definieren",
                "UNSPSC ist international verbreitet, CPV EU-spezifisch",
                "eCl@ss (v5.1.4+) wird in der Industrie häufig verwendet",
                "Bei mehreren Klassifikationen: pro Position ein BT-158 Eintrag",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def business_process_identifiers() -> str:
    """Geschaeftsprozesstyp-Kennungen (BT-23).

    Standardisierte Prozessbezeichner fuer den E-Rechnungsaustausch,
    insbesondere Peppol BIS und XRechnung.
    """
    return json.dumps(
        {
            "titel": "Geschäftsprozesstyp-Kennungen (BT-23)",
            "beschreibung": (
                "BT-23 identifiziert den Geschäftsprozess, in dem "
                "die Rechnung ausgetauscht wird. Bei Peppol-Netzwerk "
                "und vielen öffentlichen Empfängern ist dies Pflicht."
            ),
            "standard_kennungen": {
                "peppol_billing": {
                    "id": "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
                    "name": "Peppol BIS Billing 3.0",
                    "verwendung": "Standard für Peppol-Netzwerk (EU-weit)",
                },
                "xrechnung": {
                    "id": "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0",
                    "name": "XRechnung (nutzt Peppol-Prozesskennung)",
                    "verwendung": (
                        "XRechnung verwendet dieselbe Prozesskennung "
                        "wie Peppol BIS Billing"
                    ),
                },
            },
            "wann_pflicht": [
                "Bei Versand über das Peppol-Netzwerk (immer Pflicht)",
                "Bei vielen öffentlichen Auftraggebern in DE",
                "Bei Nutzung von Access Points / Service Providern",
            ],
            "wann_optional": [
                "Direkter bilateraler Austausch (E-Mail, Portal-Upload)",
                "ZUGFeRD ohne Netzwerk-Routing",
                "Interne Rechnungen (Konzernverrechnungen)",
            ],
            "e_rechnung_feld": {
                "BT-23": "BusinessProcessType im XML-Header",
                "xpath": (
                    "rsm:ExchangedDocumentContext/"
                    "ram:BusinessProcessSpecifiedDocumentContextParameter/"
                    "ram:ID"
                ),
            },
            "hinweise": [
                "XRechnung setzt BT-23 nicht als Pflicht, empfiehlt aber die Angabe",
                "Im Peppol-Netzwerk wird BT-23 für das Routing verwendet",
                "Eigene Prozess-IDs sind möglich, aber nicht interoperabel",
                "Bei fehlendem BT-23 kann der Empfänger die Rechnung ablehnen",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def vat_exemption_reason_texts() -> str:
    """Deutsche USt-Befreiungsgrund-Texte (BT-120).

    Standardisierte Befreiungsgruende fuer die haeufigsten
    Steuerbefreiungen nach UStG mit passendem VATEX-Code (BT-121).
    """
    return json.dumps(
        {
            "titel": "USt-Befreiungsgründe — Texte für BT-120 und BT-121",
            "beschreibung": (
                "Bei steuerbefreiten Umsätzen (Kategorie E, AE, K, G) "
                "muss der Befreiungsgrund (BT-120) und der zugehörige "
                "Code (BT-121) angegeben werden."
            ),
            "befreiungsgruende": {
                "kleinunternehmer": {
                    "paragraph": "§19 UStG",
                    "bt_120": (
                        "Kein Ausweis von Umsatzsteuer, da Kleinunternehmer "
                        "gemäß §19 UStG."
                    ),
                    "bt_121": "VATEX-EU-O",
                    "tax_category": "E",
                    "hinweis": "Kein Vorsteuerabzug beim Empfänger möglich",
                },
                "innergemeinschaftliche_lieferung": {
                    "paragraph": "§4 Nr. 1b i.V.m. §6a UStG",
                    "bt_120": (
                        "Steuerfreie innergemeinschaftliche Lieferung "
                        "gemäß §4 Nr. 1b i.V.m. §6a UStG."
                    ),
                    "bt_121": "VATEX-EU-IC",
                    "tax_category": "K",
                    "hinweis": "USt-IdNr. beider Parteien Pflicht",
                },
                "ausfuhrlieferung": {
                    "paragraph": "§4 Nr. 1a i.V.m. §6 UStG",
                    "bt_120": (
                        "Steuerfreie Ausfuhrlieferung gemäß "
                        "§4 Nr. 1a i.V.m. §6 UStG."
                    ),
                    "bt_121": "VATEX-EU-G",
                    "tax_category": "G",
                    "hinweis": "Ausfuhrnachweis (Zoll) erforderlich",
                },
                "reverse_charge_13b_1": {
                    "paragraph": "§13b Abs. 1 UStG",
                    "bt_120": (
                        "Steuerschuldnerschaft des Leistungsempfängers "
                        "gemäß §13b Abs. 1 UStG."
                    ),
                    "bt_121": "VATEX-EU-AE",
                    "tax_category": "AE",
                    "hinweis": "Ausländischer Unternehmer an DE-Empfänger",
                },
                "reverse_charge_13b_2_4": {
                    "paragraph": "§13b Abs. 2 Nr. 4 UStG",
                    "bt_120": (
                        "Steuerschuldnerschaft des Leistungsempfängers "
                        "für Bauleistungen gemäß §13b Abs. 2 Nr. 4 UStG."
                    ),
                    "bt_121": "VATEX-EU-AE",
                    "tax_category": "AE",
                    "hinweis": "Bauleistungen an Bauleistende",
                },
                "medizinische_leistung": {
                    "paragraph": "§4 Nr. 14 UStG",
                    "bt_120": (
                        "Steuerbefreite Heilbehandlung im Bereich der "
                        "Humanmedizin gemäß §4 Nr. 14 UStG."
                    ),
                    "bt_121": "VATEX-EU-O",
                    "tax_category": "E",
                    "hinweis": "Nur ärztliche Heilbehandlungen, nicht Kosmetik",
                },
                "bildungsleistung": {
                    "paragraph": "§4 Nr. 21 UStG",
                    "bt_120": (
                        "Steuerbefreite Bildungsleistung gemäß "
                        "§4 Nr. 21 UStG."
                    ),
                    "bt_121": "VATEX-EU-O",
                    "tax_category": "E",
                    "hinweis": "Staatlich anerkannte Bildungseinrichtungen",
                },
                "versicherungsleistung": {
                    "paragraph": "§4 Nr. 10 UStG",
                    "bt_120": (
                        "Steuerbefreite Versicherungsleistung gemäß "
                        "§4 Nr. 10 UStG."
                    ),
                    "bt_121": "VATEX-EU-O",
                    "tax_category": "E",
                    "hinweis": "Versicherungsumsätze und Vermittlung",
                },
                "finanzdienstleistung": {
                    "paragraph": "§4 Nr. 8 UStG",
                    "bt_120": (
                        "Steuerbefreite Finanzdienstleistung gemäß "
                        "§4 Nr. 8 UStG."
                    ),
                    "bt_121": "VATEX-EU-O",
                    "tax_category": "E",
                    "hinweis": "Kreditgewährung, Wertpapierhandel",
                },
                "vermietung_wohnraum": {
                    "paragraph": "§4 Nr. 12 UStG",
                    "bt_120": (
                        "Steuerbefreite Vermietung und Verpachtung "
                        "von Grundstücken gemäß §4 Nr. 12 UStG."
                    ),
                    "bt_121": "VATEX-EU-O",
                    "tax_category": "E",
                    "hinweis": (
                        "Option zur Steuerpflicht möglich (§9 UStG) "
                        "bei Vermietung an Unternehmer"
                    ),
                },
            },
            "hinweise": [
                "BT-120 und BT-121 sind bei Kategorie E, AE, K, G Pflicht",
                "Freier Text in BT-120 erlaubt, Standardtexte empfohlen",
                "VATEX-Codes stammen aus der CEF VATEX Code List",
                "Bei Kombination mehrerer Befreiungen: pro Steuergruppe angeben",
                "Detaillierte VATEX-Codes: siehe Resource einvoice://reference/vatex-codes",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def uncl_5189_allowance_reason_codes() -> str:
    """UNCL 5189 Zu-/Abschlagsgrundcodes (BT-97/BT-98, BT-140/BT-141).

    Standardisierte Grund-Codes fuer Zu- und Abschlaege auf Dokument-
    und Positionsebene nach UN/CEFACT Code List 5189.
    """
    return json.dumps(
        {
            "titel": "UNCL 5189 — Zu-/Abschlagsgrund-Codes",
            "beschreibung": (
                "Code List 5189 (UN/CEFACT) definiert standardisierte "
                "Gründe für Zu- und Abschläge. Verwendet in BT-97/BT-98 "
                "(Dokumentebene) und BT-140/BT-141 (Positionsebene)."
            ),
            "abschlag_codes": {
                "41": "Bonusrabatt",
                "42": "Händlerrabatt",
                "60": "Herstellerrabatt",
                "62": "Sonderrabatt wegen Auftragsgröße",
                "63": "Frühzahlungsrabatt (Skonto)",
                "64": "Sonderrabatt",
                "65": "Produktionsrabatt",
                "66": "Treuepunkte-Rabatt",
                "67": "Katalograbatt",
                "68": "Premiumrabatt",
                "70": "Markenrabatt",
                "71": "Preisnachlass für defekte Ware",
                "88": "Materialzuschlag/-abschlag",
                "95": "Rabatt",
                "100": "Sondervereinbarung",
                "102": "Festgesetzter langfristiger Preis",
                "103": "Vorübergehende Vereinbarung",
                "104": "Standardrabatt",
                "105": "Preisänderung im Zeitraum",
            },
            "zuschlag_codes": {
                "AA": "Werbung",
                "AAA": "Telekommunikation",
                "ABL": "Zusätzliche Verpackung",
                "ADR": "Andere Dienstleistungen",
                "ADT": "Abholung",
                "FC": "Frachtkosten",
                "FI": "Finanzierungskosten",
                "LA": "Arbeitszuschlag",
                "PC": "Verpackung",
            },
            "e_rechnung_felder": {
                "dokument_abschlag": {
                    "BT-97": "Abschlagsgrund-Code (UNCL 5189)",
                    "BT-98": "Abschlagsgrund Freitext",
                },
                "dokument_zuschlag": {
                    "BT-104": "Zuschlagsgrund-Code (UNCL 7161)",
                    "BT-105": "Zuschlagsgrund Freitext",
                },
                "position_abschlag": {
                    "BT-140": "Positionsabschlagsgrund-Code (UNCL 5189)",
                    "BT-141": "Positionsabschlagsgrund Freitext",
                },
                "position_zuschlag": {
                    "BT-145": "Positionszuschlagsgrund-Code (UNCL 7161)",
                    "BT-146": "Positionszuschlagsgrund Freitext",
                },
            },
            "hinweise": [
                "Code 95 ('Rabatt') ist der generische Standardcode für Abschläge",
                "Bei Skonto: Code 63 + Prozentsatz in BT-20 kodieren",
                "Freitext (BT-98/BT-105) ist zusätzlich zum Code erlaubt",
                "Zuschlagscodes folgen UNCL 7161, nicht 5189",
                "In der E-Rechnung: Code + Text zusammen für Interoperabilität",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def payment_terms_templates() -> str:
    """Deutsche Zahlungsbedingungen-Vorlagen fuer BT-20.

    Standardisierte Texte und XRechnung-Kodierung fuer
    gaengige Zahlungsbedingungen im deutschen B2B-Geschaeft.
    """
    return json.dumps(
        {
            "titel": "Zahlungsbedingungen-Vorlagen (BT-20)",
            "standard_bedingungen": {
                "netto_sofort": {
                    "text": "Zahlbar sofort ohne Abzug.",
                    "tage": 0,
                },
                "netto_14": {
                    "text": "Zahlbar innerhalb 14 Tagen ohne Abzug.",
                    "tage": 14,
                },
                "netto_30": {
                    "text": "Zahlbar innerhalb 30 Tagen ohne Abzug.",
                    "tage": 30,
                },
                "netto_60": {
                    "text": "Zahlbar innerhalb 60 Tagen ohne Abzug.",
                    "tage": 60,
                },
            },
            "skonto_bedingungen": {
                "2_prozent_10_tage": {
                    "text": (
                        "2% Skonto bei Zahlung innerhalb 10 Tagen, "
                        "netto zahlbar innerhalb 30 Tagen."
                    ),
                    "bt_20_kodierung": (
                        "#SKONTO#TAGE=10#PROZENT=2.00#\n"
                        "#SKONTO#TAGE=30#PROZENT=0.00#"
                    ),
                },
                "3_prozent_7_tage": {
                    "text": (
                        "3% Skonto bei Zahlung innerhalb 7 Tagen, "
                        "2% bei Zahlung innerhalb 14 Tagen, "
                        "netto 30 Tage."
                    ),
                    "bt_20_kodierung": (
                        "#SKONTO#TAGE=7#PROZENT=3.00#\n"
                        "#SKONTO#TAGE=14#PROZENT=2.00#\n"
                        "#SKONTO#TAGE=30#PROZENT=0.00#"
                    ),
                },
            },
            "xrechnung_kodierung": {
                "format": "#SKONTO#TAGE=<n>#PROZENT=<p.pp>#",
                "mehrere_staffeln": (
                    "Mehrere Zeilen, jeweils mit "
                    "#SKONTO#...#, letzte Zeile mit PROZENT=0.00"
                ),
                "basis": (
                    "Optional: #SKONTO#TAGE=10#PROZENT=2.00"
                    "#BASISBETRAG=1190.00# (wenn abweichend)"
                ),
            },
            "hinweise": [
                "BT-20 ist Freitext, aber XRechnung empfiehlt #SKONTO#-Kodierung",
                "Skontofrist beginnt ab Rechnungsdatum (BT-2), nicht Lieferdatum",
                "Bei Abschlagsrechnungen: Skonto pro Teilrechnung separat",
                "PROZENT immer mit 2 Dezimalstellen (2.00, nicht 2)",
                "Zahlungsfrist (payment_terms_days) separat als BT-9 angeben",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
