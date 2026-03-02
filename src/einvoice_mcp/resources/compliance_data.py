"""Compliance rules and regulatory reference data."""

import json


def e_rechnung_pflichten() -> str:
    """Zeitplan der E-Rechnungspflichten in Deutschland.

    Enthält alle relevanten Stichtage von 2020 bis 2028 mit
    Rechtsgrundlagen und betroffenen Unternehmen.
    """
    return json.dumps(
        {
            "title": "E-Rechnungspflichten — Zeitplan Deutschland",
            "timeline": [
                {
                    "date": "2020-11-27",
                    "obligation": "E-Rechnung an Bundesbehörden (Pflicht)",
                    "basis": "E-Rechnungsverordnung (ERechV)",
                    "affected": "Alle Lieferanten der Bundesverwaltung",
                },
                {
                    "date": "2025-01-01",
                    "obligation": "E-Rechnung empfangen (alle B2B)",
                    "basis": "Wachstumschancengesetz / BMF 2024-11-15",
                    "affected": "Alle inländischen Unternehmen",
                },
                {
                    "date": "2027-01-01",
                    "obligation": "E-Rechnung senden (Umsatz > 800.000€)",
                    "basis": "Wachstumschancengesetz §14 UStG",
                    "affected": "Unternehmen mit Vorjahresumsatz > 800.000€",
                },
                {
                    "date": "2028-01-01",
                    "obligation": "E-Rechnung senden (alle Unternehmen)",
                    "basis": "Wachstumschancengesetz §14 UStG",
                    "affected": "Alle inländischen Unternehmen (B2B)",
                },
            ],
            "notes": [
                "E-Rechnungen müssen der EN 16931 entsprechen (XRechnung oder ZUGFeRD)",
                "Papierrechnungen und einfache PDF gelten ab 2025 nicht mehr als E-Rechnung",
                "B2C-Rechnungen sind von der Pflicht ausgenommen",
                "Kleinbetragsrechnungen (≤250€) sind ebenfalls ausgenommen",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def br_de_rules() -> str:
    """Deutsche Geschäftsregeln (BR-DE) für XRechnung 3.0.

    Referenz aller BR-DE-Regeln mit Beschreibung und Lösungshinweisen.
    """
    rules = [
        {
            "code": "BR-DE-1",
            "description": "Leitweg-ID (BT-10) muss vorhanden sein",
            "field": "buyer_reference / leitweg_id",
            "fix": "buyer_reference oder leitweg_id setzen",
        },
        {
            "code": "BR-DE-2",
            "description": "Käufer-Referenz (BT-10) ist Pflichtfeld",
            "field": "buyer_reference",
            "fix": "buyer_reference setzen (z.B. Leitweg-ID)",
        },
        {
            "code": "BR-DE-3",
            "description": ("Wenn Verkäufer nicht in DE ansässig: Steuervertreter (BG-11) Pflicht"),
            "field": "seller_tax_rep_name",
            "fix": (
                "seller_tax_rep_name, seller_tax_rep_street, "
                "seller_tax_rep_city, seller_tax_rep_country_code, "
                "seller_tax_rep_tax_id setzen"
            ),
        },
        {
            "code": "BR-DE-4",
            "description": ("Steuervertreter muss USt-IdNr. (BT-63) haben"),
            "field": "seller_tax_rep_tax_id",
            "fix": "seller_tax_rep_tax_id setzen (DE-USt-IdNr.)",
        },
        {
            "code": "BR-DE-5",
            "description": "Ansprechpartner des Verkäufers (BT-41) Pflicht",
            "field": "seller_contact_name",
            "fix": "seller_contact_name setzen",
        },
        {
            "code": "BR-DE-6",
            "description": "Telefonnummer des Verkäufers (BT-42) Pflicht",
            "field": "seller_contact_phone",
            "fix": "seller_contact_phone setzen",
        },
        {
            "code": "BR-DE-7",
            "description": "E-Mail des Verkäufers (BT-43) Pflicht",
            "field": "seller_contact_email",
            "fix": "seller_contact_email setzen",
        },
        {
            "code": "BR-DE-8",
            "description": "Lieferdatum (BT-72) Format muss YYYYMMDD sein",
            "field": "delivery_date",
            "fix": "Datum im Format YYYY-MM-DD setzen",
        },
        {
            "code": "BR-DE-9",
            "description": ("Rechnungsdatum (BT-2) Format muss YYYYMMDD sein"),
            "field": "issue_date",
            "fix": "issue_date im Format YYYY-MM-DD setzen",
        },
        {
            "code": "BR-DE-10",
            "description": ("Leistungszeitraum-Beginn (BT-73) Format muss YYYYMMDD sein"),
            "field": "service_period_start",
            "fix": "service_period_start im Format YYYY-MM-DD setzen",
        },
        {
            "code": "BR-DE-11",
            "description": ("Leistungszeitraum-Ende (BT-74) Format muss YYYYMMDD sein"),
            "field": "service_period_end",
            "fix": "service_period_end im Format YYYY-MM-DD setzen",
        },
        {
            "code": "BR-DE-13",
            "description": ("Fälligkeitsdatum (BT-9) Format muss YYYYMMDD sein"),
            "field": "due_date",
            "fix": "due_date im Format YYYY-MM-DD setzen",
        },
        {
            "code": "BR-DE-14",
            "description": (
                "Steuernummer (BT-32) oder USt-IdNr. (BT-31) des Verkäufers muss vorhanden sein"
            ),
            "field": "seller_tax_id / seller_tax_number",
            "fix": "seller_tax_id (DE...) oder seller_tax_number setzen",
        },
        {
            "code": "BR-DE-15",
            "description": "Zahlungsbedingungen (BT-20) Pflicht",
            "field": "payment_terms_text",
            "fix": "payment_terms_text setzen",
        },
        {
            "code": "BR-DE-16",
            "description": (
                "Elektronische Adresse des Verkäufers (BT-34) "
                "schemeID muss ein gültiger EAS-Code sein"
            ),
            "field": "seller_electronic_address_scheme",
            "fix": "Gültigen EAS-Code verwenden (z.B. EM, 9930, 0204)",
        },
        {
            "code": "BR-DE-17",
            "description": (
                "Lieferdatum (BT-72) oder Leistungszeitraum (BT-73/BT-74) muss vorhanden sein"
            ),
            "field": "delivery_date / service_period_start+end",
            "fix": "delivery_date ODER service_period_start/end setzen",
        },
        {
            "code": "BR-DE-18",
            "description": (
                "Zahlungsart (BT-81) muss angegeben werden; "
                "Codes: 10, 30, 42, 48, 49, 57, 58, 59, 97, ZZZ"
            ),
            "field": "payment_means_type_code",
            "fix": "payment_means_type_code setzen (Standard: 58)",
        },
        {
            "code": "BR-DE-19",
            "description": ("Zahlungsart (BT-81) muss ein in DE zulässiger Code sein"),
            "field": "payment_means_type_code",
            "fix": ("Zulässig: 10, 20, 30, 42, 48, 49, 57, 58, 59, 97, ZZZ"),
        },
        {
            "code": "BR-DE-20",
            "description": (
                "Maximal eine Zahlungsanweisung je Gruppe (Credit Transfer oder Direct Debit)"
            ),
            "field": "payment_means_type_code",
            "fix": "Nur eine Zahlungsart pro Rechnung verwenden",
        },
        {
            "code": "BR-DE-21",
            "description": ("Elektronische Adresse des Verkäufers (BT-34) muss vorhanden sein"),
            "field": "seller_electronic_address",
            "fix": "seller_electronic_address setzen (z.B. E-Mail)",
        },
        {
            "code": "BR-DE-22",
            "description": (
                "Elektronische Adresse des Käufers (BT-49) schemeID muss ein gültiger EAS-Code sein"
            ),
            "field": "buyer_electronic_address_scheme",
            "fix": "Gültigen EAS-Code verwenden (z.B. EM, 9930)",
        },
        {
            "code": "BR-DE-23",
            "description": "IBAN Pflicht bei SEPA-Überweisung (Code 58)",
            "field": "seller_iban",
            "fix": "seller_iban setzen (BT-84)",
        },
        {
            "code": "BR-DE-24",
            "description": ("Mandatsreferenz + Käufer-IBAN bei SEPA-Lastschrift (Code 59)"),
            "field": "mandate_reference_id + buyer_iban",
            "fix": "mandate_reference_id (BT-89) und buyer_iban (BT-91) setzen",
        },
        {
            "code": "BR-DE-25",
            "description": ("Gesamtbetrag (BT-112) muss >= 0 sein (keine negativen Rechnungen)"),
            "field": "grand_total",
            "fix": ("Für Gutschriften type_code=381 verwenden, nicht negative Beträge"),
        },
        {
            "code": "BR-DE-26",
            "description": (
                "Beide Steuerkennzeichen (BT-31 und BT-32) dürfen nicht gleichzeitig fehlen"
            ),
            "field": "seller_tax_id / seller_tax_number",
            "fix": "Mindestens seller_tax_id oder seller_tax_number setzen",
        },
    ]
    return json.dumps(rules, ensure_ascii=False, indent=2)


def skr04_mapping() -> str:
    """SKR04-Kontenzuordnung für häufige Rechnungsarten.

    Mapping von typischen Eingangsrechnungs-Kategorien zu
    SKR04-Konten (Standardkontenrahmen 04, DATEV).
    """
    return json.dumps(
        {
            "title": "SKR04 — Typische Kontenzuordnung für Eingangsrechnungen",
            "chart": "SKR04 (DATEV)",
            "note": "Nur als Orientierung — die exakte Zuordnung hängt vom "
            "individuellen Kontenplan des Unternehmens ab.",
            "mappings": [
                {
                    "category": "Büromaterial / Bürobedarf",
                    "account": "6815",
                    "description": "Bürobedarf",
                    "tax_rate": "19%",
                },
                {
                    "category": "IT-Dienstleistung / Software",
                    "account": "6570",
                    "description": "Fremdleistungen / IT-Dienstleistungen",
                    "tax_rate": "19%",
                },
                {
                    "category": "Beratung / Consulting",
                    "account": "6825",
                    "description": "Rechts- und Beratungskosten",
                    "tax_rate": "19%",
                },
                {
                    "category": "Miete / Büromiete",
                    "account": "6310",
                    "description": "Miete (unbewegliche Wirtschaftsgüter)",
                    "tax_rate": "19% oder 0%",
                },
                {
                    "category": "Telefon / Internet",
                    "account": "6805",
                    "description": "Telefon",
                    "tax_rate": "19%",
                },
                {
                    "category": "Reisekosten",
                    "account": "6670",
                    "description": "Reisekosten Arbeitnehmer",
                    "tax_rate": "19% / 7% / 0%",
                },
                {
                    "category": "Werbung / Marketing",
                    "account": "6600",
                    "description": "Werbekosten",
                    "tax_rate": "19%",
                },
                {
                    "category": "Porto / Versand",
                    "account": "6810",
                    "description": "Porto",
                    "tax_rate": "19% oder 0%",
                },
                {
                    "category": "Reparatur / Instandhaltung",
                    "account": "6470",
                    "description": "Reparaturen und Instandhaltung",
                    "tax_rate": "19%",
                },
                {
                    "category": "Versicherung",
                    "account": "6400",
                    "description": "Versicherungen",
                    "tax_rate": "0% (steuerbefreit)",
                },
                {
                    "category": "Strom / Gas / Wasser",
                    "account": "6325",
                    "description": "Gas, Strom, Wasser",
                    "tax_rate": "19%",
                },
                {
                    "category": "Wareneinkauf",
                    "account": "5000",
                    "description": "Einkauf Roh-, Hilfs- und Betriebsstoffe",
                    "tax_rate": "19% oder 7%",
                },
                {
                    "category": "Kfz-Kosten",
                    "account": "6520",
                    "description": "Kfz-Kosten",
                    "tax_rate": "19%",
                },
                {
                    "category": "Fortbildung / Schulung",
                    "account": "6830",
                    "description": "Fortbildungskosten",
                    "tax_rate": "19% oder 0%",
                },
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def skr03_mapping() -> str:
    """SKR03-Kontenzuordnung für häufige Rechnungsarten.

    Mapping von typischen Eingangsrechnungs-Kategorien zu
    SKR03-Konten (Standardkontenrahmen 03, DATEV).
    SKR03 ist der in Deutschland am häufigsten verwendete
    Kontenrahmen (Freiberufler, Einzelunternehmer, KMU).
    """
    return json.dumps(
        {
            "title": "SKR03 — Typische Kontenzuordnung für Eingangsrechnungen",
            "chart": "SKR03 (DATEV)",
            "note": "Nur als Orientierung — die exakte Zuordnung hängt vom "
            "individuellen Kontenplan des Unternehmens ab.",
            "mappings": [
                {
                    "category": "Büromaterial / Bürobedarf",
                    "account": "4930",
                    "description": "Bürobedarf",
                    "tax_rate": "19%",
                },
                {
                    "category": "IT-Dienstleistung / Software",
                    "account": "4964",
                    "description": "Aufwendungen für IT / EDV",
                    "tax_rate": "19%",
                },
                {
                    "category": "Beratung / Consulting",
                    "account": "4950",
                    "description": "Rechts- und Beratungskosten",
                    "tax_rate": "19%",
                },
                {
                    "category": "Miete / Büromiete",
                    "account": "4210",
                    "description": "Miete (unbewegliche Wirtschaftsgüter)",
                    "tax_rate": "19% oder 0%",
                },
                {
                    "category": "Telefon / Internet",
                    "account": "4920",
                    "description": "Telefon",
                    "tax_rate": "19%",
                },
                {
                    "category": "Reisekosten",
                    "account": "4660",
                    "description": "Reisekosten Arbeitnehmer",
                    "tax_rate": "19% / 7% / 0%",
                },
                {
                    "category": "Werbung / Marketing",
                    "account": "4600",
                    "description": "Werbekosten",
                    "tax_rate": "19%",
                },
                {
                    "category": "Porto / Versand",
                    "account": "4910",
                    "description": "Porto",
                    "tax_rate": "19% oder 0%",
                },
                {
                    "category": "Reparatur / Instandhaltung",
                    "account": "4260",
                    "description": "Reparaturen und Instandhaltung",
                    "tax_rate": "19%",
                },
                {
                    "category": "Versicherung",
                    "account": "4360",
                    "description": "Versicherungen",
                    "tax_rate": "0% (steuerbefreit)",
                },
                {
                    "category": "Strom / Gas / Wasser",
                    "account": "4240",
                    "description": "Gas, Strom, Wasser",
                    "tax_rate": "19%",
                },
                {
                    "category": "Wareneinkauf",
                    "account": "3400",
                    "description": "Wareneingang 19% Vorsteuer",
                    "tax_rate": "19%",
                },
                {
                    "category": "Wareneinkauf 7%",
                    "account": "3300",
                    "description": "Wareneingang 7% Vorsteuer",
                    "tax_rate": "7%",
                },
                {
                    "category": "Kfz-Kosten",
                    "account": "4510",
                    "description": "Kfz-Kosten",
                    "tax_rate": "19%",
                },
                {
                    "category": "Fortbildung / Schulung",
                    "account": "4945",
                    "description": "Fortbildungskosten",
                    "tax_rate": "19% oder 0%",
                },
                {
                    "category": "Bewirtung (abzugsfähig)",
                    "account": "4650",
                    "description": "Bewirtungskosten (70% abzugsfähig)",
                    "tax_rate": "19%",
                },
                {
                    "category": "Fremdleistungen",
                    "account": "4780",
                    "description": "Fremdarbeiten / Subunternehmer",
                    "tax_rate": "19%",
                },
            ],
        },
        ensure_ascii=False,
        indent=2,
    )


def credit_note_reasons() -> str:
    """Gutschrift-Gründe (Credit Note Reason Codes) nach EN 16931.

    Standardisierte Gründe für Gutschriften und Korrekturrechnungen
    mit deutschen Beschreibungen und Empfehlungen.
    """
    return json.dumps(
        {
            "title": "Gutschrift- und Korrektur-Gründe",
            "type_codes": {
                "381": "Gutschrift (Credit Note)",
                "384": "Korrekturrechnung (Corrected Invoice)",
            },
            "reasons": [
                {
                    "code": "1",
                    "reason_de": "Retoure / Rückgabe",
                    "reason_en": "Return of goods",
                    "type_code": "381",
                    "note": "Gesamte oder teilweise Rückgabe der Ware",
                },
                {
                    "code": "2",
                    "reason_de": "Preisänderung / Rabatt nachträglich",
                    "reason_en": "Price correction",
                    "type_code": "381",
                    "note": "Nachträglicher Rabatt oder Preisanpassung",
                },
                {
                    "code": "3",
                    "reason_de": "Mengenabweichung",
                    "reason_en": "Quantity difference",
                    "type_code": "381",
                    "note": "Liefermenge weicht von Rechnungsmenge ab",
                },
                {
                    "code": "4",
                    "reason_de": "Fehlerhafte Rechnungsdaten",
                    "reason_en": "Invoice data error",
                    "type_code": "384",
                    "note": "Falsche Adresse, USt-IdNr., oder andere Stammdaten",
                },
                {
                    "code": "5",
                    "reason_de": "Umsatzsteuer-Korrektur",
                    "reason_en": "Tax correction",
                    "type_code": "384",
                    "note": "Falscher Steuersatz oder -kategorie auf Originalrechnung",
                },
                {
                    "code": "6",
                    "reason_de": "Mängelrüge / Qualitätsmangel",
                    "reason_en": "Quality deficiency",
                    "type_code": "381",
                    "note": "Minderung wegen mangelhafter Leistung (§437 BGB)",
                },
                {
                    "code": "7",
                    "reason_de": "Doppelte Rechnungsstellung",
                    "reason_en": "Duplicate invoice",
                    "type_code": "381",
                    "note": "Vollständige Gutschrift der doppelt gestellten Rechnung",
                },
                {
                    "code": "8",
                    "reason_de": "Kulanz / Goodwill",
                    "reason_en": "Goodwill gesture",
                    "type_code": "381",
                    "note": "Freiwillige Gutschrift ohne rechtliche Verpflichtung",
                },
            ],
            "wichtig": [
                "Gutschrift (381) muss IMMER die Originalrechnungsnummer referenzieren (BT-25)",
                "Korrekturrechnung (384) ersetzt die fehlerhafte Rechnung vollständig",
                "Teilkorrekturen: Gutschrift (381) + neue Rechnung (380) ausstellen",
                "§14 Abs. 2 Satz 3 UStG: Berichtigung nur durch neues Dokument möglich",
            ],
        },
        ensure_ascii=False,
        indent=2,
    )
