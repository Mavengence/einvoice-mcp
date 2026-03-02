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
    return json.dumps(
        [
            {
                "code": "BR-DE-1",
                "description": "Leitweg-ID (BT-10) muss vorhanden sein",
                "field": "leitweg_id / buyer_reference",
                "fix": "leitweg_id oder buyer_reference setzen",
            },
            {
                "code": "BR-DE-2",
                "description": "Käufer-Referenz (BT-10) Pflichtfeld",
                "field": "buyer_reference",
                "fix": "buyer_reference setzen",
            },
            {
                "code": "BR-DE-5",
                "description": "Ansprechpartner des Verkäufers Pflicht",
                "field": "seller_contact_name",
                "fix": "seller_contact_name setzen (BT-41)",
            },
            {
                "code": "BR-DE-6",
                "description": "Telefonnummer des Verkäufers Pflicht",
                "field": "seller_contact_phone",
                "fix": "seller_contact_phone setzen (BT-42)",
            },
            {
                "code": "BR-DE-7",
                "description": "E-Mail des Verkäufers Pflicht",
                "field": "seller_contact_email",
                "fix": "seller_contact_email setzen (BT-43)",
            },
            {
                "code": "BR-DE-15",
                "description": "Zahlungsbedingungen Pflicht",
                "field": "payment_terms_text",
                "fix": "payment_terms_text setzen (BT-20)",
            },
            {
                "code": "BR-DE-17",
                "description": "Lieferdatum oder Leistungszeitraum Pflicht",
                "field": "delivery_date / service_period_start+end",
                "fix": "delivery_date ODER service_period_start/end setzen",
            },
            {
                "code": "BR-DE-23",
                "description": "IBAN Pflicht bei SEPA-Überweisung (Code 58)",
                "field": "seller_iban",
                "fix": "seller_iban setzen (BT-84)",
            },
            {
                "code": "BR-DE-24",
                "description": "Mandatsreferenz + Käufer-IBAN bei SEPA-Lastschrift (Code 59)",
                "field": "mandate_reference_id + buyer_iban",
                "fix": "mandate_reference_id (BT-89) und buyer_iban (BT-91) setzen",
            },
        ],
        ensure_ascii=False,
        indent=2,
    )


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
