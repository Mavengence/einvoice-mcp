"""German e-invoice guidance prompts."""


def steuerprüfung_checkliste() -> str:
    """Checkliste: E-Rechnungen für die Steuerprüfung vorbereiten.

    Leitfaden zur Vorbereitung auf eine Betriebsprüfung mit
    Fokus auf E-Rechnungs-Compliance und GoBD-Archivierung.
    """
    return (
        "# Steuerprüfung — E-Rechnungs-Checkliste\n\n"
        "## 1. Archivierung (GoBD-konform)\n"
        "- [ ] E-Rechnungen im **Originalformat** archiviert (XML, nicht nur PDF)\n"
        "- [ ] **10 Jahre** Aufbewahrungsfrist (§147 AO, §14b UStG)\n"
        "- [ ] **Unveränderbarkeit** sichergestellt (kein nachträgliches Editieren)\n"
        "- [ ] **Maschinelle Auswertbarkeit** gewährleistet (GoBD Tz. 128)\n"
        "- [ ] Verfahrensdokumentation vorhanden\n\n"
        "## 2. Pflichtangaben prüfen (§14 UStG)\n"
        "- [ ] BT-1: Rechnungsnummer (fortlaufend, eindeutig)\n"
        "- [ ] BT-2: Rechnungsdatum\n"
        "- [ ] BT-27..40: Vollständige Verkäufer-Angaben (Name, Anschrift, USt-IdNr.)\n"
        "- [ ] BT-44..55: Vollständige Käufer-Angaben\n"
        "- [ ] Positionen: Menge, Art, Entgelt, Steuersatz, Steuerbetrag\n"
        "- [ ] BT-81: Zahlungsart angegeben\n"
        "- [ ] BT-20: Zahlungsbedingungen\n\n"
        "## 3. Umsatzsteuer-Prüfung\n"
        "- [ ] Steuersätze korrekt (19%, 7%, 0% mit Begründung)\n"
        "- [ ] Reverse Charge (§13b): Hinweis vorhanden, 0% Steuer\n"
        "- [ ] Innergemeinschaftliche Lieferungen: USt-IdNr. beider Parteien\n"
        "- [ ] Steuerbefreiungen: Befreiungsgrund (BT-120) und Code (BT-121)\n"
        "- [ ] Vorsteuerabzug: Alle Voraussetzungen erfüllt?\n\n"
        "## 4. Gutschriften und Korrekturen\n"
        "- [ ] Gutschriften (381) referenzieren Originalrechnung (BT-25 + BT-26)\n"
        "- [ ] Korrekturrechnungen (384) referenzieren Originalrechnung (BT-25 + BT-26)\n"
        "- [ ] Schlussrechnungen (877): `prepaid_amount` (BT-113) korrekt gesetzt\n"
        "- [ ] Keine 'informellen' Korrekturen per E-Mail oder PDF\n"
        "- [ ] Stornierungen vollständig dokumentiert\n\n"
        "## 5. Validierung\n"
        "- [ ] Alle E-Rechnungen gegen **KoSIT-Validator** geprüft\n"
        "- [ ] XRechnung: BR-DE-Regeln erfüllt\n"
        "- [ ] ZUGFeRD: PDF/A-3 Konformität sichergestellt\n"
        "- [ ] IBAN/BIC-Formate korrekt\n\n"
        "## 6. B2B-Pflicht (ab 2025/2027/2028)\n"
        "- [ ] Empfang von E-Rechnungen sichergestellt (seit 01.01.2025)\n"
        "- [ ] Versand vorbereitet (ab 2027 für Umsatz > 800K€, ab 2028 für alle)\n"
        "- [ ] Format: EN 16931 (XRechnung oder ZUGFeRD)\n\n"
        "## Typische Prüfungsschwerpunkte:\n"
        "1. **Rechnungsnummern-Lücken** — fehlende Nummern im Kreis\n"
        "2. **Vorsteuerabzug** — alle formellen Voraussetzungen erfüllt?\n"
        "3. **Reverse Charge** — §13b korrekt angewendet?\n"
        "4. **Innergemeinschaftliche Lieferungen** — ZM abgegeben?\n"
        "5. **Archivierung** — GoBD-Konformität nachweisbar?"
    )


def b2b_pflicht_2027() -> str:
    """Checkliste: B2B E-Rechnungspflicht ab 2027 vorbereiten.

    Schritt-für-Schritt-Anleitung für die Umstellung auf E-Rechnung.
    """
    return (
        "# B2B E-Rechnungspflicht — Checkliste zur Vorbereitung\n\n"
        "## Zeitplan:\n"
        "- **01.01.2025**: Alle Unternehmen müssen E-Rechnungen **empfangen** können\n"
        "- **01.01.2027**: Unternehmen mit Umsatz > 800.000€ müssen E-Rechnungen **senden**\n"
        "- **01.01.2028**: **Alle** Unternehmen müssen E-Rechnungen senden\n\n"
        "## Was ist eine E-Rechnung?\n"
        "- Maschinenlesbares XML nach **EN 16931** (nicht PDF!)\n"
        "- Erlaubte Formate: **XRechnung** (CII-XML) oder **ZUGFeRD** (PDF/A-3 + XML)\n"
        "- Papierrechnungen und einfache PDF gelten NICHT als E-Rechnung\n\n"
        "## Checkliste:\n"
        "1. [ ] **Empfang sicherstellen** — E-Mail-Postfach für E-Rechnungen einrichten\n"
        "2. [ ] **Format wählen** — XRechnung (B2G) oder ZUGFeRD (B2B empfohlen)\n"
        "3. [ ] **Software testen** — Mit diesem MCP-Server Testrechnungen erstellen\n"
        "4. [ ] **Stammdaten pflegen** — USt-IdNr., IBAN, Kontaktdaten aktuell halten\n"
        "5. [ ] **Mitarbeiter schulen** — Rechnungswesen auf neue Formate vorbereiten\n"
        "6. [ ] **Archivierung** — GoBD-konforme Archivierung sicherstellen (10 Jahre)\n"
        "7. [ ] **Testlauf** — Echte Rechnung erstellen und mit KoSIT validieren\n\n"
        "## Beispiel-Prompt:\n"
        "```\n"
        "Erstelle eine ZUGFeRD-Rechnung:\n"
        "- Rechnungsnr.: RE-2026-001\n"
        "- Verkäufer: [Ihre Firma], [Adresse], USt-IdNr. DE...\n"
        "- Käufer: [Kunde], [Adresse]\n"
        "- Position: [Beschreibung], [Menge], [Preis], 19% USt\n"
        "- SEPA-Überweisung, IBAN: DE...\n"
        "- Zahlungsziel: 30 Tage netto\n"
        "```\n\n"
        "## Ausnahmen:\n"
        "- B2C-Rechnungen (an Privatpersonen) → keine Pflicht\n"
        "- Kleinbetragsrechnungen ≤ 250€ → keine Pflicht\n"
        "- Fahrausweise → keine Pflicht\n\n"
        "## Rechtsgrundlage:\n"
        "- Wachstumschancengesetz (BGBl. 2024 I Nr. 108)\n"
        "- §14 UStG (neue Fassung ab 2025)\n"
        "- BMF-Schreiben vom 15.11.2024"
    )


def gutschrift_erstellen() -> str:
    """Anleitung: Gutschrift / Credit Note (TypeCode 381) erstellen.

    Schritt-für-Schritt-Anleitung für die korrekte Erstellung einer Gutschrift
    nach deutschem Steuerrecht (§14 Abs. 4 UStG).
    """
    return (
        "# Gutschrift (Credit Note) erstellen — Checkliste\n\n"
        "Eine Gutschrift korrigiert eine bereits gestellte Rechnung.\n\n"
        "## Pflichtparameter:\n"
        "- `type_code`: **381** (Gutschrift)\n"
        "- `preceding_invoice_number`: Nummer der Originalrechnung (BT-25, PFLICHT)\n"
        "- `preceding_invoice_date`: Datum der Originalrechnung (BT-26, empfohlen)\n"
        "- Alle Standardfelder wie bei einer normalen Rechnung\n\n"
        "## Beträge:\n"
        "- Positionen mit **positiven** Beträgen eintragen\n"
        "- Die Gutschrift reduziert die offene Forderung\n\n"
        "## Beispiel:\n"
        "```\n"
        "type_code: '381'\n"
        "preceding_invoice_number: 'RE-2026-001'\n"
        "preceding_invoice_date: '2026-01-15'\n"
        "invoice_note: 'Gutschrift zu Rechnung RE-2026-001 wegen Retoure'\n"
        "```\n\n"
        "## Häufige Fehler:\n"
        "- BT-25 vergessen → KoSIT-Validierung schlägt fehl\n"
        "- Falscher TypeCode (380 statt 381)\n"
        "- Negative Beträge (nicht nötig — Gutschrift-Semantik ist implizit)"
    )


def reverse_charge_checkliste() -> str:
    """Checkliste für Reverse Charge (§13b UStG) — Kategorie AE.

    Alle Pflichtangaben und Prüfschritte für Rechnungen mit
    Steuerschuldnerschaft des Leistungsempfängers.
    """
    return (
        "# Reverse Charge (§13b UStG) — Checkliste\n\n"
        "## Voraussetzungen:\n"
        "- Leistender Unternehmer im Ausland ODER\n"
        "- Bauleistungen (§13b Abs. 2 Nr. 4 UStG) ODER\n"
        "- Andere §13b-Tatbestände\n\n"
        "## Pflichtangaben:\n"
        "1. **tax_category**: `AE` für alle Positionen\n"
        "2. **tax_rate**: `0.00` (muss 0% sein)\n"
        "3. **seller_tax_id**: USt-IdNr. des Verkäufers (BT-31, PFLICHT)\n"
        "4. **buyer_tax_id**: USt-IdNr. des Käufers (BT-48, PFLICHT)\n"
        "5. **tax_exemption_reason**: z.B. 'Reverse Charge — "
        "Steuerschuldnerschaft des Leistungsempfängers gemäß §13b UStG'\n"
        "6. **tax_exemption_reason_code**: `vatex-eu-ae`\n\n"
        "## Hinweis auf der Rechnung:\n"
        "Pflichthinweis nach §14a Abs. 5 UStG: "
        "'Steuerschuldnerschaft des Leistungsempfängers'\n\n"
        "## Beispiel:\n"
        "```json\n"
        '{"description": "IT-Beratung", "quantity": 10, "unit_code": "HUR",\n'
        ' "unit_price": 150.00, "tax_rate": 0.00, "tax_category": "AE"}\n'
        "```"
    )


def xrechnung_schnellstart() -> str:
    """Schnellstart: XRechnung für öffentliche Auftraggeber erstellen.

    Minimale Pflichtangaben für eine gültige XRechnung 3.0.
    """
    return (
        "# XRechnung — Schnellstart\n\n"
        "## Mindestangaben für eine gültige XRechnung:\n\n"
        "### Pflicht:\n"
        "- `invoice_id`: Eindeutige Rechnungsnummer\n"
        "- `issue_date`: Rechnungsdatum (YYYY-MM-DD)\n"
        "- `seller_name`, `seller_street`, `seller_city`, `seller_postal_code`, "
        "`seller_country_code`\n"
        "- `seller_tax_id`: USt-IdNr. (DE...)\n"
        "- `buyer_name`, `buyer_street`, `buyer_city`, `buyer_postal_code`, "
        "`buyer_country_code`\n"
        "- `items`: Mindestens eine Position\n"
        "- `leitweg_id` ODER `buyer_reference`: Leitweg-ID des Auftraggebers\n\n"
        "### XRechnung-spezifisch (BR-DE-Regeln):\n"
        "- `seller_electronic_address`: E-Mail des Verkäufers (BT-34)\n"
        "- `buyer_electronic_address`: E-Mail des Käufers (BT-49)\n"
        "- `seller_contact_name`: Ansprechpartner (BT-41, BR-DE-5)\n"
        "- `seller_contact_phone`: Telefon (BT-42, BR-DE-6)\n"
        "- `seller_contact_email`: E-Mail (BT-43, BR-DE-7)\n"
        "- `payment_terms_text`: Zahlungsbedingungen (BT-20, BR-DE-15)\n"
        "- `delivery_date` ODER `service_period_start`/`service_period_end`\n\n"
        "### Leitweg-ID Format:\n"
        "Typisch: `04011000-12345-67` (Grobadresse-Feinadresse-Prüfziffer)\n"
        "Fragen Sie den Auftraggeber nach seiner Leitweg-ID.\n\n"
        "### Empfohlene Zahlungsart:\n"
        "- `payment_means_type_code`: `58` (SEPA-Überweisung)\n"
        "- `seller_iban`: IBAN des Verkäufers"
    )


def korrekturrechnung_erstellen() -> str:
    """Anleitung: Korrekturrechnung (TypeCode 384) erstellen.

    Unterschiede zur Gutschrift und korrekte Vorgehensweise
    nach §14 Abs. 4 UStG.
    """
    return (
        "# Korrekturrechnung (TypeCode 384) erstellen\n\n"
        "## Unterschied zur Gutschrift (381):\n"
        "- **381 Gutschrift**: Reduziert eine Forderung (z.B. Retoure, Rabatt)\n"
        "- **384 Korrekturrechnung**: Ersetzt/korrigiert eine fehlerhafte Rechnung\n\n"
        "## Pflichtparameter:\n"
        "- `type_code`: **384**\n"
        "- `preceding_invoice_number`: Nummer der fehlerhaften Originalrechnung (BT-25)\n"
        "- `preceding_invoice_date`: Datum der Originalrechnung (BT-26, empfohlen)\n"
        "- `invoice_note`: Grund der Korrektur angeben\n"
        "- Alle korrekten Daten der neuen Rechnung\n\n"
        "## Beispiel:\n"
        "```\n"
        "type_code: '384'\n"
        "preceding_invoice_number: 'RE-2026-001'\n"
        "preceding_invoice_date: '2026-01-15'\n"
        "invoice_note: 'Korrektur der Rechnung RE-2026-001 — "
        "falscher Steuersatz korrigiert'\n"
        "```\n\n"
        "## Steuerliche Wirkung:\n"
        "- Die Korrekturrechnung ERSETZT die Originalrechnung\n"
        "- Der Käufer muss den Vorsteuerabzug der Originalrechnung korrigieren\n"
        "- Zeitpunkt: Die Korrektur wirkt für den Besteuerungszeitraum "
        "der Originalrechnung"
    )


def abschlagsrechnung_guide() -> str:
    """Anleitung: Abschlagsrechnung / Teilrechnung (TypeCode 875/876/877).

    Erklärung der Rechnungstypen für Teilleistungen und Schlussrechnungen
    nach §632a BGB und §14 Abs. 1 UStG.
    """
    return (
        "# Abschlagsrechnung & Teilrechnung — TypeCode 875/876/877\n\n"
        "## TypeCode-Auswahl:\n"
        "- **875 — Teilrechnung (Partial Invoice)**: Rechnung über eine "
        "Teilleistung innerhalb eines Gesamtauftrags\n"
        "- **876 — Vorauszahlungsrechnung (Prepayment Invoice)**: "
        "Abschlagsrechnung VOR Leistungserbringung\n"
        "- **877 — Schlussrechnung (Final Invoice)**: Abschluss nach "
        "vorherigen Teil-/Vorauszahlungen\n\n"
        "## Pflichtangaben:\n"
        "- `type_code`: **875**, **876** oder **877**\n"
        "- `contract_reference`: Vertragsnummer / Auftragsnummer (BT-12)\n"
        "- `invoice_note`: Bezug auf Gesamtauftrag und bisherige Zahlungen\n"
        "- `project_reference`: Projektnummer, falls vorhanden (BT-11)\n\n"
        "## Beispiel Abschlagsrechnung:\n"
        "```\n"
        "type_code: '876'\n"
        "contract_reference: 'V-2026-100'\n"
        "invoice_note: '2. Abschlag für Auftrag V-2026-100 "
        "(Gesamtauftrag: 50.000€, bisherige Abschläge: 15.000€)'\n"
        "```\n\n"
        "## Schlussrechnung:\n"
        "```\n"
        "type_code: '877'\n"
        "contract_reference: 'V-2026-100'\n"
        "prepaid_amount: 30000.00  # BT-113: Bereits gezahlte Abschläge\n"
        "invoice_note: 'Schlussrechnung V-2026-100. "
        "Gesamtleistung: 50.000€'\n"
        "```\n\n"
        "## BT-113 Vorauszahlung (prepaid_amount):\n"
        "- Bei Schlussrechnungen (877) `prepaid_amount` setzen\n"
        "- Der Restbetrag (`due_payable`) wird automatisch berechnet:\n"
        "  `due_payable = gross_total - prepaid_amount`\n"
        "- Ohne `prepaid_amount` wird der volle Bruttobetrag fällig!\n\n"
        "## Steuerrecht:\n"
        "- Abschläge sind umsatzsteuerpflichtig bei Vereinnahmung "
        "(§13 Abs. 1 Nr. 1a Satz 4 UStG)\n"
        "- Schlussrechnung korrigiert Vorsteuerabzug der Abschläge"
    )


def ratenzahlung_rechnung() -> str:
    """Anleitung: Rechnung mit Ratenzahlung erstellen.

    Korrekte Darstellung von Ratenzahlungsvereinbarungen
    in XRechnung/ZUGFeRD.
    """
    return (
        "# Rechnung mit Ratenzahlung\n\n"
        "## Darstellung in XRechnung:\n"
        "Ratenzahlung wird über `payment_terms_text` (BT-20) abgebildet.\n\n"
        "## Beispiel:\n"
        "```\n"
        "payment_terms_text: '3 Raten: "
        "1. Rate 1.000€ fällig 01.04.2026, "
        "2. Rate 1.000€ fällig 01.05.2026, "
        "3. Rate 1.000€ fällig 01.06.2026'\n"
        "due_date: '2026-04-01'  # Erste Fälligkeit\n"
        "```\n\n"
        "## Hinweise:\n"
        "- `due_date` (BT-9): Datum der **ersten** Rate\n"
        "- `payment_terms_text` (BT-20): Gesamten Ratenplan textlich beschreiben\n"
        "- Optional: Skonto-Bedingungen pro Rate möglich\n\n"
        "## Mit Skonto:\n"
        "```\n"
        "payment_terms_text: '3 Raten à 1.000€, "
        "2% Skonto bei Zahlung innerhalb von 10 Tagen'\n"
        "skonto_percent: 2.0\n"
        "skonto_days: 10\n"
        "```\n\n"
        "## Rechtlicher Hintergrund:\n"
        "- §271 BGB: Fälligkeit nach Vereinbarung\n"
        "- Ratenvereinbarungen sollten schriftlich fixiert sein"
    )


def handwerkerrechnung_35a() -> str:
    """Anleitung: Handwerkerrechnung nach §35a EStG.

    Rechnungsstellung für haushaltsnahe Handwerkerleistungen mit
    Ausweisung der Arbeitskosten für den Steuerabzug des Kunden.
    """
    return (
        "# Handwerkerrechnung für §35a EStG\n\n"
        "## Hintergrund:\n"
        "Kunden können 20% der Arbeitskosten (max. 1.200€/Jahr) als "
        "Steuerermäßigung geltend machen (§35a Abs. 3 EStG).\n\n"
        "## Pflicht auf der Rechnung:\n"
        "1. **Getrennte Ausweisung** von Arbeitskosten und Materialkosten\n"
        "2. **Adresse der Leistungserbringung** (Haushalt des Kunden)\n"
        "3. **Banküberweisung** als Zahlungsart (§35a Abs. 5 Satz 3: "
        "keine Barzahlung!)\n\n"
        "## Umsetzung in XRechnung:\n"
        "```\n"
        "items:\n"
        "  - description: 'Arbeitsleistung: Bad sanieren (30 Std)'\n"
        "    quantity: 30\n"
        "    unit_code: 'HUR'\n"
        "    unit_price: 55.00\n"
        "    tax_rate: 19.00\n"
        "  - description: 'Material: Fliesen, Kleber, Silikon'\n"
        "    quantity: 1\n"
        "    unit_code: 'C62'\n"
        "    unit_price: 800.00\n"
        "    tax_rate: 19.00\n"
        "delivery_location_name: 'Privathaushalt Meier'\n"
        "delivery_street: 'Musterstraße 42'\n"
        "delivery_city: 'München'\n"
        "delivery_postal_code: '80331'\n"
        "delivery_country_code: 'DE'\n"
        "payment_means_type_code: '58'  # SEPA-Überweisung — PFLICHT!\n"
        "invoice_note: 'Arbeitskosten: 1.650€ netto "
        "(§35a EStG steuerlich absetzbar)'\n"
        "```\n\n"
        "## Häufige Fehler:\n"
        "- Keine Trennung von Material/Arbeit → Finanzamt lehnt ab\n"
        "- Barzahlung → §35a nicht anwendbar\n"
        "- Lieferort fehlt → Nachweis des Haushalts nicht erbracht"
    )


def typecode_entscheidungshilfe() -> str:
    """Entscheidungshilfe: Welcher TypeCode für welchen Anlass?

    Übersicht aller unterstützten Rechnungstypen nach EN 16931
    mit deutschen Erklärungen und Anwendungsfällen.
    """
    return (
        "# TypeCode — Welcher Rechnungstyp?\n\n"
        "| Code | Typ | Wann verwenden? |\n"
        "|------|-----|------------------|\n"
        "| **380** | Handelsrechnung | Standardrechnung für Lieferungen/Leistungen |\n"
        "| **381** | Gutschrift | Korrektur zugunsten des Käufers "
        "(Retoure, Rabatt) |\n"
        "| **384** | Korrekturrechnung | Fehlerhafte Rechnung ersetzen |\n"
        "| **389** | Selbstfakturierte Rechnung | Käufer stellt Rechnung "
        "im Namen des Verkäufers |\n"
        "| **875** | Teilrechnung | Rechnung über Teilleistung |\n"
        "| **876** | Vorauszahlungsrechnung | Abschlag vor Leistung |\n"
        "| **877** | Schlussrechnung | Endabrechnung nach Abschlägen |\n\n"
        "## Entscheidungsbaum:\n\n"
        "1. **Neue Lieferung/Leistung?** → **380**\n"
        "2. **Korrektur einer Rechnung?**\n"
        "   - Zugunsten des Käufers → **381** (Gutschrift)\n"
        "   - Fehlerhafte Daten korrigieren → **384** (Korrekturrechnung)\n"
        "3. **Teilweise Leistungserbringung?**\n"
        "   - Abschlag vorab → **876**\n"
        "   - Teilleistung erbracht → **875**\n"
        "   - Letzte Rechnung nach Abschlägen → **877**\n"
        "4. **Käufer stellt Rechnung?** → **389** (Gutschriftverfahren)\n\n"
        "## Pflichtfelder je nach TypeCode:\n"
        "- **381/384**: `preceding_invoice_number` (BT-25) PFLICHT, "
        "`preceding_invoice_date` (BT-26) empfohlen\n"
        "- **875/876/877**: `contract_reference` (BT-12) empfohlen\n"
        "- **877**: `prepaid_amount` (BT-113) für bereits gezahlte Abschläge\n"
        "- **389**: Vereinbarung zwischen den Parteien erforderlich"
    )


def kleinunternehmer_guide() -> str:
    """Anleitung zur Erstellung einer Rechnung als Kleinunternehmer (§19 UStG).

    Zeigt Pflichtfelder, steuerliche Hinweise und ein vollständiges Beispiel.
    """
    return (
        "# Kleinunternehmerrechnung (§19 UStG)\n\n"
        "## Voraussetzungen\n"
        "- Vorjahresumsatz ≤ 22.000 EUR und\n"
        "- Voraussichtlicher Umsatz im laufenden Jahr ≤ 50.000 EUR\n"
        "- Option nach §19 Abs. 1 UStG nicht widerrufen\n\n"
        "## Pflichtangaben auf der Rechnung\n"
        "1. **Alle §14 UStG Pflichtangaben** (Name, Anschrift, Datum, etc.)\n"
        "2. **Hinweis auf Steuerbefreiung** — PFLICHT per §19 Abs. 1 Satz 4:\n"
        "   `tax_exemption_reason`: 'Gemäß §19 UStG wird keine "
        "Umsatzsteuer berechnet (Kleinunternehmerregelung).'\n"
        "3. **Kein gesonderter MwSt-Ausweis** — VERBOTEN!\n\n"
        "## Technische Umsetzung\n"
        "```\n"
        "tax_category: E       (Exempt)\n"
        "tax_rate: 0.00\n"
        "tax_exemption_reason: 'Gemäß §19 UStG wird keine "
        "Umsatzsteuer berechnet (Kleinunternehmerregelung).'\n"
        "tax_exemption_reason_code: 'vatex-eu-ae'\n"
        "```\n\n"
        "## Beispielaufruf\n"
        "```json\n"
        '{\n'
        '  "invoice_id": "KU-2026-001",\n'
        '  "issue_date": "2026-03-01",\n'
        '  "seller_name": "Anna Muster",\n'
        '  "seller_street": "Hauptstr. 1",\n'
        '  "seller_city": "München",\n'
        '  "seller_postal_code": "80331",\n'
        '  "seller_country_code": "DE",\n'
        '  "seller_tax_id": "",\n'
        '  "seller_tax_number": "123/456/78901",\n'
        '  "buyer_name": "Kunde GmbH",\n'
        '  "buyer_street": "Marktplatz 5",\n'
        '  "buyer_city": "Berlin",\n'
        '  "buyer_postal_code": "10115",\n'
        '  "buyer_country_code": "DE",\n'
        '  "tax_exemption_reason": "Gemäß §19 UStG wird keine '
        'Umsatzsteuer berechnet (Kleinunternehmerregelung).",\n'
        '  "tax_exemption_reason_code": "vatex-eu-ae",\n'
        '  "items_json": "[{\\"description\\":\\"Grafikdesign Logo\\",'
        '\\"quantity\\":\\"1\\",'
        '\\"unit_code\\":\\"C62\\",'
        '\\"unit_price\\":\\"800.00\\",'
        '\\"tax_rate\\":\\"0.00\\",'
        '\\"tax_category\\":\\"E\\"}]"\n'
        "}\n"
        "```\n\n"
        "## Häufige Fehler\n"
        "- MwSt-Ausweis auf der Rechnung → Steuerschuld nach §14c UStG!\n"
        "- Fehlender §19-Hinweis → Finanzamt kann Nachforderung stellen\n"
        "- USt-IdNr. angeben statt Steuernummer → nicht erforderlich, "
        "Steuernummer reicht\n"
        "- Rechnungsbetrag > 22.000 EUR → prüfen ob noch Kleinunternehmer"
    )


def bauleistungen_13b_guide() -> str:
    """Anleitung für Rechnungen bei Bauleistungen (§13b Abs. 2 Nr. 4 UStG).

    Reverse Charge bei Bauleistungen — Steuerschuldnerschaft des
    Leistungsempfängers.
    """
    return (
        "# Bauleistungen — Reverse Charge (§13b UStG)\n\n"
        "## Wann gilt §13b bei Bauleistungen?\n"
        "- Leistungsempfänger ist **selbst Bauleistender** (§13b Abs. 5 UStG)\n"
        "- Leistung fällt unter §13b Abs. 2 Nr. 4 UStG:\n"
        "  - Werklieferungen und Werkleistungen am Grundstück\n"
        "  - Elektroinstallation, Sanitär, Heizung, Dachdeckerarbeiten\n"
        "  - Gerüstbau, Abbrucharbeiten, Erdarbeiten\n"
        "  - NICHT: reine Planungsleistungen, Reinigung, Gartenbau\n\n"
        "## Pflichtangaben auf der Rechnung\n"
        "1. **USt-IdNr. des Verkäufers** (BT-31) — PFLICHT\n"
        "2. **USt-IdNr. des Käufers** (BT-48) — PFLICHT\n"
        "3. **Hinweis auf Reverse Charge** (BT-22):\n"
        "   'Steuerschuldnerschaft des Leistungsempfängers "
        "gemäß §13b UStG'\n"
        "4. **Nettobetrag ohne MwSt** — kein gesonderter Steuerausweis\n\n"
        "## Technische Umsetzung\n"
        "```\n"
        "tax_category: AE      (Reverse Charge)\n"
        "tax_rate: 0.00\n"
        "seller_tax_id: DE123456789  (USt-IdNr. Verkäufer)\n"
        "buyer_tax_id: DE987654321   (USt-IdNr. Käufer)\n"
        "invoice_note: 'Steuerschuldnerschaft des Leistungsempfängers "
        "gemäß §13b UStG'\n"
        "tax_exemption_reason: 'Steuerschuldnerschaft des "
        "Leistungsempfängers gemäß §13b Abs. 2 Nr. 4 UStG'\n"
        "```\n\n"
        "## Beispiel items_json\n"
        "```json\n"
        '[{\n'
        '  "description": "Elektroinstallation Bürogebäude, 2. OG",\n'
        '  "quantity": "1",\n'
        '  "unit_code": "C62",\n'
        '  "unit_price": "15000.00",\n'
        '  "tax_rate": "0.00",\n'
        '  "tax_category": "AE"\n'
        "}]\n"
        "```\n\n"
        "## Compliance-Prüfung\n"
        "Das `einvoice_check_compliance` Tool prüft automatisch:\n"
        "- RC-BT-31: USt-IdNr. Verkäufer vorhanden\n"
        "- RC-BT-48: USt-IdNr. Käufer vorhanden\n"
        "- RC-TAX-RATE: Steuersatz = 0%\n"
        "- RC-COUNTRY: Länderprüfung (bei Inland gleich)\n\n"
        "## Häufige Fehler\n"
        "- Steuerausweis trotz §13b → Steuerschuld nach §14c UStG!\n"
        "- Fehlende USt-IdNr. des Käufers → keine Reverse Charge\n"
        "- Falscher Hinweistext → formaler Mangel\n"
        "- Leistung fällt nicht unter §13b → normaler Steuerausweis nötig"
    )


def differenzbesteuerung_25a_guide() -> str:
    """Differenzbesteuerung nach §25a UStG — E-Rechnung für Gebrauchtwaren.

    Anleitung für Händler von Gebrauchtwaren, Antiquitäten, Sammlerstücken
    und Kunstgegenständen, die die Differenzbesteuerung anwenden.
    """
    return (
        "# Differenzbesteuerung (§25a UStG) — E-Rechnung\n\n"
        "## Wann anwendbar?\n"
        "- Wiederverkäufer von Gebrauchtwaren, Antiquitäten, "
        "Sammlerstücken, Kunstgegenständen\n"
        "- Ware wurde von Privatperson oder Kleinunternehmer ohne "
        "USt-Ausweis erworben\n"
        "- Händler versteuert nur die **Marge** "
        "(Verkaufspreis - Einkaufspreis)\n\n"
        "## Pflichtangaben auf der Rechnung\n"
        "1. **Hinweis auf Differenzbesteuerung** (BT-22):\n"
        '   `"Gebrauchtgegenstände / Sonderregelung nach §25a UStG"`\n'
        "2. **Kein gesonderter Steuerausweis** — "
        "USt darf NICHT ausgewiesen werden (§25a Abs. 3 UStG)\n"
        "3. Bruttopreis = Endpreis inkl. enthaltener Steuer\n\n"
        "## Technische Umsetzung (CII/XRechnung)\n"
        "```json\n"
        "{\n"
        '  "tax_category": "S",\n'
        '  "tax_rate": "0.00",\n'
        '  "tax_exemption_reason": '
        '"Differenzbesteuerung nach §25a UStG",\n'
        '  "tax_exemption_reason_code": "vatex-eu-o",\n'
        '  "invoice_note": "Gebrauchtgegenstände / '
        'Sonderregelung nach §25a UStG"\n'
        "}\n"
        "```\n\n"
        "**Wichtig:** Der Bruttopreis wird als Positionspreis angegeben. "
        "Die Steuer auf die Marge wird **intern** berechnet, erscheint "
        "aber NICHT auf der Rechnung.\n\n"
        "## Beispiel-Position\n"
        "```json\n"
        "{\n"
        '  "description": "Gebrauchtes Notebook ThinkPad X1",\n'
        '  "quantity": "1",\n'
        '  "unit_price": "499.00",\n'
        '  "tax_rate": "0.00",\n'
        '  "tax_category": "S"\n'
        "}\n"
        "```\n\n"
        "## Häufige Fehler\n"
        "- Steuer gesondert ausweisen → Steuerschuld nach §14c UStG!\n"
        "- Hinweis auf §25a fehlt → formaler Mangel\n"
        "- Anwendung bei Neuware → §25a nur für Gebrauchtwaren\n"
        "- Vorsteuerabzug beim Einkauf → dann keine Differenzbesteuerung"
    )


def stornobuchung_workflow() -> str:
    """Storno und Korrektur von E-Rechnungen — Wann 381, 384 oder neue 380?

    Entscheidungshilfe für die korrekte Vorgehensweise bei Rechnungs-
    korrekturen und Stornierungen im E-Rechnungs-Kontext.
    """
    return (
        "# Storno & Korrektur von E-Rechnungen\n\n"
        "## Überblick: Welcher Belegtyp?\n\n"
        "| Situation | Typ | BT-3 |\n"
        "|-----------|-----|------|\n"
        "| Vollständige Stornierung | Gutschrift | 381 |\n"
        "| Teilkorrektur (Menge/Preis) | Korrekturrechnung | 384 |\n"
        "| Komplett neue Rechnung | Rechnung | 380 |\n\n"
        "## 1. Gutschrift (381) — Vollstorno\n"
        "Verwendet bei:\n"
        "- Komplette Rechnungsstornierung\n"
        "- Rückabwicklung des gesamten Geschäfts\n"
        "- Retoure aller Positionen\n\n"
        "**Pflichtfelder:**\n"
        "- `preceding_invoice_number` (BT-25): Nummer der "
        "Originalrechnung\n"
        "- `preceding_invoice_date` (BT-26): Datum der "
        "Originalrechnung\n"
        "- Alle Positionen mit **negativen Beträgen** oder "
        "mit gleichen Beträgen und Verweis auf Gutschrift\n\n"
        "```json\n"
        "{\n"
        '  "type_code": "381",\n'
        '  "preceding_invoice_number": "RE-2026-001",\n'
        '  "preceding_invoice_date": "2026-01-15",\n'
        '  "invoice_note": "Vollständige Stornierung von '
        'RE-2026-001"\n'
        "}\n"
        "```\n\n"
        "## 2. Korrekturrechnung (384) — Teilkorrektur\n"
        "Verwendet bei:\n"
        "- Preisänderung einzelner Positionen\n"
        "- Mengenkorrektur\n"
        "- Nachträglicher Rabatt\n\n"
        "**Pflichtfelder:**\n"
        "- `preceding_invoice_number` (BT-25)\n"
        "- `preceding_invoice_date` (BT-26)\n"
        "- Nur die **Differenz** als Position aufführen\n\n"
        "```json\n"
        "{\n"
        '  "type_code": "384",\n'
        '  "preceding_invoice_number": "RE-2026-001",\n'
        '  "preceding_invoice_date": "2026-01-15",\n'
        '  "invoice_note": "Preiskorrektur Position 2"\n'
        "}\n"
        "```\n\n"
        "## 3. Neue Rechnung (380) — Neuausstellung\n"
        "Verwendet bei:\n"
        "- Originalrechnung war formal ungültig\n"
        "- Empfänger fordert komplette Neuausstellung\n"
        "- Storno + Neuausstellung als Paar\n\n"
        "**Workflow:** Erst 381 (Storno), dann neue 380.\n\n"
        "## Steuerliche Hinweise\n"
        "- Gutschrift/Korrektur muss im **gleichen Voranmeldungs"
        "zeitraum** wie die Originalrechnung korrigiert werden\n"
        "- Bei Vorsteuerabzug des Empfängers: Korrektur löst "
        "Vorsteuerberichtigung nach §17 UStG aus\n"
        "- Aufbewahrungspflicht: 10 Jahre für alle Belege (§14b UStG)"
    )
