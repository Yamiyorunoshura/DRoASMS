ARG UV_VERSION=0.7.3
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/*

FROM base AS runtime

WORKDIR /app

# 放入 uv/uvx 二進位
COPY --from=uvbin /uv /uvx /usr/local/bin/
# 健檢：顯示版本，若抓取失敗可及早中止
RUN uv --version && uvx --version


# 複製專案定義與鎖檔以便快取依賴層
COPY pyproject.toml uv.lock alembic.ini ./
# hatchling 需要 readme/license 檔案存在於專案根目錄
COPY README.md LICENSE ./
COPY src ./src

# 以 uv 建置隔離環境並安裝相依
RUN uv venv .venv \
    && . ./.venv/bin/activate \
    && uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:${PATH}"

# 入口腳本
COPY docker/bin/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

USER 65532:65532

ENTRYPOINT ["/app/entrypoint.sh"]
