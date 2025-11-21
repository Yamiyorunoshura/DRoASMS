ARG UV_VERSION=0.7.3
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

# Test stage with development and testing dependencies
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1

# Install test dependencies more efficiently
RUN set -eux; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        curl \
        gnupg \
        build-essential \
        postgresql-client; \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /etc/apt/trusted.gpg.d/pgdg.gpg; \
    apt-get update; \
    apt-get install -y --no-install-recommends pgtap; \
    rm -rf /var/lib/apt/lists/*; \
    useradd -m -u 65532 -s /bin/bash testuser

FROM base AS test-runtime

WORKDIR /app

# Install uv for package management
COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN uv --version && uvx --version

# Stage 1: Copy dependency files first for better caching
COPY pyproject.toml uv.lock alembic.ini ./
COPY README.md LICENSE ./

# Stage 2: Install dependencies with dev tools included
RUN uv venv .venv \
    && . ./.venv/bin/activate \
    && uv sync --frozen --group dev

# Stage 3: Copy source code after dependencies are installed
COPY src ./src
COPY scripts ./scripts
RUN mkdir -p build/unified build/cython

# Stage 4: Compile with incremental caching
RUN . ./.venv/bin/activate \
    && python scripts/compile_modules.py compile --incremental

# Clean up build artifacts to reduce layer size
RUN find build/unified -name "*.o" -delete 2>/dev/null || true

ENV PATH="/app/.venv/bin:${PATH}"
# Make compiled extensions take precedence over pure Python versions
ENV PYTHONPATH="/app/build/unified:/app"

# Copy test entrypoint script
COPY --chown=testuser:testuser docker/bin/test.sh /app/test.sh
RUN chmod +x /app/test.sh

# Switch to non-root user
USER testuser

ENTRYPOINT ["/app/test.sh"]
