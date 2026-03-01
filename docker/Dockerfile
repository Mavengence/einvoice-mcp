# Pin to specific tag for reproducibility; update regularly.
FROM python:3.11-slim AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

# Pin to same specific tag for reproducibility.
FROM python:3.11-slim

RUN groupadd -r mcp && useradd -r -g mcp mcp
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER mcp

# MCP server runs on stdio transport — no HTTP health check needed.
# Container orchestration should use process-level health checks instead.

CMD ["python", "-m", "einvoice_mcp"]
