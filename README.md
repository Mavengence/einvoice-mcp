# einvoice-mcp

**MCP-Server for German e-invoice compliance — XRechnung 3.0 & ZUGFeRD 2.x**

An MCP server that enables AI agents (Claude, Cursor, Copilot) to validate, generate, parse, and check compliance of electronic invoices per EN 16931 — without a single line of integration code.

---

## Why This Exists

Germany mandated e-invoice reception for B2B as of January 2025 (BMF 2024-11-15). Issuance mandates follow in 2027 (Vorjahresumsatz > 800K) and 2028 (all businesses). Every German company needs tooling — this MCP server gives AI agents that capability.

---

## Compliance Proof

**475 tests | 99% coverage (1968 stmts, 7 defensive) | 0 failures | lint clean (ruff + mypy strict)**

*Run `make test` to verify.*

### EN 16931 / XRechnung 3.0 Field Coverage

Every mandatory Business Term is tested in generated XML output:

| BT | Field | Test | Result |
|----|-------|------|--------|
| BT-1 | Invoice number | `test_contains_invoice_id` | PASS |
| BT-2 | Issue date | `test_produces_valid_xml` | PASS |
| BT-3 | Invoice type code (380/381/384) | `test_type_code_380_rechnung`, `test_type_code_381_gutschrift` | PASS |
| BT-5 | Currency code (EUR) | `test_currency_eur` | PASS |
| BT-10 | Buyer reference / Leitweg-ID | `test_buyer_reference_set` | PASS |
| BT-27 | Seller name | `test_contains_seller` | PASS |
| BT-31 | Seller VAT ID (schemeID=VA) | `test_tax_registration_scheme_id_correct` | PASS |
| BT-32 | Seller tax number (schemeID=FC) | `test_steuernummer_bt32_scheme_fc` | PASS |
| BT-34 | Seller electronic address (schemeID=EM) | `test_seller_electronic_address_bt34` | PASS |
| BT-35..40 | Seller address | `test_contains_seller` | PASS |
| BT-41 | Seller contact name (BR-DE-5) | `test_seller_contact_br_de_5` | PASS |
| BT-42 | Seller contact phone | `test_seller_contact_phone` | PASS |
| BT-43 | Seller contact email (BR-DE-7) | `test_seller_contact_email_br_de_7` | PASS |
| BT-44 | Buyer name | `test_contains_buyer` | PASS |
| BT-49 | Buyer electronic address (schemeID=EM) | `test_buyer_electronic_address_bt49` | PASS |
| BT-50..55 | Buyer address | `test_contains_buyer` | PASS |
| BT-71 | Delivery date (§14 Abs. 4 Nr. 6 UStG) | `test_delivery_date_bt71` | PASS |
| BT-20 | Payment terms text | `test_payment_terms_text_roundtrip` | PASS |
| BT-22 | Invoice note | `test_invoice_note_roundtrip` | PASS |
| BT-73/74 | Service period start/end | `test_service_period_bt73_bt74` | PASS |
| BT-11 | Project reference | `test_project_reference_bt11` | PASS |
| BT-12 | Contract reference | `test_contract_reference_bt12` | PASS |
| BT-13 | Purchase order reference | `test_purchase_order_reference_bt13` | PASS |
| BT-25 | Preceding invoice number | `test_preceding_invoice_bt25` | PASS |
| BT-81 | Payment means type code | `test_payment_means_type_code_custom` | PASS |
| BT-83 | Remittance information | `test_remittance_information_roundtrip` | PASS |
| BT-84 | IBAN (SEPA credit transfer) | `test_iban_in_xml` | PASS |
| BT-9 | Due date | `test_due_date_roundtrip` | PASS |
| BT-14 | Sales order reference | `test_sales_order_roundtrip` | PASS |
| BT-29 | Seller registration ID (GLN) | `test_seller_registration_id_roundtrip` | PASS |
| BT-36/37 | Seller address lines 2/3 | `test_address_lines_full_roundtrip` | PASS |
| BT-44 | Buyer contact name | `test_buyer_contact_roundtrip` | PASS |
| BT-46 | Buyer contact phone | `test_buyer_contact_roundtrip` | PASS |
| BT-47 | Buyer contact email | `test_buyer_contact_roundtrip` | PASS |
| BT-51/52 | Buyer address lines 2/3 | `test_address_lines_full_roundtrip` | PASS |
| BT-70..80 | Delivery location | `test_delivery_location_roundtrip` | PASS |
| BT-127 | Line item note | `test_item_note_roundtrip` | PASS |
| BT-155 | Seller item identifier | `test_seller_item_id_roundtrip` | PASS |
| BT-156 | Buyer item identifier | `test_buyer_item_id_roundtrip` | PASS |
| BT-157 | Standard item ID (GTIN) | `test_standard_item_id_roundtrip` | PASS |
| BG-20/21 | Document-level allowances/charges | `test_allowance_roundtrip` | PASS |
| BG-27/28 | Line-level allowances/charges | `test_line_allowance_roundtrip` | PASS |
| BT-16 | Despatch advice reference | `test_despatch_advice_roundtrip` | PASS |
| BT-18 | Invoiced object identifier | `test_invoiced_object_identifier_roundtrip` | PASS |
| BT-23 | Business process type | `test_business_process_type_roundtrip` | PASS |
| BT-89 | SEPA mandate reference (BG-19) | `test_sepa_direct_debit_roundtrip` | PASS |
| BT-91 | Buyer IBAN (BG-19) | `test_sepa_direct_debit_roundtrip` | PASS |
| BT-120 | VAT exemption reason text (BR-E-10) | `test_exemption_reason_roundtrip` | PASS |
| BT-121 | VAT exemption reason code | `test_exemption_reason_roundtrip` | PASS |
| BT-28 | Seller trading name | `test_trading_names_roundtrip` | PASS |
| BT-45 | Buyer trading name | `test_trading_names_roundtrip` | PASS |
| BT-17 | Tender or lot reference | `test_tender_reference_roundtrip` | PASS |
| BT-133 | Buyer accounting reference | `test_bt133_roundtrip` | PASS |
| BT-134/135 | Line-level billing period | `test_line_period_roundtrip` | PASS |
| BT-147/148 | Gross price / price discount | `test_gross_price_and_discount_roundtrip` | PASS |
| BT-158 | Item classification (CPV, etc.) | `test_item_classification_roundtrip` | PASS |
| BG-11 | Seller tax representative (BT-62..65) | `test_seller_tax_rep_roundtrip` | PASS |
| BG-10 | Payee party (BT-59..61) | `test_payee_party_roundtrip` | PASS |
| BG-18 | Payment card (BT-87/88) | `test_payment_card_roundtrip` | PASS |
| BT-159 | Item country of origin | `test_country_of_origin_roundtrip` | PASS |
| BG-30 | Item attributes (BT-160/161) | `test_single_attribute_roundtrip` | PASS |
| BT-15 | Receiving advice reference | `test_receiving_advice_roundtrip` | PASS |
| BT-71 | Delivery location identifier | `test_delivery_location_id_roundtrip` | PASS |
| BT-82 | Payment means text | `test_payment_means_text_roundtrip` | PASS |
| BG-24 | Supporting documents (BT-122..125) | `test_supporting_doc_with_uri` | PASS |
| Skonto | Payment discount terms | `test_skonto_roundtrip` | PASS |

### Calculation Rules

| Rule | Description | Test | Result |
|------|-------------|------|--------|
| BR-CO-14 | TaxTotalAmount = sum of per-group CalculatedAmount | `test_br_co_14_tax_total_equals_sum_of_trade_tax` | PASS |
| BR-CO-14 | PDF/XML/API totals use identical per-group rounding | `test_total_tax_uses_per_group_rounding` | PASS |
| BR-CO-10 | Line item LineTotalAmount quantized to 0.01 | `test_line_item_net_amount_quantized` | PASS |
| BR-DE-23 | IBAN mandatory when PaymentMeansCode=58 | `test_iban_missing_flags_bt84` | PASS |
| §14/4/2 | BT-31 or BT-32 must be present | `test_neither_bt31_nor_bt32_flags_missing` | PASS |
| §14/4/6 | BT-71 or BT-73/74 must be present | `test_no_delivery_date_or_period_flags_missing` | PASS |
| BT-3 | TypeCode validated against EN 16931 codes | `test_invalid_type_code_rejected` | PASS |
| BT-25 | Credit note (381) must reference preceding invoice | `test_credit_note_without_bt25_flags_missing` | PASS |
| §13b UStG | Reverse charge: seller+buyer VAT IDs, 0% rate | `test_reverse_charge_*` | PASS |
| §4/1b UStG | Intra-community (K): buyer VAT ID, 0% rate | `test_k_*` | PASS |
| §19 UStG | Kleinunternehmer: exemption note advisory | `test_exempt_without_note_suggests_ku` | PASS |
| LW-FMT | Leitweg-ID format advisory | `test_invalid_leitweg_format` | PASS |
| VAT-FMT | German USt-IdNr. format advisory (DE + 9 digits) | `test_invalid_german_vat_format` | PASS |
| §4/1a UStG | Export (G): 0% tax rate | `test_export_g_*` | PASS |
| §33 UStDV | Kleinbetragsrechnung advisory (≤250€) | `test_small_invoice_gets_kb_hint` | PASS |
| BR-E-10 | Exemption reason required for TaxCategory E | `test_compliance_missing_exemption_reason` | PASS |
| BR-DE-24 | SEPA DD: mandate (BT-89) + buyer IBAN (BT-91) | `test_dd_missing_mandate_and_iban` | PASS |
| BR-DE-15 | Payment terms (BT-20) required for XRechnung | `test_payment_terms_missing` | PASS |
| CC-BT-87 | Credit card PAN required when code=48 | `test_credit_card_missing_pan` | PASS |
| REP-BT-63 | Tax rep VAT ID required when BG-11 present | `test_tax_rep_without_tax_id` | PASS |
| IBAN | IBAN format validation (ISO 13616) | `test_invalid_iban_*` | PASS |
| BIC | BIC format validation (ISO 9362) | `test_invalid_bic_*` | PASS |

### Parsing Fidelity

| Scenario | Description | Test | Result |
|----------|-------------|------|--------|
| SchemeID stripping | `DE123456789 (VA)` → `DE123456789` | `test_str_element_strips_scheme_id` | PASS |
| Numeric schemeID | `4000000000098 (9930)` → `4000000000098` | `test_strips_numeric_scheme` | PASS |
| Description text | `Reisekosten (pauschal)` preserved | `test_preserves_lowercase_parens` | PASS |
| Unicode safety | `Artikel (3Ü)` preserved (not stripped) | `test_preserves_unicode_parens` | PASS |
| BT-32 roundtrip | Steuernummer FC generate → parse | `test_steuernummer_roundtrip` | PASS |
| TypeCode roundtrip | 381 Gutschrift generate → parse | `test_type_code_381_roundtrip` | PASS |
| Delivery date roundtrip | BT-71 generate → parse | `test_delivery_date_roundtrip` | PASS |
| Service period roundtrip | BT-73/74 generate → parse | `test_service_period_roundtrip` | PASS |
| Electronic address roundtrip | BT-34 generate → parse | `test_seller_electronic_address_roundtrip` | PASS |
| Invoice note roundtrip | BT-22 generate → parse | `test_invoice_note_roundtrip` | PASS |
| Payment terms roundtrip | BT-20 generate → parse | `test_payment_terms_text_roundtrip` | PASS |
| Payment terms override | BT-20 text overrides days | `test_payment_terms_text_overrides_days` | PASS |
| Purchase order roundtrip | BT-13 generate → parse | `test_purchase_order_reference_bt13` | PASS |
| Contract roundtrip | BT-12 generate → parse | `test_contract_reference_bt12` | PASS |
| Project roundtrip | BT-11 generate → parse | `test_project_reference_bt11` | PASS |
| Preceding invoice roundtrip | BT-25 generate → parse | `test_preceding_invoice_bt25` | PASS |
| Remittance roundtrip | BT-83 generate → parse | `test_remittance_information_roundtrip` | PASS |
| Empty scheme stripping | `"PO-42 ()"` → `"PO-42"` | `test_strips_empty_parens` | PASS |
| Roundtrip invoice | Generate → Parse → Verify key fields | `test_xrechnung_roundtrip` | PASS |
| Due date roundtrip | BT-9 generate → parse | `test_due_date_roundtrip` | PASS |
| Address line 2/3 roundtrip | BT-36/37, BT-51/52 generate → parse | `test_address_lines_full_roundtrip` | PASS |
| Buyer contact roundtrip | BT-44/46/47 generate → parse | `test_buyer_contact_roundtrip` | PASS |
| Registration ID roundtrip | BT-29 generate → parse | `test_seller_registration_id_roundtrip` | PASS |
| Sales order roundtrip | BT-14 generate → parse | `test_sales_order_roundtrip` | PASS |
| Item identifiers roundtrip | BT-155/156/157 generate → parse | `test_all_item_ids_together` | PASS |
| Line item note roundtrip | BT-127 generate → parse | `test_item_note_roundtrip` | PASS |
| Delivery location roundtrip | BT-70..80 generate → parse | `test_delivery_location_roundtrip` | PASS |
| Allowance roundtrip | BG-20 generate → parse | `test_allowance_roundtrip` | PASS |
| Charge roundtrip | BG-21 generate → parse | `test_charge_roundtrip` | PASS |
| Line allowance roundtrip | BG-27 generate → parse | `test_line_allowance_roundtrip` | PASS |
| Despatch advice roundtrip | BT-16 generate → parse | `test_despatch_advice_roundtrip` | PASS |
| Invoiced object roundtrip | BT-18 generate → parse | `test_invoiced_object_identifier_roundtrip` | PASS |
| Business process roundtrip | BT-23 generate → parse | `test_business_process_type_roundtrip` | PASS |
| SEPA direct debit roundtrip | BG-19 generate → parse | `test_sepa_direct_debit_roundtrip` | PASS |
| Skonto roundtrip | PaymentDiscountTerms generate → parse | `test_skonto_roundtrip` | PASS |
| BT-133 roundtrip | Buyer accounting reference generate → parse | `test_bt133_roundtrip` | PASS |
| Trading names roundtrip | BT-28/BT-45 generate → parse | `test_trading_names_roundtrip` | PASS |
| Tender reference roundtrip | BT-17 generate → parse | `test_tender_reference_roundtrip` | PASS |
| Exemption reason roundtrip | BT-120/BT-121 generate → parse | `test_exemption_reason_roundtrip` | PASS |
| Line period roundtrip | BT-134/BT-135 generate → parse | `test_line_period_roundtrip` | PASS |
| Seller tax rep roundtrip | BG-11 generate → parse | `test_seller_tax_rep_roundtrip` | PASS |
| Payee roundtrip | BT-59/60/61 generate → parse | `test_payee_party_roundtrip` | PASS |
| Payment card roundtrip | BT-87/88 generate → parse | `test_payment_card_roundtrip` | PASS |
| Gross price roundtrip | BT-147/148 generate → parse | `test_gross_price_and_discount_roundtrip` | PASS |
| Classification roundtrip | BT-158 generate → parse | `test_item_classification_roundtrip` | PASS |
| Country of origin roundtrip | BT-159 generate → parse | `test_country_of_origin_roundtrip` | PASS |
| Item attributes roundtrip | BT-160/161 generate → parse | `test_single_attribute_roundtrip` | PASS |
| Receiving advice roundtrip | BT-15 generate → parse | `test_receiving_advice_roundtrip` | PASS |
| Delivery location ID roundtrip | BT-71 generate → parse | `test_delivery_location_id_roundtrip` | PASS |
| Payment means text roundtrip | BT-82 generate → parse | `test_payment_means_text_roundtrip` | PASS |
| Supporting docs roundtrip | BG-24 generate → parse | `test_supporting_doc_with_uri` | PASS |
| Supporting docs + tender ref | BG-24 + BT-17 coexistence | `test_supporting_docs_coexist_with_tender_ref` | PASS |
| Combined item features | BT-159 + BG-30 + BT-148 together | `test_all_item_features_together` | PASS |
| Multi-reference coexistence | BT-17 + BT-18 in same invoice | `test_tender_and_invoiced_object_coexist` | PASS |
| Non-ASCII party names | Cyrillic/Chinese names | `test_non_ascii_party_names` | PASS |
| All type codes | 380, 381, 384, 389, 875, 876, 877 | `test_all_type_codes` | PASS |
| All tax categories | S, Z, E, AE, K, G, O, L, M | `test_all_tax_categories` | PASS |
| 50 line items | Large invoice build + parse | `test_many_line_items` | PASS |

### Tax Category Coverage (All 9 EU VAT Categories)

| Category | Code | Description | Result |
|----------|------|-------------|--------|
| Standard | S | 19% / 7% USt | PASS |
| Zero | Z | 0% rated | PASS |
| Exempt | E | Exempt | PASS |
| Reverse charge | AE | Reverse charge (Umkehr der Steuerschuld) | PASS |
| Intra-community | K | EU supply (innergemeinschaftliche Lieferung) | PASS |
| Export | G | Outside EU (Drittlandslieferung) | PASS |
| Not subject | O | No VAT | PASS |
| Canary Islands | L | IGIC | PASS |
| Ceuta/Melilla | M | IPSI | PASS |

### Security Hardening

| Attack Vector | Protection | Test | Result |
|---------------|-----------|------|--------|
| XXE entity expansion | defusedxml pre-screen | `test_parse_xml_blocks_xxe` | PASS |
| Billion laughs (entity bomb) | defusedxml pre-screen | `test_parse_xml_blocks_billion_laughs` | PASS |
| External entity injection | defusedxml pre-screen | `test_parse_xml_blocks_external_entity` | PASS |
| XML bomb (>10 MB) | Size limit | `test_validate_rejects_oversized_xml` | PASS |
| PDF bomb (>50 MB base64) | Size limit | `test_validate_rejects_oversized_pdf` | PASS |
| Decoded PDF bomb (>50 MB) | Post-decode guard | `test_validate_rejects_oversized_decoded_pdf` | PASS |
| KoSIT response bomb | 10 MB + 512 KB cap | `test_oversized_content_length_header` | PASS |
| Input reflection in errors | Sanitized | `test_parse_rejects_unknown_file_type` | PASS |
| Error detail leakage | Generic messages | `test_connection_error_no_hostname_in_message_de` | PASS |
| SSRF via redirect | `follow_redirects=False` | Defense-in-depth | HARDENED |
| Supply chain (Docker) | SHA-256 checksum verification | `Dockerfile.kosit` | HARDENED |
| Container privilege | Non-root user (both containers) | `Dockerfile`, `Dockerfile.kosit` | HARDENED |
| Port exposure | KoSIT bound to 127.0.0.1 only | `docker-compose.yml` | HARDENED |
| Supply chain (Python) | `uv.lock` for reproducible builds | `uv.lock` | HARDENED |
| IBAN injection | ISO 13616 format validation | `test_invalid_iban_*` | HARDENED |
| BIC injection | ISO 9362 format validation | `test_invalid_bic_*` | HARDENED |

### Profile Coverage

| Profile | Generate | Parse | Validate | Compliance |
|---------|----------|-------|----------|------------|
| XRechnung 3.0 | PASS | PASS | PASS | PASS |
| ZUGFeRD EN16931 | PASS | PASS | PASS | PASS |
| ZUGFeRD Basic | PASS* | - | - | - |
| ZUGFeRD Extended | PASS* | - | - | - |

*\* Generation produces XML with correct guideline URI; full parse/validate/compliance support planned.*

### Module Coverage

| Module | Stmts | Miss | Coverage |
|--------|-------|------|----------|
| `config.py` | 16 | 0 | **100%** |
| `errors.py` | 36 | 0 | **100%** |
| `models.py` | 311 | 0 | **100%** |
| `services/invoice_builder.py` | 329 | 0 | **100%** |
| `services/kosit.py` | 80 | 0 | **100%** |
| `services/pdf_generator.py` | 182 | 0 | **100%** |
| `services/xml_parser.py` | 689 | 7 | **99%** |
| `tools/compliance.py` | 203 | 0 | **100%** |
| `tools/generate.py` | 50 | 0 | **100%** |
| `tools/parse.py` | 39 | 0 | **100%** |
| `tools/validate.py` | 33 | 0 | **100%** |
| **TOTAL** | **1968** | **7** | **99%** |

*`server.py` excluded — FastMCP Context cannot be unit-tested; helper functions tested in `test_server_helpers.py`.*

---

## Tools

| Tool | Description |
|------|-------------|
| `einvoice_validate_xrechnung` | Validates XRechnung XML against the KoSIT Validator |
| `einvoice_validate_zugferd` | Validates ZUGFeRD PDF (extracts + validates embedded XML) |
| `einvoice_generate_xrechnung` | Generates an XRechnung-compliant CII XML invoice |
| `einvoice_generate_zugferd` | Generates a ZUGFeRD hybrid PDF (visual + machine-readable) |
| `einvoice_parse` | Parses e-invoices (XML or PDF) into structured data |
| `einvoice_check_compliance` | Checks mandatory fields + KoSIT validation with German suggestions |

### MCP Resources

| Resource URI | Description |
|-------------|-------------|
| `einvoice://schemas/line-item` | JSON schema for line item objects (items array) |
| `einvoice://schemas/allowance-charge` | JSON schema for allowance/charge objects |
| `einvoice://schemas/invoice-data` | Full JSON schema for InvoiceData with all fields |

---

## Quick Start

### Prerequisites

- Python 3.11+
- Docker (for the KoSIT Validator)

### Installation

```bash
git clone https://github.com/Mavengence/einvoice-mcp.git
cd einvoice-mcp
pip install -e ".[dev]"
```

### Start KoSIT Validator

```bash
make docker-up
```

Starts the KoSIT Validator (v1.6.2, XRechnung scenarios v2026-01-31) on port 8081.

### Local Operation (stdio)

```bash
make dev
```

---

## Configuration

### Claude Desktop

```json
{
  "mcpServers": {
    "einvoice": {
      "command": "python",
      "args": ["-m", "einvoice_mcp"],
      "env": {
        "KOSIT_URL": "http://localhost:8081"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add einvoice -- python -m einvoice_mcp
```

### Cursor

Add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "einvoice": {
      "command": "python",
      "args": ["-m", "einvoice_mcp"],
      "env": {
        "KOSIT_URL": "http://localhost:8081"
      }
    }
  }
}
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KOSIT_URL` | `http://localhost:8081` | KoSIT Validator URL |
| `LOG_LEVEL` | `INFO` | Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL) |

---

## Example Prompts

```
Validiere diese XRechnung: [XML einfügen]

Erstelle eine Rechnung von TechCorp GmbH (DE123456789) an ClientCorp GmbH
für 40 Stunden Software-Beratung à 150€/Stunde mit 19% USt.

Parse diese E-Rechnung und zeig mir die Positionen.

Prüfe ob diese Rechnung XRechnung-konform ist und gib Verbesserungsvorschläge.
```

### Advanced Examples

```
Erstelle eine Gutschrift (TypeCode 381) für Rechnung RE-2025-099 über
200€ netto mit 19% USt.

Erstelle eine Rechnung mit Reverse Charge (§13b UStG, Kategorie AE):
Verkäufer DE123456789, Käufer ATU12345678, Dienstleistung 5.000€.

Erstelle eine Rechnung mit 2% Skonto bei Zahlung innerhalb von 10 Tagen.

Erstelle eine Rechnung mit SEPA-Lastschrift (PaymentMeansCode 59),
Käufer-IBAN DE89370400440532013000, Mandatsreferenz MREF-2025-001.

Erstelle eine Rechnung mit Lieferort: Lager Hamburg, Hafenstraße 42,
20457 Hamburg.

Erstelle eine innergemeinschaftliche Lieferung (Kategorie K) an
einen französischen Kunden (FR12345678901).

Erstelle eine steuerbefreite Rechnung (§19 UStG, Kleinunternehmer)
mit Befreiungsgrund und Code vatex-eu-132.

Erstelle eine Rechnung für ein Vergabeverfahren mit Losnummer VERGABE-2026-42
und Kontierungsreferenz KST-4711 pro Position.
```

---

## Architecture

```
[AI Client] --> stdio --> [FastMCP Server]
                              |-- drafthorse (CII XML generation/parsing)
                              |-- factur-x (PDF/A-3 embedding/extraction)
                              |-- reportlab (Visual PDF rendering)
                              |-- defusedxml (XXE protection on all parse paths)
                              '-- httpx --> [KoSIT Validator :8081]
```

### KoSIT Validator Stack

| Component | Version | Source |
|-----------|---------|--------|
| KoSIT Validator | v1.6.2 (SHA-256 verified) | [itplr-kosit/validator](https://github.com/itplr-kosit/validator) |
| XRechnung Scenarios | v2026-01-31 (SHA-256 verified) | [itplr-kosit/validator-configuration-xrechnung](https://github.com/itplr-kosit/validator-configuration-xrechnung) |
| Java Runtime | Eclipse Temurin 17 | OpenJDK |

---

## Development

```bash
make install    # Install dependencies
make test       # Run tests with coverage
make lint       # Ruff + mypy strict
make fmt        # Format code
make docker-up  # Start Docker stack
```

---

## Supported Business Terms (EN 16931)

| BT/BG | Field | Generate | Parse | Compliance |
|-------|-------|----------|-------|------------|
| BT-1 | Invoice number | Yes | Yes | Yes |
| BT-2 | Issue date | Yes | Yes | Yes |
| BT-3 | Type code (380/381/384) | Yes | Yes | Yes |
| BT-5 | Currency code | Yes | Yes | Yes |
| BT-9 | Due date | Yes | Yes | — |
| BT-10 | Buyer reference / Leitweg-ID | Yes | Yes | Yes |
| BT-11 | Project reference | Yes | Yes | — |
| BT-12 | Contract reference | Yes | Yes | — |
| BT-13 | Purchase order reference | Yes | Yes | — |
| BT-14 | Sales order reference | Yes | Yes | — |
| BT-16 | Despatch advice reference | Yes | Yes | — |
| BT-17 | Tender or lot reference | Yes | Yes | — |
| BT-18 | Invoiced object identifier | Yes | Yes | — |
| BT-20 | Payment terms text | Yes | Yes | — |
| BT-22 | Invoice note | Yes | Yes | — |
| BT-23 | Business process type | Yes | Yes | — |
| BT-25 | Preceding invoice (credit notes) | Yes | Yes | Yes |
| BT-27..40 | Seller party + address (incl. lines 2/3) | Yes | Yes | Yes |
| BT-28 | Seller trading name | Yes | Yes | — |
| BT-29 | Seller registration ID (GLN) | Yes | Yes | — |
| BT-31 | Seller VAT ID (schemeID=VA) | Yes | Yes | Yes |
| BT-32 | Seller tax number (schemeID=FC) | Yes | Yes | Yes |
| BT-34 | Seller electronic address | Yes | Yes | Yes |
| BT-41 | Seller contact name | Yes | Yes | Yes |
| BT-42 | Seller contact phone | Yes | Yes | Yes |
| BT-43 | Seller contact email | Yes | Yes | Yes |
| BT-44..55 | Buyer party + address (incl. lines 2/3) | Yes | Yes | Yes |
| BT-45 | Buyer trading name | Yes | Yes | — |
| BT-46 | Buyer registration ID (GLN) | Yes | Yes | — |
| BT-49 | Buyer electronic address | Yes | Yes | Yes |
| BT-70..80 | Delivery location (name + address) | Yes | Yes | — |
| BT-71 | Delivery date | Yes | Yes | Yes |
| BT-73/74 | Service period | Yes | Yes | Yes |
| BT-81 | Payment means type code | Yes | Yes | — |
| BT-83 | Remittance information | Yes | Yes | — |
| BT-84 | Seller IBAN | Yes | Yes | Yes |
| BT-86 | BIC | Yes | Yes | — |
| BT-89 | SEPA mandate reference | Yes | Yes | Yes |
| BT-91 | Buyer IBAN (SEPA direct debit) | Yes | Yes | Yes |
| BT-120 | VAT exemption reason text | Yes | Yes | Yes |
| BT-121 | VAT exemption reason code | Yes | Yes | — |
| BT-127 | Line item note | Yes | Yes | — |
| BT-155 | Seller item identifier | Yes | Yes | — |
| BT-156 | Buyer item identifier | Yes | Yes | — |
| BT-157 | Standard item ID (GTIN/EAN) | Yes | Yes | — |
| BT-159 | Item country of origin | Yes | Yes | — |
| BT-160/161 | Item attributes (BG-30, name/value) | Yes | Yes | — |
| BG-20/21 | Document-level allowances/charges | Yes | Yes | — |
| BG-27/28 | Line-level allowances/charges | Yes | Yes | — |
| BT-15 | Receiving advice reference | Yes | Yes | — |
| BT-71 | Delivery location identifier | Yes | Yes | — |
| BT-82 | Payment means text | Yes | Yes | — |
| BG-24 | Supporting documents (BT-122..125) | Yes | Yes | — |
| BT-133 | Buyer accounting reference | Yes | Yes | — |
| Skonto | Payment discount terms (percent, days) | Yes | Yes | — |

---

## Gutschrift (Credit Note) Support

For credit notes (TypeCode 381), the server:
- Sets XML header name to "GUTSCHRIFT" and PDF title accordingly
- Requires BT-25 (preceding invoice number) in compliance checks
- Shows "Bezug: [Rechnungsnummer]" in the PDF header
- Validates against EN 16931 type code whitelist (380, 381, 384, 389, 875, 876, 877)

Example: `type_code="381"`, `preceding_invoice_number="RE-2025-099"`

---

## Profile Selection Guide

| Profile | Use Case | Guideline URI |
|---------|----------|---------------|
| `XRECHNUNG` | German public sector (B2G), Leitweg-ID required | `urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0` |
| `ZUGFERD_EN16931` | B2B invoices (default for ZUGFeRD PDF) | `urn:cen.eu:en16931:2017` |
| `ZUGFERD_BASIC` | Simplified B2B invoices | `urn:cen.eu:en16931:2017#compliant#urn:factur-x.eu:1p0:basic` |
| `ZUGFERD_EXTENDED` | Extended B2B invoices with additional fields | `urn:cen.eu:en16931:2017#conformant#urn:factur-x.eu:1p0:extended` |

---

## Limitations

- **ZUGFeRD Basic/Extended**: Generation produces XML with correct guideline URIs, but parsing, validation, and compliance checks are tested for XRechnung 3.0 and ZUGFeRD EN16931 only.
- **Batch processing**: Each tool call processes one invoice. For bulk operations, call the tools in sequence.

---

## Regulatory References

- **EN 16931** — European standard for electronic invoicing
- **XRechnung 3.0 (Szenarien 3.0.2)** — German CIUS (Core Invoice Usage Specification)
- **ZUGFeRD 2.x / Factur-X 1.08** — Hybrid PDF/A-3 invoice format
- **BMF 2024-11-15** — German Federal Ministry of Finance e-invoice mandate
- **§14 UStG** — German VAT Act invoice requirements
- **§14 Abs. 4 Nr. 2 UStG** — Steuernummer or USt-IdNr. required (BT-31 / BT-32)
- **§14 Abs. 4 Nr. 6 UStG** — Delivery date or service period required (BT-71 / BT-73/74)
- **BR-CO-14** — Tax total must equal sum of per-group calculated amounts
- **BR-DE-5** — Seller contact person (mandatory for XRechnung)
- **BR-DE-7** — Seller contact email (mandatory for XRechnung)
- **BR-DE-23** — IBAN mandatory when PaymentMeansCode = 58 (SEPA)
- **§13b UStG** — Reverse charge: seller + buyer VAT IDs required, 0% tax rate
- **§4 Nr. 1b UStG** — Intra-community supply: buyer VAT ID required, 0% tax rate
- **§19 UStG** — Kleinunternehmerregelung: exemption note advisory for TaxCategory E
- **BG-19** — SEPA direct debit (PaymentMeansCode = 59, buyer IBAN, mandate reference)
- **BR-DE-24** — SEPA direct debit: mandate reference + buyer IBAN required
- **BR-E-10** — VAT exemption reason (BT-120) required for TaxCategory E
- **§4 Nr. 1a UStG** — Export outside EU (TaxCategory G): 0% tax rate required
- **§33 UStDV** — Kleinbetragsrechnung advisory (invoices ≤250€ gross)
- **Skonto** — Early payment discount terms (PaymentDiscountTerms in CII)
- **ISO 13616** — IBAN format validation (seller + buyer)
- **ISO 9362** — BIC/SWIFT format validation

---

## License

MIT
