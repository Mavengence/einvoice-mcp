---
name: einvoice-mcp
description: >
  German e-invoice compliance MCP server for XRechnung 3.0 and ZUGFeRD 2.x.
  Validate, generate, parse, and check compliance of electronic invoices per
  EN 16931 with full German business rule support (BR-DE). Use when working
  with German e-invoices, XRechnung, ZUGFeRD, CII XML, or EN 16931 compliance.
license: MIT
compatibility: Requires Python 3.11+, optional Docker for KoSIT validator
metadata:
  author: mavengence
  version: "0.1.0"
---

# einvoice-mcp

MCP server for German e-invoice compliance — XRechnung 3.0 & ZUGFeRD 2.x.

Germany mandated e-invoice reception for B2B as of January 2025. Issuance mandates follow in 2027/2028. This MCP server gives AI agents full e-invoice capabilities.

## Tools

| Tool | Description |
|------|-------------|
| `einvoice_validate_xrechnung` | Validate XRechnung XML against EN 16931 + German rules via KoSIT |
| `einvoice_validate_zugferd` | Validate ZUGFeRD/Factur-X XML against EN 16931 via KoSIT |
| `einvoice_generate_xrechnung` | Generate compliant XRechnung 3.0 CII XML from structured data |
| `einvoice_generate_zugferd` | Generate ZUGFeRD PDF with embedded CII XML |
| `einvoice_parse` | Parse CII XML or ZUGFeRD PDF into structured data |
| `einvoice_check_compliance` | Check invoice data against XRechnung/ZUGFeRD field requirements |

## Quick Start

### Installation

```bash
pip install -e .
```

### Claude Desktop Configuration

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

### With KoSIT Validator (Docker)

```bash
make docker-up
```

## Example Prompts

- "Generate an XRechnung for Mustermann GmbH selling 10 widgets at 100 EUR each with 19% VAT"
- "Validate this XML invoice against XRechnung 3.0 rules"
- "Parse this ZUGFeRD PDF and extract the invoice data"
- "Check if this invoice is compliant with German e-invoice requirements"
- "Create a Gutschrift (credit note) referencing invoice INV-2024-001"
- "Generate an invoice with Reverse Charge (§13b UStG) for cross-border services"

## Resources

The server provides 26 reference resources covering:
- EN 16931 field reference and BT mappings
- German tax category guide (all 9 EU VAT categories)
- XRechnung mandatory field checklists
- UNTDID type codes and payment means codes
- Reverse Charge and intra-community delivery rules
- Skonto calculation and payment terms

## Documentation

- See [GERMAN_COMPLIANCE_GUIDE.md](docs/GERMAN_COMPLIANCE_GUIDE.md) for detailed compliance guidance
- See [DEPLOYMENT.md](docs/DEPLOYMENT.md) for production deployment
