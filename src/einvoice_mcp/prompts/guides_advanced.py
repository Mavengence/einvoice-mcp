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
        '- Margenbesteuerung gemaess §25 UStG. '
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
