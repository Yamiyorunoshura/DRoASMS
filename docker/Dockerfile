ARG UV_VERSION=0.7.3
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

FROM python:3.13-slim AS build-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates build-essential git \
    && rm -rf /var/lib/apt/lists/*

FROM build-base AS builder

WORKDIR /app

COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN uv --version && uvx --version

# 先只複製相依定義以提升快取命中率
COPY pyproject.toml uv.lock README.md LICENSE alembic.ini ./

# 建立虛擬環境並安裝執行期相依
RUN uv venv .venv \
    && . ./.venv/bin/activate \
    && uv sync --frozen --no-dev

# 單獨建置 dev 工具環境供 Cython 編譯使用，避免在執行期保留多餘套件
RUN uv venv /tmp/dev-venv \
    && . /tmp/dev-venv/bin/activate \
    && uv sync --frozen --group dev --active

# 複製來源與編譯腳本
COPY src ./src
COPY scripts ./scripts
RUN mkdir -p build/unified

# 以 dev 環境執行統一編譯腳本並清理暫存
RUN . /tmp/dev-venv/bin/activate \
    && python scripts/compile_modules.py compile \
    && rm -rf /tmp/dev-venv backup/python_modules

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=uvbin /uv /uvx /usr/local/bin/
RUN uv --version && uvx --version

COPY --from=builder --chown=65532:65532 /app/.venv /app/.venv
COPY --from=builder --chown=65532:65532 /app/build/unified /app/build/unified

# 需要在執行期可用的專案檔案
COPY --chown=65532:65532 pyproject.toml uv.lock README.md LICENSE alembic.ini ./
COPY --chown=65532:65532 src ./src
COPY --chown=65532:65532 scripts ./scripts

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/app/build/unified:/app"

COPY --chown=65532:65532 docker/bin/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER 65532:65532

ENTRYPOINT ["/app/entrypoint.sh"]
