ARG UV_VERSION=0.7.3
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

# Production-optimized build stage
FROM python:3.13-slim AS build-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1

# Install minimal build dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        build-essential \
        git \
    && rm -rf /var/lib/apt/lists/*

FROM build-base AS builder

WORKDIR /app

# Install uv for package management
COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN uv --version && uvx --version

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock README.md LICENSE alembic.ini ./

# Create virtual environment with ONLY production dependencies (no dev dependencies)
RUN uv venv .venv \
    && . ./.venv/bin/activate \
    && uv sync --frozen --no-dev --no-group dev

# Create separate dev environment only for compilation of performance modules
RUN uv venv /tmp/dev-venv \
    && . /tmp/dev-venv/bin/activate \
    && uv sync --frozen --group dev --active

# Copy source code after dependencies are installed
COPY src ./src
COPY scripts ./scripts
RUN mkdir -p build/unified build/cython

# Use dev environment to compile performance modules with caching
RUN . /tmp/dev-venv/bin/activate \
    && python scripts/compile_modules.py compile --incremental \
    && rm -rf /tmp/dev-venv

# Clean up build artifacts to minimize image size
RUN find build/unified -name "*.o" -delete 2>/dev/null || true \
    && find build/cython -name "*.c" -delete 2>/dev/null || true

# Production runtime stage - minimal image
FROM python:3.13-slim AS production

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/build/unified:/app"

# Install only essential runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 65532 -s /bin/bash appuser

WORKDIR /app

# Install uv for runtime package management
COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN uv --version && uvx --version

# Copy only what's needed for production runtime
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/build/unified /app/build/unified
COPY --from=builder --chown=appuser:appuser /app/build/cython /app/build/cython

# Copy essential runtime files
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md LICENSE alembic.ini ./
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser scripts ./scripts

# Copy entrypoint script and set permissions
COPY --chown=appuser:appuser docker/bin/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user for security
USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
