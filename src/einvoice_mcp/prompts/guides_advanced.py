"""Advanced German e-invoice guidance prompts (tax scenarios, EU trade)."""


def reiseleistungen_25_guide() -> str:
    """Reiseleistungen nach §25 UStG (Margenbesteuerung).

    Leitfaden fuer Reisebueros und Veranstalter, die Reiseleistungen
    an Endverbraucher erbringen. Sonderregelung fuer die Berechnung
    der Umsatzsteuer auf die Marge.
    """
    return (
        "# Reiseleistungen - Margenbesteuerung (§25 UStG)\n\n"
        "## Anwendungsbereich\n"
        "- Reiseleistungen an **Endverbraucher** (B2C)\n"
        "- Reisebueros, Tour-Operatoren, Veranstalter\n"
        "- Bündelung von Reisevorleistungen "
        "(Hotel, Flug, Transfer)\n\n"
        "## Grundprinzip\n"
        "Die USt wird nur auf die **Marge** berechnet:\n"
        "- Marge = Reisepreis - Reisevorleistungen\n"
        "- Steuersatz: 19% auf die Marge\n"
        "- Kein Vorsteuerabzug fuer Reisevorleistungen\n\n"
        "## E-Rechnungs-Besonderheiten\n"
        "- `tax_category`: `S` (Standard) mit Satz auf Marge\n"
        "- `invoice_note`: Hinweis auf §25 UStG Pflicht\n"
        "- Kein separater Steuerausweis auf Endkundenrechnung\n"
        "- **Vorsteuerabzug beim Kunden nicht moeglich**\n\n"
        "## Pflichtangaben auf der Rechnung\n"
        "- Hinweis: 'Margenbesteuerung, Reiseleistung "
        "gemaess §25 UStG'\n"
        "- Gesamtpreis inkl. USt (keine Aufschluesselung)\n"
        "- Reiseleistende Firma mit USt-IdNr.\n\n"
        "## XRechnung-Umsetzung\n"
        "```json\n"
        "{\n"
        '  "invoice_note": "Sonderregelung fuer Reisebueros '
        "- Margenbesteuerung gemaess §25 UStG. "
        'Kein separater Steuerausweis.",\n'
        '  "items": [{\n'
        '    "description": "Pauschalreise Mallorca 7 Tage",\n'
        '    "quantity": "2",\n'
        '    "unit_price": "899.00",\n'
        '    "tax_rate": "0.00",\n'
        '    "tax_category": "O"\n'
        "  }]\n"
        "}\n"
        "```\n\n"
        "## Abgrenzung zu §25a UStG\n"
        "- §25 = Reiseleistungen (Pauschalreisen)\n"
        "- §25a = Differenzbesteuerung (Gebrauchtwarenhandel)\n"
        "- Beide: Marge als Bemessungsgrundlage\n"
        "- Unterschied: §25 nur fuer Reiseleistungen an "
        "Nichtunternehmer"
    )


def innergemeinschaftliche_lieferung_guide() -> str:
    """Innergemeinschaftliche Lieferung (§4 Nr. 1b UStG / §6a UStG).

    Leitfaden fuer steuerfreie Lieferungen an Unternehmer in
    anderen EU-Mitgliedstaaten.
    """
    return (
        "# Innergemeinschaftliche Lieferung "
        "(§4 Nr. 1b / §6a UStG)\n\n"
        "## Voraussetzungen fuer Steuerfreiheit\n"
        "1. Lieferung an einen **Unternehmer** in einem "
        "anderen EU-Mitgliedstaat\n"
        "2. Kaeufer hat **gueltige USt-IdNr.** "
        "eines anderen Mitgliedstaats\n"
        "3. Ware gelangt **physisch** in den anderen "
        "Mitgliedstaat (Gelangensbestaetigung)\n"
        "4. Kaeufer unterliegt der **Erwerbsbesteuerung** "
        "im Zielland\n\n"
        "## Pruefungspflichten des Verkaeufers\n"
        "- USt-IdNr. des Kaeufers pruefen (BZSt-Abfrage: "
        "https://evatr.bff-online.de)\n"
        "- Gelangensbestaetigung oder Alternativnachweise "
        "sichern (§17a UStDV)\n"
        "- Zusammenfassende Meldung (ZM) abgeben\n\n"
        "## E-Rechnungs-Pflichtfelder\n"
        "| Feld | BT-Code | Wert |\n"
        "|------|---------|------|\n"
        "| Steuerkategorie | BT-151 | `K` |\n"
        "| Steuersatz | BT-152 | `0.00` |\n"
        "| Befreiungsgrund | BT-120 | §4 Nr. 1b UStG |\n"
        "| Befreiungscode | BT-121 | `VATEX-EU-IC` |\n"
        "| Kaeufer USt-IdNr. | BT-48 | z.B. `ATU12345678` |\n"
        "| Verkaeufer USt-IdNr. | BT-31 | z.B. "
        "`DE123456789` |\n\n"
        "## XRechnung-Umsetzung\n"
        "```json\n"
        "{\n"
        '  "seller": {\n'
        '    "tax_id": "DE123456789"\n'
        "  },\n"
        '  "buyer": {\n'
        '    "tax_id": "ATU12345678"\n'
        "  },\n"
        '  "tax_exemption_reason": "Innergemeinschaftliche '
        'Lieferung gemaess §4 Nr. 1b UStG i.V.m. §6a UStG",\n'
        '  "tax_exemption_reason_code": "VATEX-EU-IC",\n'
        '  "items": [{\n'
        '    "description": "Industriemaschine Typ X",\n'
        '    "quantity": "1",\n'
        '    "unit_price": "25000.00",\n'
        '    "tax_rate": "0.00",\n'
        '    "tax_category": "K"\n'
        "  }]\n"
        "}\n"
        "```\n\n"
        "## Nachweispflichten (§17a UStDV)\n"
        "Alternativ zur Gelangensbestaetigung:\n"
        "- Frachtbrief (CMR) mit Empfangsbestaetigung\n"
        "- Spediteursbescheinigung\n"
        "- Versendungsbeleg (Tracking-Nachweis)\n\n"
        "## Compliance-Checks im MCP-Server\n"
        "Der `einvoice_check_compliance` prueft automatisch:\n"
        "- Steuerkategorie K -> USt-IdNr. beider Parteien\n"
        "- Steuersatz = 0% bei Kategorie K\n"
        "- Unterschiedliche Laender Verkaeufer/Kaeufer\n\n"
        "## Haeufige Fehler\n"
        "- Fehlende USt-IdNr. des Kaeufers (BT-48)\n"
        "- Ungueltige/abgelaufene USt-IdNr.\n"
        "- Gelangensbestaetigung nicht rechtzeitig beschafft\n"
        "- ZM nicht oder verspätet abgegeben"
    )


def dauerrechnung_guide() -> str:
    """Dauerrechnung / Monatsrechnung (wiederkehrende Leistungen).

    Leitfaden fuer wiederkehrende Rechnungen bei Miet-, Wartungs-,
    Abo- und Servicevertraegen.
    """
    return (
        "# Dauerrechnung / Monatsrechnung\n\n"
        "## Anwendungsfaelle\n"
        "- Mietvertraege (Buero, Maschinen, Fahrzeuge)\n"
        "- Wartungsvertraege und Service-Abonnements\n"
        "- Wiederkehrende Beratungsleistungen\n"
        "- Software-Lizenzen (monatlich/jaehrlich)\n\n"
        "## Rechtliche Grundlage\n"
        "- Eine Dauerrechnung gilt als **Rechnung** "
        "i.S.d. §14 UStG\n"
        "- Muss alle Pflichtangaben enthalten\n"
        "- Vorsteuerabzug ab Erhalt, nicht erst bei Zahlung\n"
        "- Gilt fuer den gesamten vereinbarten Zeitraum\n\n"
        "## E-Rechnungs-Besonderheiten\n"
        "- `service_period_start` / `service_period_end` "
        "(BT-73/BT-74) **zwingend**\n"
        "- `invoice_note`: Hinweis 'Dauerrechnung gueltig "
        "von ... bis ...'\n"
        "- Bei Preisaenderung: **Neue Dauerrechnung** "
        "erforderlich\n\n"
        "## XRechnung-Umsetzung\n"
        "```json\n"
        "{\n"
        '  "invoice_id": "DR-2026-001",\n'
        '  "service_period_start": "2026-01-01",\n'
        '  "service_period_end": "2026-12-31",\n'
        '  "invoice_note": "Dauerrechnung gueltig vom '
        "01.01.2026 bis 31.12.2026. "
        'Vorsteuerabzug fuer jeden Teilzeitraum moeglich.",\n'
        '  "items": [{\n'
        '    "description": "Bueroraum-Miete inkl. NK",\n'
        '    "quantity": "12",\n'
        '    "unit_code": "MON",\n'
        '    "unit_price": "1500.00",\n'
        '    "tax_rate": "19.00"\n'
        "  }]\n"
        "}\n"
        "```\n\n"
        "## Vorsteuerabzug\n"
        "- Empfaenger kann Vorsteuer **monatlich** abziehen\n"
        "- Zeitraum muss auf der Rechnung erkennbar sein\n"
        "- Bei jaehrlicher Rechnung: monatliche Aufteilung "
        "fuer UStVA\n\n"
        "## Aenderungen und Korrekturen\n"
        "- Preisaenderung: Neue Dauerrechnung ab Aenderungsdatum\n"
        "- Kuendigung: Letzte Rechnung mit End-Datum\n"
        "- Rueckwirkende Korrektur: 384 (Korrektur) auf "
        "alte Dauerrechnung"
    )


def steuernummer_vs_ustidnr_guide() -> str:
    """Steuernummer vs. USt-IdNr. — Welche verwenden?

    Entscheidungshilfe fuer BT-31 (USt-IdNr.) und BT-32
    (Steuernummer) bei der E-Rechnungserstellung.
    """
    return (
        "# Steuernummer vs. USt-IdNr. — Entscheidungshilfe\n\n"
        "## Ueberblick\n"
        "| | Steuernummer (BT-32) | USt-IdNr. (BT-31) |\n"
        "|---|---|---|\n"
        "| Format | z.B. 123/456/78901 | DE + 9 Ziffern |\n"
        "| Vergabe | Finanzamt | BZSt |\n"
        "| Pflicht | §14 UStG | EU-Handel |\n"
        "| XRechnung | schemeID='FC' | schemeID='VA' |\n\n"
        "## Wann welche verwenden?\n\n"
        "### USt-IdNr. (BT-31) bevorzugt bei:\n"
        "- Innergemeinschaftlichem Handel (Pflicht!)\n"
        "- B2B-Rechnungen allgemein\n"
        "- XRechnung an oeffentliche Auftraggeber\n"
        "- Wenn Datenschutz wichtig (Steuernummer = "
        "persoenlich)\n\n"
        "### Steuernummer (BT-32) nur bei:\n"
        "- Inlaendsgeschaeft ohne USt-IdNr.\n"
        "- Kleinunternehmer (§19 UStG) ohne USt-IdNr.\n"
        "- Freiberufler, die nur national taetig sind\n\n"
        "## BR-DE-26: Nicht beide gleichzeitig!\n"
        "XRechnung 3.0 verbietet die gleichzeitige Angabe "
        "von **beiden** (USt-IdNr. UND Steuernummer).\n"
        "Verwenden Sie immer nur **eine** der beiden.\n\n"
        "## E-Rechnungs-Umsetzung\n"
        "```json\n"
        "// Variante 1: USt-IdNr. (empfohlen)\n"
        "{\n"
        '  "seller": {\n'
        '    "tax_id": "DE123456789",\n'
        '    "tax_number": null\n'
        "  }\n"
        "}\n"
        "\n"
        "// Variante 2: Steuernummer\n"
        "{\n"
        '  "seller": {\n'
        '    "tax_id": null,\n'
        '    "tax_number": "123/456/78901"\n'
        "  }\n"
        "}\n"
        "```\n\n"
        "## Hinweise\n"
        "- USt-IdNr. Pruefung: "
        "https://evatr.bff-online.de\n"
        "- Steuernummern sind bundeslandspezifisch "
        "(Format variiert)\n"
        "- Bei Neugründung: USt-IdNr. beim BZSt beantragen"
    )


def schlussrechnung_nach_abschlag() -> str:
    """Schlussrechnung nach Abschlagsrechnungen (Typ 380 mit prepaid_amount).

    Leitfaden fuer die Erstellung einer Schlussrechnung nach einer
    oder mehreren Abschlagszahlungen (875/876/877 → 380).
    """
    return (
        "# Schlussrechnung nach Abschlagszahlungen\n\n"
        "## Ablauf\n"
        "1. Abschlagsrechnung(en) (TypeCode 875/876)\n"
        "2. Schlussrechnung (TypeCode 380) mit Verrechnung\n"
        "3. Nur der **Restbetrag** wird faellig\n\n"
        "## Pflichtangaben Schlussrechnung\n"
        "- Gesamtbetrag der Leistung (netto + brutto)\n"
        "- Bereits erhaltene Abschlagszahlungen "
        "(`prepaid_amount`)\n"
        "- Restbetrag = Gesamtbetrag - Abschlagszahlungen\n"
        "- Verweis auf vorherige Abschlagsrechnungen "
        "(`preceding_invoice_number`)\n\n"
        "## E-Rechnungs-Felder\n"
        "| Feld | BT-Code | Beschreibung |\n"
        "|------|---------|-------------|\n"
        "| prepaid_amount | BT-113 | Summe der Abschlaege |\n"
        "| preceding_invoice_number | BT-25 | Letzte "
        "Abschlagsrechnung |\n"
        "| type_code | BT-3 | `380` (Schlussrechnung) |\n"
        "| DuePayableAmount | BT-115 | Restbetrag |\n\n"
        "## XRechnung-Umsetzung\n"
        "```json\n"
        "{\n"
        '  "invoice_id": "RE-2026-FINAL-001",\n'
        '  "type_code": "380",\n'
        '  "preceding_invoice_number": "AB-2026-003",\n'
        '  "prepaid_amount": "15000.00",\n'
        '  "items": [{\n'
        '    "description": "Gesamtleistung Webentwicklung",\n'
        '    "quantity": "1",\n'
        '    "unit_price": "25000.00",\n'
        '    "tax_rate": "19.00"\n'
        "  }],\n"
        '  "invoice_note": "Schlussrechnung. Bereits gezahlt: '
        "15.000,00 EUR (AB-2026-001 bis AB-2026-003). "
        'Restbetrag: 14.750,00 EUR inkl. 19% USt."\n'
        "}\n"
        "```\n\n"
        "## Haeufige Fehler\n"
        "- prepaid_amount > Gesamtbrutto "
        "(Ueberzahlung ohne Korrektur)\n"
        "- Fehlender Verweis auf Abschlagsrechnungen\n"
        "- USt bereits in Abschlagsrechnungen ausgewiesen "
        "→ doppelte Besteuerung vermeiden\n"
        "- Abschlagsrechnungen nicht als 875/876 gekennzeichnet\n\n"
        "## USt-Behandlung\n"
        "- Abschlagszahlungen: USt entsteht bei Vereinnahmung "
        "(§13 Abs. 1 Nr. 1a UStG)\n"
        "- Schlussrechnung: Korrektur der USt auf den Gesamtbetrag\n"
        "- Endresultat: USt nur einmal auf den Gesamtbetrag"
    )


def proforma_rechnung_guide() -> str:
    """Proforma-Rechnung — Rechtliche Einordnung und E-Rechnungs-Behandlung.

    Leitfaden fuer vorläufige Rechnungen, die keine
    umsatzsteuerliche Wirkung haben.
    """
    return (
        "# Proforma-Rechnung\n\n"
        "## Was ist eine Proforma-Rechnung?\n"
        "- **Keine Rechnung** im Sinne von §14 UStG\n"
        "- Dient als Beleg fuer Zoll, Versicherung, "
        "Preisindikation\n"
        "- Kein Vorsteuerabzug moeglich\n"
        "- Keine Zahlungsaufforderung\n\n"
        "## Typische Anwendungsfaelle\n"
        "- Zollabfertigung bei Export/Import\n"
        "- Vorab-Preiskalkulation fuer Kunden\n"
        "- Warenbegleitung bei Musterlieferungen\n"
        "- Foerderantraege / Budgetfreigaben\n\n"
        "## E-Rechnungs-Behandlung\n"
        "- **Kein Standard-TypeCode** in EN 16931 vorgesehen\n"
        "- Empfehlung: Als **regulaere Rechnung** "
        "(TypeCode 380) erstellen\n"
        "- Deutlicher Hinweis im `invoice_note`:\n"
        '  "PROFORMA — Keine Rechnung im Sinne von §14 UStG. '
        'Kein Vorsteuerabzug moeglich."\n'
        "- Alternative: Ausserhalb des E-Rechnungssystems "
        "als PDF versenden\n\n"
        "## XRechnung-Umsetzung (wenn noetig)\n"
        "```json\n"
        "{\n"
        '  "invoice_id": "PF-2026-001",\n'
        '  "type_code": "380",\n'
        '  "invoice_note": "PROFORMA-RECHNUNG — Kein Dokument '
        "im Sinne von §14 UStG. Dient ausschliesslich zu "
        "Informationszwecken. Kein Vorsteuerabzug. "
        'Keine Zahlungsaufforderung.",\n'
        '  "items": [{\n'
        '    "description": "Muster: Industriepumpe Typ A",\n'
        '    "quantity": "1",\n'
        '    "unit_price": "5000.00",\n'
        '    "tax_rate": "19.00"\n'
        "  }]\n"
        "}\n"
        "```\n\n"
        "## Abgrenzung\n"
        "| | Proforma | Rechnung (§14) |\n"
        "|---|---|---|\n"
        "| Vorsteuerabzug | Nein | Ja |\n"
        "| Zahlungspflicht | Nein | Ja |\n"
        "| USt-Ausweis | Informativ | Rechtswirksam |\n"
        "| E-Rechnungspflicht | Nein | Ja (ab 2025) |\n\n"
        "## Wichtig\n"
        "- Sobald eine echte Lieferung/Leistung erfolgt, "
        "muss eine **ordentliche Rechnung** erstellt werden\n"
        "- Proforma ersetzt nie die E-Rechnungspflicht"
    )


def drittlandlieferung_guide() -> str:
    """Drittlandlieferung — Export ausserhalb der EU (Steuerkategorie G).

    Leitfaden fuer steuerfreie Ausfuhrlieferungen an Kunden
    in Nicht-EU-Staaten (§4 Nr. 1a / §6 UStG).
    """
    return (
        "# Drittlandlieferung — Ausfuhrlieferung "
        "(§4 Nr. 1a / §6 UStG)\n\n"
        "## Voraussetzungen fuer Steuerfreiheit\n"
        "1. Gegenstand gelangt in das **Drittlandsgebiet** "
        "(ausserhalb EU)\n"
        "2. Ausfuhr ist durch **Belege nachgewiesen** "
        "(Ausfuhrnachweis)\n"
        "3. Buchmässiger Nachweis (§6 Abs. 4 UStG)\n\n"
        "## E-Rechnungs-Pflichtfelder\n"
        "| Feld | BT-Code | Wert |\n"
        "|------|---------|------|\n"
        "| Steuerkategorie | BT-151 | `G` |\n"
        "| Steuersatz | BT-152 | `0.00` |\n"
        "| Befreiungsgrund | BT-120 | §4 Nr. 1a UStG |\n"
        "| Befreiungscode | BT-121 | `VATEX-EU-G` |\n\n"
        "## XRechnung-Umsetzung\n"
        "```json\n"
        "{\n"
        '  "seller": {\n'
        '    "tax_id": "DE123456789"\n'
        "  },\n"
        '  "buyer": {\n'
        '    "name": "US Customer Inc.",\n'
        '    "address": {\n'
        '      "street": "100 Main St",\n'
        '      "city": "New York",\n'
        '      "postal_code": "10001",\n'
        '      "country_code": "US"\n'
        "    }\n"
        "  },\n"
        '  "tax_exemption_reason": "Steuerfreie '
        'Ausfuhrlieferung gemaess §4 Nr. 1a UStG",\n'
        '  "tax_exemption_reason_code": "VATEX-EU-G",\n'
        '  "items": [{\n'
        '    "description": "Spezialmaschine Modell Z",\n'
        '    "quantity": "1",\n'
        '    "unit_price": "45000.00",\n'
        '    "tax_rate": "0.00",\n'
        '    "tax_category": "G"\n'
        "  }]\n"
        "}\n"
        "```\n\n"
        "## Ausfuhrnachweise (§10 UStDV)\n"
        "- **Ausgangsvermerk** des Zolls (ATLAS-Meldung)\n"
        "- Alternativ: Frachtbrief, Spediteursbescheinigung\n"
        "- Aufbewahrungspflicht: 10 Jahre\n\n"
        "## Lieferbedingungen (Incoterms)\n"
        "- EXW: Kaeufer traegt Ausfuhrrisiko → "
        "Verkaeufer muss trotzdem Ausfuhr nachweisen\n"
        "- FOB/CIF: Verkaeufer uebergibt an Frachtfuehrer\n"
        "- DDP: Verkaeufer traegt alle Kosten inkl. Zoll\n"
        "- Empfehlung: Incoterms in `invoice_note` angeben\n\n"
        "## Sonderfaelle\n"
        "- **Schweiz/Norwegen/UK** (EFTA/Drittland): "
        "Gleiche Behandlung wie andere Drittstaaten\n"
        "- **Lohnveredelung**: Ware kommt zurueck → "
        "andere Regelung (§4 Nr. 1a S. 2 UStG)\n"
        "- **Reihengeschaeft**: Pruefen, wer die "
        "bewegte Lieferung ausfuehrt\n\n"
        "## Compliance-Checks\n"
        "Der `einvoice_check_compliance` prueft:\n"
        "- Steuerkategorie G → Steuersatz muss 0% sein\n"
        "- Befreiungsgrund/-code sollte angegeben sein\n"
        "- Verkaeufer-USt-IdNr. vorhanden"
    )


def gutschriftverfahren_389_guide() -> str:
    """Gutschriftverfahren (TypeCode 389) — Self-Billing.

    Leitfaden fuer das Gutschriftverfahren, bei dem der
    Leistungsempfaenger die Rechnung im Namen des Leistenden erstellt.
    """
    return (
        "# Gutschriftverfahren — Self-Billing "
        "(TypeCode 389)\n\n"
        "## Was ist ein Gutschriftverfahren?\n"
        "- Der **Kaeufer** (Leistungsempfaenger) erstellt die "
        "Rechnung im Namen des **Verkaeufers** (Leistenden)\n"
        "- Geregelt in §14 Abs. 2 Satz 2 UStG\n"
        "- Erfordert **vorherige Vereinbarung** "
        "zwischen den Parteien\n"
        "- Nicht verwechseln mit Gutschrift (381) = "
        "Stornobeleg!\n\n"
        "## Voraussetzungen\n"
        "1. Schriftliche **Vereinbarung** zwischen "
        "Leistungserbringer und Empfaenger\n"
        "2. Leistungserbringer muss der Gutschrift "
        "**nicht widersprechen**\n"
        "3. Gutschrift muss alle Pflichtangaben "
        "einer Rechnung (§14 Abs. 4 UStG) enthalten\n"
        "4. **Hinweis 'Gutschrift'** auf dem Dokument "
        "(§14 Abs. 4 S. 1 Nr. 10 UStG)\n\n"
        "## Abgrenzung TypeCodes\n"
        "| TypeCode | Bezeichnung | Verwendung |\n"
        "|----------|-------------|------------|\n"
        "| 380 | Rechnung | Normale Rechnung |\n"
        "| 381 | Gutschrift (Storno) | Stornierung/Korrektur |\n"
        "| 384 | Korrekturrechnung | Berichtigung |\n"
        "| **389** | **Self-Billing** | **Gutschriftverfahren** |\n\n"
        "## E-Rechnungs-Pflichtfelder\n"
        "| Feld | BT-Code | Beschreibung |\n"
        "|------|---------|-------------|\n"
        "| type_code | BT-3 | `389` |\n"
        "| Seller | BG-4 | **Leistungserbringer** |\n"
        "| Buyer | BG-7 | **Rechnungsersteller** |\n"
        "| invoice_note | BT-22 | Hinweis: Gutschrift |\n\n"
        "## XRechnung-Umsetzung\n"
        "```json\n"
        "{\n"
        '  "invoice_id": "GS-2026-001",\n'
        '  "type_code": "389",\n'
        '  "seller": {\n'
        '    "name": "Lieferant GmbH",\n'
        '    "tax_id": "DE111111111"\n'
        "  },\n"
        '  "buyer": {\n'
        '    "name": "Einkäufer AG",\n'
        '    "tax_id": "DE222222222"\n'
        "  },\n"
        '  "invoice_note": "Gutschrift im Sinne von §14 '
        "Abs. 2 Satz 2 UStG. Erstellt durch den "
        'Leistungsempfaenger.",\n'
        '  "items": [{\n'
        '    "description": "Zulieferteil A-100",\n'
        '    "quantity": "500",\n'
        '    "unit_price": "12.50",\n'
        '    "tax_rate": "19.00"\n'
        "  }]\n"
        "}\n"
        "```\n\n"
        "## Typische Branchen\n"
        "- Automobilindustrie (Zulieferer)\n"
        "- Handel (Rueckverguetungen)\n"
        "- Landwirtschaft (Erzeugergemeinschaften)\n"
        "- Entsorgungswirtschaft\n\n"
        "## Haeufige Fehler\n"
        "- TypeCode 380 statt 389 verwendet\n"
        "- Seller/Buyer vertauscht (Seller = Leistender!)\n"
        "- Fehlender Hinweis 'Gutschrift'\n"
        "- Keine schriftliche Vereinbarung vorhanden"
    )
