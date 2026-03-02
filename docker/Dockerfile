# Pin to specific Python version for reproducibility.
# To pin to a SHA-256 digest for maximum supply-chain security:
#   docker pull python:3.11-slim-bookworm
#   docker inspect --format='{{index .RepoDigests 0}}' python:3.11-slim-bookworm
# Then replace ARG value with: python@sha256:<digest>
ARG PYTHON_IMAGE=python:3.11-slim-bookworm

FROM ${PYTHON_IMAGE} AS builder

WORKDIR /app
COPY pyproject.toml .
COPY src/ src/

# Install to a fixed prefix — works with any Python version
RUN pip install --no-cache-dir --prefix=/install .

FROM ${PYTHON_IMAGE}

RUN groupadd -r mcp && useradd -r -g mcp mcp
WORKDIR /app

# Copy installed packages from builder (version-independent path)
COPY --from=builder /install /usr/local

USER mcp

# MCP server runs on stdio transport — no HTTP health check needed.
# Container orchestration should use process-level health checks instead.

CMD ["python", "-m", "einvoice_mcp"]
