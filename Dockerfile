FROM python:3.13-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH=/root/.local/bin:$PATH \
    UV_SYSTEM_PYTHON=1

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

# 安裝 uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /app

# 先複製相依檔案以利快取
COPY pyproject.toml uv.lock alembic.ini README.md ./
COPY src ./src

# 安裝相依（以 uv.lock 鎖定版本）
RUN uv sync --frozen --no-dev

ENV PATH=/app/.venv/bin:$PATH

# 預設啟動命令（可被 Compose 覆寫）
CMD ["uv", "run", "-m", "src.bot.main"]

