ARG UV_VERSION=0.7.3
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

# Build stage with all development tools
FROM python:3.13-slim AS build-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1

# Install build dependencies only in build stage
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

# Stage 1: Copy dependency files first for better caching
COPY pyproject.toml uv.lock README.md LICENSE alembic.ini ./

# Create virtual environment and install dependencies
RUN uv venv .venv \
    && . ./.venv/bin/activate \
    && uv sync --frozen --no-dev

# Stage 2: Create separate dev environment only for compilation
RUN uv venv /tmp/dev-venv \
    && . /tmp/dev-venv/bin/activate \
    && uv sync --frozen --group dev --active

# Stage 3: Copy source code after dependencies are installed
COPY src ./src
COPY scripts ./scripts
RUN mkdir -p build/unified build/cython

# Stage 4: Use dev environment to compile with caching
# The compile script already has intelligent caching based on file hashes
RUN . /tmp/dev-venv/bin/activate \
    && python scripts/compile_modules.py compile --incremental \
    && rm -rf /tmp/dev-venv

# Clean up any build artifacts to reduce image size
RUN find build/unified -name "*.o" -delete 2>/dev/null || true

# Runtime stage - minimal image with only what's needed to run
FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/app/.venv/bin:${PATH}" \
    PYTHONPATH="/app/build/unified:/app"

# Install only runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 65532 -s /bin/bash appuser

WORKDIR /app

# Install uv for runtime
COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN uv --version && uvx --version

# Copy only what's needed for runtime
COPY --from=builder --chown=appuser:appuser /app/.venv /app/.venv
COPY --from=builder --chown=appuser:appuser /app/build/unified /app/build/unified
COPY --from=builder --chown=appuser:appuser /app/build/cython /app/build/cython

# Copy runtime configuration files
COPY --chown=appuser:appuser pyproject.toml uv.lock README.md LICENSE alembic.ini ./
COPY --chown=appuser:appuser src ./src
COPY --chown=appuser:appuser scripts ./scripts

# Copy entrypoint script and set permissions
COPY --chown=appuser:appuser docker/bin/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# Switch to non-root user
USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]