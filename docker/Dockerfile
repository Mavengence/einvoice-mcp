# Pin to specific Debian release for reproducibility; update regularly.
# To pin to a SHA-256 digest, run:
#   docker pull python:3.11-slim-bookworm
#   docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim-bookworm
# Then replace with: FROM python:3.11-slim-bookworm@sha256:<digest>
FROM python:3.11-slim-bookworm AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

RUN pip install --no-cache-dir .

# Same pinned image for runtime.
FROM python:3.11-slim-bookworm

RUN groupadd -r mcp && useradd -r -g mcp mcp
WORKDIR /app

COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

USER mcp

# MCP server runs on stdio transport — no HTTP health check needed.
# Container orchestration should use process-level health checks instead.

CMD ["python", "-m", "einvoice_mcp"]
