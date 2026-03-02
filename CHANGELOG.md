# Changelog

All notable changes to the einvoice-mcp project.

## [0.1.0] — 2026-03-02

### Added

#### MCP Tools (6)
- `einvoice_validate_xrechnung` — XRechnung XML validation via KoSIT
- `einvoice_validate_zugferd` — ZUGFeRD PDF validation (extract + validate)
- `einvoice_generate_xrechnung` — XRechnung 3.0 CII XML generation
- `einvoice_generate_zugferd` — ZUGFeRD hybrid PDF/A-3 generation
- `einvoice_parse` — Parse XML/PDF into structured data
- `einvoice_check_compliance` — Mandatory field checks with German suggestions

#### MCP Resources (11)
- `einvoice://schemas/line-item` — JSON schema for line items
- `einvoice://schemas/allowance-charge` — JSON schema for allowances/charges
- `einvoice://schemas/item-attribute` — JSON schema for item attributes (BG-30)
- `einvoice://schemas/supporting-document` — JSON schema for supporting docs (BG-24)
- `einvoice://schemas/invoice-data` — Full InvoiceData JSON schema
- `einvoice://reference/type-codes` — Invoice type codes (380, 381, 384, 389, 875, 876, 877)
- `einvoice://reference/payment-means-codes` — Payment means codes (58=SEPA, 59=DD, 48=CC, …)
- `einvoice://reference/tax-categories` — EU VAT categories (S, Z, E, AE, K, G, O, L, M)
- `einvoice://reference/unit-codes` — UN/ECE unit codes (H87, HUR, KGM, DAY, …)
- `einvoice://reference/eas-codes` — Electronic Address Scheme codes (EM, 9930, 0204, …)
- `einvoice://system/kosit-status` — On-demand KoSIT validator health check

#### MCP Prompts (8)
- `gutschrift_erstellen` — Credit note (381) creation guide
- `reverse_charge_checkliste` — Reverse charge (§13b UStG) checklist
- `xrechnung_schnellstart` — XRechnung quick start for public procurement
- `korrekturrechnung_erstellen` — Corrective invoice (384) creation guide
- `abschlagsrechnung_guide` — Partial/advance invoice (875/876/877) guide
- `ratenzahlung_rechnung` — Installment payment invoice guide
- `handwerkerrechnung_35a` — Craftsman invoice for §35a EStG tax deduction
- `typecode_entscheidungshilfe` — TypeCode decision tree (which code for which scenario)

#### EN 16931 Business Terms
- BT-1..5 — Invoice number, date, type code, currency
- BT-9..18 — Due date, buyer reference, project/contract/order references, despatch advice, tender reference, invoiced object
- BT-20..25 — Payment terms, invoice note, business process, preceding invoice
- BT-27..43 — Seller party (name, address incl. lines 2/3 and subdivision, VAT ID, tax number, electronic address, contact)
- BT-44..55 — Buyer party (name, address incl. lines 2/3 and subdivision, trading name, electronic address, contact)
- BT-59..65 — Payee party (BG-10), seller tax representative (BG-11)
- BT-70..80 — Delivery location (name, address, identifier)
- BT-71, BT-73/74 — Delivery date, service period
- BT-81..91 — Payment means (type code, text, IBAN, BIC, SEPA DD mandate + buyer IBAN, credit card PAN)
- BT-120/121 — VAT exemption reason text and code
- BT-127 — Line item note
- BT-133 — Buyer accounting reference
- BT-134/135 — Line-level billing period
- BT-147/148 — Gross price and price discount
- BT-155..161 — Item identifiers (seller, buyer, standard/GTIN, classification, country of origin, attributes)
- BG-20/21 — Document-level allowances/charges
- BG-24 — Supporting documents (with embedded binary)
- BG-27/28 — Line-level allowances/charges
- Skonto — Payment discount terms (percent, days, base amount)

#### Tax Categories (all 9 EU VAT)
- S (Standard), Z (Zero), E (Exempt), AE (Reverse charge), K (Intra-community), G (Export), O (Not subject), L (Canary Islands / IGIC), M (Ceuta-Melilla / IPSI)

#### Compliance Rules (25+)
- BR-CO-14 — Tax total = sum of per-group calculated amounts
- BR-CO-10 — Line net amount quantized to 0.01
- BR-DE-5/6/7 — Seller contact name, phone, email
- BR-DE-15 — Payment terms required for XRechnung
- BR-DE-23 — IBAN mandatory for PaymentMeansCode 58
- BR-DE-24 — SEPA DD mandate + buyer IBAN
- BR-E-10 — Exemption reason for TaxCategory E
- §14/4/2 UStG — BT-31 or BT-32 required
- §14/4/6 UStG — BT-71 or BT-73/74 required
- §13b UStG — Reverse charge: seller + buyer VAT IDs, 0% rate
- §4/1a UStG — Export (G): 0% tax rate
- §4/1b UStG — Intra-community (K): buyer VAT ID, 0% rate
- §19 UStG — Kleinunternehmer exemption note advisory
- §33 UStDV — Kleinbetragsrechnung advisory (≤250€)
- BT-25 — Credit note (381) must reference preceding invoice
- 384-BT-25 — Corrective invoice (384) must reference preceding invoice
- RC-COUNTRY — Reverse charge country advisory (domestic §13b allowed)
- IC-COUNTRY — Intra-community country check (different countries required)
- CC-BT-87 — Credit card PAN required when code=48
- REP-BT-63 — Tax rep VAT ID required when BG-11 present
- IBAN — ISO 13616 format validation
- BIC — ISO 9362 format validation
- LW-FMT — Leitweg-ID format advisory
- VAT-FMT — German USt-IdNr. format advisory

#### Profiles
- XRechnung 3.0 (generate, parse, validate, compliance)
- ZUGFeRD EN16931 (generate, parse, validate, compliance)
- ZUGFeRD Basic (generate with correct guideline URI)
- ZUGFeRD Extended (generate with correct guideline URI)

#### Security
- defusedxml XXE/DTD protection on all XML parse paths
- XML size limit (10 MB), PDF size limit (50 MB)
- KoSIT response size cap (10 MB + 512 KB)
- Input reflection sanitization in error messages
- SSRF protection (follow_redirects=False)
- IBAN/BIC injection prevention (format validation)
- Docker: non-root user, SHA-256 checksum verification, KoSIT bound to 127.0.0.1

#### Infrastructure
- Docker Compose stack (MCP server + KoSIT validator)
- KoSIT v1.6.2 with XRechnung scenarios v2026-01-31
- GitHub Actions CI (lint + test)
- PyPI publish workflow
- Makefile for common operations
- Smithery manifest for MCP marketplace
- PEP 561 py.typed marker
- Integration tests for KoSIT validator (5 tests, skipped by default)
- Sample XRechnung 3.0 fixture (tests/fixtures/sample_xrechnung.xml)
- Deployment guide (docs/DEPLOYMENT.md)
- UBL format detection (rejects UBL with clear German error)
- Pydantic validation errors with BT number references
- 531 tests, 100% coverage (2011 stmts), ruff + mypy strict clean
