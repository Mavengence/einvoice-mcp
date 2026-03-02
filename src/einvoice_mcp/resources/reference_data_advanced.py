"""Advanced reference resources (Leitweg-ID, tax category decision tree)."""

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
