ARG UV_VERSION=0.7.3
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uvbin

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_COLOR=1 \
    PIP_NO_CACHE_DIR=1

RUN set -eux; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates git curl gnupg build-essential; \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /etc/apt/trusted.gpg.d/pgdg.gpg; \
    apt-get update; \
    apt-get install -y --no-install-recommends pgtap; \
    rm -rf /var/lib/apt/lists/*

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
COPY scripts ./scripts
# 注意：tests/ 目錄在運行時透過 volume 掛載，不在建置時複製

# 以 uv 建置隔離環境並安裝開發依賴（包含測試工具）
RUN uv venv .venv \
    && . ./.venv/bin/activate \
    && uv sync --frozen --group dev \
    && mkdir -p build/unified \
    && uv run python scripts/compile_modules.py compile --project-root /app

ENV PATH="/app/.venv/bin:${PATH}"
# 讓編譯後的擴充模組優先於原始純 Python 版本
ENV PYTHONPATH="/app/build/unified:/app"

# 入口腳本
COPY docker/bin/test.sh /app/test.sh
RUN chmod +x /app/test.sh

USER 65532:65532

ENTRYPOINT ["/app/test.sh"]
