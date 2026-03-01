# einvoice-mcp

MCP-Server für deutsche E-Rechnungen — XRechnung & ZUGFeRD Compliance.

Ermöglicht KI-Agenten (Claude, Cursor, Copilot) die Validierung, Erstellung, Analyse und Konformitätsprüfung von elektronischen Rechnungen gemäß EN 16931.

## Tools

| Tool | Beschreibung |
|------|-------------|
| `einvoice_validate_xrechnung` | Validiert XRechnung-XML gegen den KoSIT-Validator |
| `einvoice_validate_zugferd` | Validiert ZUGFeRD-PDF (extrahiert + prüft eingebettetes XML) |
| `einvoice_generate_xrechnung` | Erstellt eine XRechnung-konforme CII-XML-Rechnung |
| `einvoice_generate_zugferd` | Erstellt eine ZUGFeRD-Hybrid-PDF (visuell + maschinenlesbar) |
| `einvoice_parse` | Parst E-Rechnungen (XML oder PDF) in strukturierte Daten |
| `einvoice_check_compliance` | Prüft Pflichtfelder + KoSIT-Validierung mit deutschen Hinweisen |

## Schnellstart

### Voraussetzungen

- Python 3.11+
- Docker (für den KoSIT-Validator)

### Installation

```bash
git clone https://github.com/Mavengence/einvoice-mcp.git
cd einvoice-mcp
pip install -e ".[dev]"
```

### KoSIT-Validator starten

```bash
make docker-up
```

Dies startet den KoSIT-Validator auf Port 8081 und den MCP-Server auf Port 8000.

### Lokaler Betrieb (stdio)

```bash
make dev
```

## Konfiguration

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

Füge in `.cursor/mcp.json` hinzu:

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

## Umgebungsvariablen

| Variable | Standard | Beschreibung |
|----------|----------|-------------|
| `KOSIT_URL` | `http://localhost:8081` | URL des KoSIT-Validators |
| `MCP_PORT` | `8000` | Port für den HTTP-Transport |
| `API_KEY` | — | Optionaler API-Schlüssel |
| `LOG_LEVEL` | `INFO` | Log-Level |

## Beispiel-Prompts

```
Validiere diese XRechnung: [XML einfügen]

Erstelle eine Rechnung von TechCorp GmbH (DE123456789) an ClientCorp GmbH
für 40 Stunden Software-Beratung à 150€/Stunde mit 19% MwSt.

Parse diese E-Rechnung und zeig mir die Positionen.

Prüfe ob diese Rechnung XRechnung-konform ist und gib Verbesserungsvorschläge.
```

## Entwicklung

```bash
make install    # Abhängigkeiten installieren
make test       # Tests mit Coverage ausführen
make lint       # Ruff + MyPy prüfen
make fmt        # Code formatieren
make docker-up  # Docker-Stack starten
```

## Architektur

```
[AI Client] → stdio/HTTP → [FastMCP Server]
                                ├── drafthorse (XML-Erstellung/-Parsing)
                                ├── factur-x (PDF/A-3 Einbettung/Extraktion)
                                ├── reportlab (Visuelles PDF)
                                └── httpx → [KoSIT Validator :8081]
```

## Lizenz

MIT
