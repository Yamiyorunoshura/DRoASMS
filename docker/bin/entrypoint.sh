#!/usr/bin/env bash
set -euo pipefail

json_log() {
  # json_log LEVEL EVENT MSG EXTRA_JSON
  # EXTRA_JSON 可為空字串
  local level="$1"; shift
  local event="$1"; shift
  local msg="$1"; shift
  local extra="${1:-}"
  local ts
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  if [[ -n "$extra" ]]; then
    printf '{"ts":"%s","level":"%s","msg":"%s","event":"%s",%s}\n' "$ts" "$level" "$msg" "$event" "$extra"
  else
    printf '{"ts":"%s","level":"%s","msg":"%s","event":"%s"}\n' "$ts" "$level" "$msg" "$event"
  fi
}

# 將 uv 快取導向可寫目錄（避免預設寫入 /.cache 或沿用建置期 root 擁有的快取）
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-run}"
mkdir -p "$UV_CACHE_DIR"
chmod 700 "$UV_CACHE_DIR" || true

missing=()
required=("DISCORD_TOKEN")
for key in "${required[@]}"; do
  if [[ -z "${!key:-}" ]]; then
    missing+=("$key")
  fi
done

if (( ${#missing[@]} > 0 )); then
  json_log "ERROR" "bot.config.error" "missing required environment variables" "\"missing\":[\"${missing[*]}\"]"
  exit 64
fi

# 基本 Schema 檢查（最小化）：若設定了 DATABASE_URL，需為以 postgresql:// 開頭
if [[ -n "${DATABASE_URL:-}" ]]; then
  if [[ "${DATABASE_URL}" != postgresql://* ]]; then
    json_log "ERROR" "bot.config.invalid" "invalid DATABASE_URL; must start with postgresql://" "\"key\":\"DATABASE_URL\""
    exit 78
  fi
fi

# DB 可用性檢查（重試/退避）
: "${RETRY_MAX_ATTEMPTS:=5}"
: "${RETRY_BASE_DELAY_MS:=1000}"
: "${RETRY_MAX_TOTAL_MS:=120000}"
# 單次連線逾時（毫秒）
: "${DB_CONNECT_TIMEOUT_MS:=1000}"

attempt=0
start_ms=$(python - <<'PY'
import time
print(int(time.time()*1000))
PY
)
while :; do
  attempt=$((attempt+1))
  json_log "INFO" "db.connect.attempt" "checking database connectivity" "\"attempt\":${attempt}"
  if python - "$DATABASE_URL" "$DB_CONNECT_TIMEOUT_MS" <<'PY'
import asyncio, sys
import asyncpg

async def main(dsn: str, timeout_s: float) -> int:
    try:
        conn = await asyncpg.connect(dsn=dsn, timeout=timeout_s)
        await conn.close()
        return 0
    except Exception:
        return 1

if __name__ == "__main__":
    dsn = sys.argv[1]
    timeout_ms = int(sys.argv[2]) if len(sys.argv) > 2 else 1000
    code = asyncio.run(main(dsn, timeout_ms/1000.0))
    sys.exit(code)
PY
  then
    json_log "INFO" "db.connect.success" "database connectivity verified" "\"attempt\":${attempt}"
    break
  fi

  now_ms=$(python - <<'PY'
import time
print(int(time.time()*1000))
PY
)
  elapsed=$((now_ms - start_ms))
  if (( elapsed >= RETRY_MAX_TOTAL_MS )); then
    json_log "ERROR" "db.unavailable" "database not reachable within timeout" "\"attempts\":${attempt},\"elapsed_ms\":${elapsed}"
    exit 69
  fi

  # 指數退避 + 最小抖動（±20%）
  delay=$(( RETRY_BASE_DELAY_MS * (2 ** (attempt-1)) ))
  # 上限 10 秒避免過長
  if (( delay > 10000 )); then delay=10000; fi
  # 抖動：±20%
  jitter=$(( (delay * (RANDOM % 21 - 10)) / 100 ))
  sleep_ms=$(( delay + jitter ))
  if (( elapsed + sleep_ms > RETRY_MAX_TOTAL_MS )); then
    sleep_ms=$(( RETRY_MAX_TOTAL_MS - elapsed ))
  fi
  json_log "INFO" "db.connect.retry" "will retry after delay" "\"delay_ms\":${sleep_ms}"
  SLEEP_MS="$sleep_ms" python - <<'PY'
import time, os
ms = int(os.environ.get('SLEEP_MS','0'))
time.sleep(ms/1000)
PY
done

# 預設 Alembic 目標（無 pg_cron 的環境）
: "${ALEMBIC_UPGRADE_TARGET:=003_economy_adjustments}"

json_log "INFO" "bot.migrate.start" "running alembic upgrade" "\"target\":\"${ALEMBIC_UPGRADE_TARGET}\""
if ! alembic upgrade "${ALEMBIC_UPGRADE_TARGET}"; then
  json_log "ERROR" "bot.migrate.error" "alembic upgrade failed" "\"target\":\"${ALEMBIC_UPGRADE_TARGET}\""
  exit 70
fi
json_log "INFO" "bot.migrate.done" "alembic upgrade finished" "\"target\":\"${ALEMBIC_UPGRADE_TARGET}\""

exec python -m src.bot.main
