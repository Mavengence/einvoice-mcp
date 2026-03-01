# einvoice-mcp

**MCP-Server for German e-invoice compliance — XRechnung 3.0 & ZUGFeRD 2.x**

The first MCP server that enables AI agents (Claude, Cursor, Copilot) to validate, generate, parse, and check compliance of electronic invoices per EN 16931 — without a single line of integration code.

---

## Why This Exists

Germany mandated e-invoice reception for B2B as of January 2025 (BMF 2024-11-15). Issuance mandates follow in 2027 (revenue > 800K) and 2028 (all businesses). Every German company needs tooling — this MCP server gives AI agents that capability.

---

## Compliance Proof

**179 tests | 96% coverage | 0 failures | lint clean (ruff + mypy strict)**

*Run `make test` to verify.*

### EN 16931 / XRechnung 3.0 Field Coverage

Every mandatory Business Term is tested in generated XML output:

| BT | Field | Test | Result |
|----|-------|------|--------|
| BT-1 | Invoice number | `test_contains_invoice_id` | PASS |
| BT-2 | Issue date | `test_produces_valid_xml` | PASS |
| BT-3 | Invoice type code (380) | `test_produces_valid_xml` | PASS |
| BT-5 | Currency code (EUR) | `test_currency_eur` | PASS |
| BT-10 | Buyer reference / Leitweg-ID | `test_buyer_reference_set` | PASS |
| BT-27 | Seller name | `test_contains_seller` | PASS |
| BT-31 | Seller VAT ID (schemeID=VA) | `test_tax_registration_scheme_id_correct` | PASS |
| BT-34 | Seller electronic address (schemeID=EM) | `test_seller_electronic_address_bt34` | PASS |
| BT-35..40 | Seller address | `test_contains_seller` | PASS |
| BT-41 | Seller contact name (BR-DE-5) | `test_seller_contact_br_de_5` | PASS |
| BT-42 | Seller contact phone | `test_seller_contact_phone` | PASS |
| BT-43 | Seller contact email (BR-DE-7) | `test_seller_contact_email_br_de_7` | PASS |
| BT-44 | Buyer name | `test_contains_buyer` | PASS |
| BT-49 | Buyer electronic address (schemeID=EM) | `test_buyer_electronic_address_bt49` | PASS |
| BT-50..55 | Buyer address | `test_contains_buyer` | PASS |

### Calculation Rules

| Rule | Description | Test | Result |
|------|-------------|------|--------|
| BR-CO-14 | TaxTotalAmount = sum of per-group CalculatedAmount | `test_br_co_14_tax_total_equals_sum_of_trade_tax` | PASS |

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

### Profile Coverage

| Profile | Generate | Parse | Validate | Compliance |
|---------|----------|-------|----------|------------|
| XRechnung 3.0 | PASS | PASS | PASS | PASS |
| ZUGFeRD EN16931 | PASS | PASS | PASS | PASS |
| ZUGFeRD Basic | PASS | - | - | - |
| ZUGFeRD Extended | PASS | - | - | - |

### Module Coverage

| Module | Stmts | Miss | Coverage |
|--------|-------|------|----------|
| `config.py` | 16 | 0 | **100%** |
| `errors.py` | 36 | 0 | **100%** |
| `models.py` | 101 | 0 | **100%** |
| `services/invoice_builder.py` | 108 | 0 | **100%** |
| `services/kosit.py` | 77 | 1 | **99%** |
| `services/pdf_generator.py` | 70 | 1 | **99%** |
| `services/xml_parser.py` | 157 | 23 | **85%** |
| `tools/compliance.py` | 57 | 2 | **96%** |
| `tools/generate.py` | 56 | 0 | **100%** |
| `tools/parse.py` | 39 | 4 | **90%** |
| `tools/validate.py` | 33 | 2 | **94%** |
| **TOTAL** | **750** | **33** | **96%** |

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

## Regulatory References

- **EN 16931** — European standard for electronic invoicing
- **XRechnung 3.0.2** — German CIUS (Core Invoice Usage Specification)
- **ZUGFeRD 2.x / Factur-X 1.08** — Hybrid PDF/A-3 invoice format
- **BMF 2024-11-15** — German Federal Ministry of Finance e-invoice mandate
- **§14 UStG** — German VAT Act invoice requirements
- **BR-DE-5** — Seller contact person (mandatory for XRechnung)
- **BR-DE-7** — Seller contact email (mandatory for XRechnung)
- **BR-CO-14** — Tax total must equal sum of per-group calculated amounts

---

## License

MIT
