# Deployment Guide — einvoice-mcp

Production deployment options for the einvoice-mcp server.

---

## Option 1: Docker Compose (Recommended)

The simplest production setup. Both services (MCP server + KoSIT validator) run in isolated containers.

### Prerequisites

- Docker Engine 24+
- Docker Compose v2+
- 2 GB RAM minimum (KoSIT JVM needs ~1 GB)

### Deploy

```bash
git clone https://github.com/Mavengence/einvoice-mcp.git
cd einvoice-mcp

# Start both services
docker compose -f docker/docker-compose.yml up -d

# Verify health
docker compose -f docker/docker-compose.yml ps
curl http://localhost:8081/server/health  # KoSIT
```

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `KOSIT_URL` | `http://kosit:8081` | KoSIT validator URL (internal Docker network) |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

### Update

```bash
docker compose -f docker/docker-compose.yml pull
docker compose -f docker/docker-compose.yml up -d
```

---

## Option 2: Standalone Python (stdio mode)

For direct integration with Claude Desktop, Cursor, or other MCP clients via stdio transport.

### Prerequisites

- Python 3.11+
- KoSIT validator running separately (Docker or Java)

### Install

```bash
pip install einvoice-mcp
# or from source:
pip install -e .
```

### Run

```bash
# stdio mode (for MCP clients)
python -m einvoice_mcp

# With custom KoSIT URL
KOSIT_URL=http://validator.internal:8081 python -m einvoice_mcp
```

### Claude Desktop Configuration

Add to `~/Library/Application Support/Claude/claude_desktop_config.json`:

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

## Option 3: KoSIT Validator Only (Docker)

If you only need the KoSIT validator (e.g., running the MCP server natively):

```bash
docker build -t kosit-validator -f docker/Dockerfile.kosit docker/
docker run -d --name kosit -p 8081:8081 kosit-validator
```

### Verify

```bash
curl http://localhost:8081/server/health
# Expected: 200 OK
```

---

## Monitoring

### Health Checks

The MCP server exposes a KoSIT health resource:

```
einvoice://system/kosit-status
```

Returns JSON with `healthy`, `url`, and `message` fields.

### Docker Health Checks

Both containers have built-in health checks:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' einvoice-mcp-kosit-1
docker inspect --format='{{.State.Health.Status}}' einvoice-mcp-mcp-server-1
```

### Logging

```bash
# Follow MCP server logs
docker compose -f docker/docker-compose.yml logs -f mcp-server

# Follow KoSIT logs
docker compose -f docker/docker-compose.yml logs -f kosit
```

---

## Security Considerations

### Network Isolation

- KoSIT validator should **not** be exposed to the public internet
- In docker-compose, KoSIT is only accessible within the Docker network
- If exposing externally, use a reverse proxy with authentication

### Input Validation

The MCP server enforces:
- XML size limit: 10 MB
- PDF size limit: 50 MB (base64), 50 MB (decoded)
- XXE protection via defusedxml on all parse paths
- No redirect following on KoSIT HTTP client (SSRF prevention)

### Non-Root Containers

Both Docker images run as non-root users:
- MCP server: `mcp` user (UID 1001)
- KoSIT validator: `kosit` user (UID 1001)

---

## Scaling

### Single Instance

For most use cases (< 100 invoices/day), a single Docker Compose stack is sufficient. Each invoice validation takes ~200ms against KoSIT.

### Multiple Instances

For higher throughput:
1. Run multiple MCP server instances behind a load balancer
2. Share a single KoSIT validator (stateless, handles concurrent requests)
3. KoSIT JVM benefits from more memory: set `-Xmx2g` for high-load scenarios

### Resource Requirements

| Component | CPU | RAM | Disk |
|-----------|-----|-----|------|
| MCP Server | 0.5 core | 256 MB | 100 MB |
| KoSIT Validator | 1 core | 1 GB | 500 MB |

---

## Troubleshooting

### KoSIT Validator Won't Start

```bash
# Check Java memory
docker logs einvoice-mcp-kosit-1 2>&1 | grep -i "memory\|heap\|error"

# Increase JVM memory
docker run -d -e JAVA_OPTS="-Xmx2g" -p 8081:8081 kosit-validator
```

### Connection Refused

```bash
# Verify KoSIT is listening
docker exec einvoice-mcp-kosit-1 curl -s http://localhost:8081/server/health

# Check Docker network
docker network inspect docker_default
```

### Slow Validation

- First validation after startup is slower (JVM warmup)
- Subsequent validations: ~100-200ms
- Large XML files (>1 MB): up to 500ms

---

*Last updated: March 2026*
