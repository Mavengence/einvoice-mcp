# Deutsche E-Rechnungs-Compliance — Leitfaden

Praxisleitfaden für die korrekte Erstellung elektronischer Rechnungen mit dem einvoice-mcp Server nach EN 16931, XRechnung 3.0 und ZUGFeRD 2.x.

---

## Welcher Rechnungstyp (TypeCode)?

```
Standardlieferung/-leistung?
├── Ja → 380 (Handelsrechnung)
└── Nein
    ├── Korrektur einer Rechnung?
    │   ├── Zugunsten des Käufers (Retoure, Rabatt) → 381 (Gutschrift)
    │   └── Fehlerhafte Daten ersetzen → 384 (Korrekturrechnung)
    ├── Teilleistung/Abschlag?
    │   ├── Abschlag VOR Leistung → 876 (Vorauszahlungsrechnung)
    │   ├── Teilleistung erbracht → 875 (Teilrechnung)
    │   └── Endabrechnung → 877 (Schlussrechnung)
    └── Käufer stellt Rechnung? → 389 (Selbstfakturiert)
```

### Pflichtfelder je TypeCode

| TypeCode | BT-25 (Vorherige Rechnungsnr.) | BT-12 (Vertragsnr.) | BT-22 (Hinweis) |
|----------|-------------------------------|----------------------|------------------|
| 380 | — | empfohlen | — |
| 381 | **PFLICHT** | — | empfohlen (Grund) |
| 384 | **PFLICHT** | — | **empfohlen** (Korrekturgrund) |
| 875 | — | **empfohlen** | empfohlen (Leistungsstand) |
| 876 | — | **empfohlen** | empfohlen (Abschlagsnr.) |
| 877 | — | **empfohlen** | **empfohlen** (Auflistung Abschläge) |
| 389 | — | empfohlen | empfohlen |

---

## Umsatzsteuer-Kategorien — Entscheidungsbaum

```
Lieferung/Leistung an Unternehmer?
├── Nein (Privatperson)
│   ├── Steuerpflicht? → S (Standard: 19% oder 7%)
│   ├── Befreit (§4 UStG)? → E (Exempt)
│   └── Kleinunternehmer (§19)? → E + Hinweis
├── Ja (Unternehmer, INLAND)
│   ├── Reguläre Lieferung → S (Standard)
│   ├── §13b UStG (Reverse Charge) → AE
│   └── §4 UStG Befreiung → E
├── Ja (Unternehmer, EU-AUSLAND)
│   ├── Innergemeinschaftliche Lieferung → K (§4 Nr. 1b UStG)
│   └── §13b grenzüberschreitend → AE
└── Ja (DRITTLAND)
    └── Ausfuhrlieferung → G (§4 Nr. 1a UStG)
```

### Kategorie-Details

| Code | Name | Steuersatz | §-Grundlage | Pflichtfelder |
|------|------|-----------|-------------|---------------|
| **S** | Standard | 19% oder 7% | §12 UStG | — |
| **Z** | Nullsatz | 0% | — | — |
| **E** | Befreit | 0% | §4 UStG | BT-120 (Befreiungsgrund), BT-121 (Code) |
| **AE** | Reverse Charge | 0% | §13b UStG | BT-31 (Verkäufer USt-IdNr.), BT-48 (Käufer USt-IdNr.) |
| **K** | Innergemeinschaftlich | 0% | §4/1b UStG | BT-48 (Käufer USt-IdNr.), verschiedene Länder |
| **G** | Ausfuhr | 0% | §4/1a UStG | Nachweis der Ausfuhr |
| **O** | Nicht steuerbar | — | — | — |
| **L** | Kanarische Inseln | IGIC | — | — |
| **M** | Ceuta/Melilla | IPSI | — | — |

### Ermäßigter Steuersatz (7%)

Gilt für (§12 Abs. 2 UStG):
- Lebensmittel (außer Getränke und Gastronomie)
- Bücher, Zeitungen, Zeitschriften
- Kunstgegenstände
- Personenbeförderung im Nahverkehr
- Eintrittskarten (Theater, Konzerte, Museen)
- Beherbergungsleistungen
- Landwirtschaftliche Erzeugnisse

---

## Leitweg-ID (BT-10) — Pflicht bei XRechnung

### Format
```
[Grobadresse]-[Feinadresse]-[Prüfziffer]
Beispiel: 04011000-12345-67
```

- **Grobadresse**: Identifiziert die übergeordnete Behörde (z.B. Bundesland, Kommune)
- **Feinadresse**: Identifiziert die einzelne Dienststelle
- **Prüfziffer**: 2-stellig, Modulo 97-Verfahren

### Wo finde ich die Leitweg-ID?

1. **Vergabeunterlagen**: In der Auftragserteilung angegeben
2. **Auftraggeber direkt fragen**: Die Behörde ist verpflichtet, sie mitzuteilen
3. **E-Rechnungsportale**: ZRE (Zentraler Rechnungseingang) bzw. OZG-RE der Länder

### Häufige Fehler

- Leitweg-ID vergessen → XRechnung wird abgelehnt
- Format falsch (keine Bindestriche) → Validierungsfehler
- Leitweg-ID des falschen Auftraggebers → Rechnung erreicht falsche Stelle

---

## Zahlungsarten (PaymentMeansCode)

| Code | Zahlungsart | Zusätzliche Pflichtfelder |
|------|-------------|--------------------------|
| **58** | SEPA-Überweisung | BT-84 (IBAN), optional BT-86 (BIC) |
| **59** | SEPA-Lastschrift | BT-89 (Mandatsreferenz), BT-91 (Käufer-IBAN) |
| **48** | Kreditkarte | BT-87 (PAN, letzte 4-6 Stellen) |
| **30** | Banküberweisung | BT-84 (IBAN) |
| **1** | Nicht festgelegt | — |
| **10** | Bar | — |
| **49** | Abbuchung | BT-84 (IBAN) |
| **57** | Dauerauftrag | BT-84 (IBAN) |
| **68** | Online-Zahlung | — |

### SEPA-Überweisung (empfohlen für B2B/B2G)

```
payment_means_type_code: '58'
seller_iban: 'DE89370400440532013000'
seller_bic: 'COBADEFFXXX'  # optional bei DE-IBAN
```

### SEPA-Lastschrift

```
payment_means_type_code: '59'
mandate_reference_id: 'MREF-2026-001'
buyer_iban: 'DE89370400440532013000'
```

---

## Reverse Charge (§13b UStG)

### Wann gilt Reverse Charge?

1. **§13b Abs. 1**: Leistender im EU-Ausland, Empfänger ist Unternehmer
2. **§13b Abs. 2 Nr. 1**: Werklieferungen eines EU-Unternehmers
3. **§13b Abs. 2 Nr. 4**: Bauleistungen (auch inländisch!)
4. **§13b Abs. 2 Nr. 5**: Gebäudereinigung
5. **§13b Abs. 2 Nr. 6**: Lieferung von Gold
6. **§13b Abs. 2 Nr. 10**: Handylieferungen > 5.000€
7. **§13b Abs. 2 Nr. 11**: Metalle (Anlage 4 UStG)

### Pflichtangaben auf der Rechnung

- **Kategorie**: `AE` für alle Positionen
- **Steuersatz**: `0.00`
- **Verkäufer USt-IdNr.** (BT-31): Pflicht
- **Käufer USt-IdNr.** (BT-48): Pflicht
- **Hinweis**: „Steuerschuldnerschaft des Leistungsempfängers" (§14a Abs. 5 UStG)
- **Befreiungscode**: `vatex-eu-ae`

### Hinweis: Inländischer Reverse Charge

Bei Bauleistungen (§13b Abs. 2 Nr. 4) und Gebäudereinigung (Nr. 5) ist Reverse Charge auch bei gleichem Land möglich. Der MCP-Server gibt bei gleichem Ländercode eine Warnung (advisory), keinen Fehler.

---

## Innergemeinschaftliche Lieferung (§4 Nr. 1b UStG)

### Voraussetzungen

1. Lieferung eines Gegenstands (keine Dienstleistung)
2. Verkäufer und Käufer in **verschiedenen** EU-Ländern
3. Käufer ist Unternehmer mit gültiger USt-IdNr.
4. Gegenstand wird in anderen EU-Staat befördert

### Pflichtangaben

- **Kategorie**: `K`
- **Steuersatz**: `0.00`
- **Käufer USt-IdNr.** (BT-48): Pflicht
- **Befreiungscode**: `vatex-eu-ic`
- **Befreiungsgrund** (BT-120): empfohlen

### Zusammenfassende Meldung (ZM)

Innergemeinschaftliche Lieferungen müssen in der ZM an das BZSt gemeldet werden (§18a UStG). Dies liegt außerhalb des Funktionsumfangs des MCP-Servers.

---

## Kleinunternehmerregelung (§19 UStG)

### Wann anwendbar?

- Vorjahresumsatz ≤ 22.000€ UND
- Voraussichtlicher Umsatz im laufenden Jahr ≤ 50.000€

### Rechnungsstellung

- **Kategorie**: `E` (Exempt)
- **Steuersatz**: nicht ausweisen (0% oder weglassen)
- **Pflichthinweis** (BT-120): „Kein Ausweis der Umsatzsteuer aufgrund Anwendung der Kleinunternehmerregelung gem. §19 UStG"
- **Befreiungscode** (BT-121): `vatex-eu-132`

### Achtung

- **Kein Vorsteuerabzug** für Kleinunternehmer
- Optionale USt-IdNr. trotzdem empfohlen für EU-Geschäfte

---

## Kleinbetragsrechnung (§33 UStDV)

Für Rechnungen ≤ 250€ brutto gelten vereinfachte Anforderungen:

### Mindestangaben

- Name und Anschrift des Verkäufers
- Menge und Art der Lieferung/Leistung
- Bruttobetrag und Steuersatz

### Nicht erforderlich

- Name/Anschrift des Käufers
- Rechnungsnummer (aber empfohlen!)
- Nettobetrag
- Steuerbetrag einzeln ausgewiesen

Der MCP-Server gibt bei Rechnungen ≤ 250€ einen informativen Hinweis aus.

---

## Skonto (Zahlungsabzug)

### Darstellung in XRechnung

```
skonto_percent: 2.0
skonto_days: 10
skonto_base_amount: 1190.00  # optional, Standard: Gesamtbetrag
payment_terms_text: '2% Skonto bei Zahlung innerhalb von 10 Tagen, 30 Tage netto'
```

### Berechnung

- **Skontobasis**: Bruttobetrag (inkl. USt) oder Nettobetrag je nach Vereinbarung
- **Steuerliche Wirkung**: Skonto mindert die Bemessungsgrundlage (§17 Abs. 1 UStG)
- Der MCP-Server berechnet den Skontobetrag automatisch im CII-XML

---

## Handwerkerrechnung (§35a EStG)

### Steuerermäßigung für den Kunden

- 20% der Arbeitskosten absetzbar (max. 1.200€/Jahr)
- Gilt für Renovierung, Erhaltung, Modernisierung des Haushalts

### Pflichten des Handwerkers

1. **Getrennte Ausweisung**: Arbeitskosten und Materialkosten separat
2. **Leistungsort**: Adresse des Kundenhaushalts angeben
3. **Banküberweisung**: Keine Barzahlung (§35a Abs. 5 Satz 3 EStG)!
4. **Rechnung**: Formelle Rechnung nach §14 UStG

### Umsetzung im MCP-Server

- Separate Positionen für Arbeit (`unit_code: 'HUR'`) und Material
- `delivery_location_*`: Adresse des Kundenhaushalts
- `payment_means_type_code: '58'` (SEPA-Überweisung)
- `invoice_note`: Summe der Arbeitskosten als Hinweis

---

## Pflichtfelder-Checkliste: XRechnung 3.0

### Immer erforderlich

- [ ] BT-1: Rechnungsnummer
- [ ] BT-2: Rechnungsdatum
- [ ] BT-3: TypeCode (380, 381, 384, ...)
- [ ] BT-5: Währung (EUR)
- [ ] BT-10: Leitweg-ID / Buyer Reference
- [ ] BT-27: Name des Verkäufers
- [ ] BT-35..40: Adresse des Verkäufers
- [ ] BT-31 oder BT-32: USt-IdNr. oder Steuernummer
- [ ] BT-34: Elektronische Adresse des Verkäufers (schemeID=EM)
- [ ] BT-44: Name des Käufers
- [ ] BT-50..55: Adresse des Käufers
- [ ] BT-49: Elektronische Adresse des Käufers (schemeID=EM)

### XRechnung-spezifisch (BR-DE-Regeln)

- [ ] BT-41: Ansprechpartner Verkäufer (BR-DE-5)
- [ ] BT-42: Telefon Verkäufer (BR-DE-6)
- [ ] BT-43: E-Mail Verkäufer (BR-DE-7)
- [ ] BT-20: Zahlungsbedingungen (BR-DE-15)
- [ ] BT-71 oder BT-73/74: Lieferdatum oder Leistungszeitraum

### Bei SEPA-Überweisung

- [ ] BT-84: IBAN des Verkäufers (BR-DE-23)

### Bei SEPA-Lastschrift

- [ ] BT-89: Mandatsreferenz (BR-DE-24)
- [ ] BT-91: IBAN des Käufers (BR-DE-24)

### Bei Steuerbefreiung (Kategorie E)

- [ ] BT-120: Befreiungsgrund (BR-E-10)
- [ ] BT-121: Befreiungscode

### Bei Gutschrift/Korrektur (381/384)

- [ ] BT-25: Vorherige Rechnungsnummer

---

## Profil-Auswahl

| Szenario | Profil | Erklärung |
|----------|--------|-----------|
| Rechnung an Behörde | `XRECHNUNG` | Pflicht seit 2020 (E-Rechnungsverordnung) |
| Rechnung an Unternehmen | `ZUGFERD_EN16931` | Empfohlen ab 2027 (B2B-Pflicht) |
| Vereinfachte B2B-Rechnung | `ZUGFERD_BASIC` | Weniger Felder, einfacherer Einstieg |
| Erweiterte B2B-Rechnung | `ZUGFERD_EXTENDED` | Zusätzliche Felder über EN 16931 hinaus |

---

## Fristen und Pflichten

| Datum | Pflicht | Grundlage |
|-------|---------|-----------|
| 27.11.2020 | E-Rechnung an Bundesbehörden | E-Rechnungsverordnung |
| 01.01.2025 | E-Rechnung empfangen (alle B2B) | BMF 2024-11-15 |
| 01.01.2027 | E-Rechnung senden (Umsatz > 800K) | Wachstumschancengesetz |
| 01.01.2028 | E-Rechnung senden (alle) | Wachstumschancengesetz |

---

## Häufige Fehler und Lösungen

### 1. „Leitweg-ID fehlt"
→ `buyer_reference` oder `leitweg_id` setzen (fragen Sie den Auftraggeber)

### 2. „BT-31 oder BT-32 fehlt"
→ `seller_tax_id` (USt-IdNr.) oder `seller_tax_number` (Steuernummer) angeben

### 3. „Lieferdatum fehlt"
→ `delivery_date` oder `service_period_start`/`service_period_end` setzen

### 4. „Ansprechpartner fehlt (BR-DE-5)"
→ `seller_contact_name`, `seller_contact_phone`, `seller_contact_email` setzen

### 5. „KoSIT-Validator nicht erreichbar"
→ `make docker-up` ausführen, warten bis Container `healthy` ist

### 6. „IBAN-Format ungültig"
→ IBAN ohne Leerzeichen angeben: `DE89370400440532013000`

### 7. „Reverse Charge: Käufer-USt-IdNr. fehlt"
→ `buyer_tax_id` mit EU-USt-IdNr. des Käufers setzen

---

*Dieses Dokument wird regelmäßig aktualisiert. Stand: März 2026.*
