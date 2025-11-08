#!/usr/bin/env bash
set -euo pipefail

# 測試執行腳本
# 支援不同測試類型：unit, contract, integration, performance, db, economy, council, ci

# 設置覆蓋率文件位置到可寫入的目錄（掛載的 htmlcov 目錄）
# 當使用 pytest-xdist 時，pytest-cov 會自動為每個 worker 創建 .coverage.worker* 文件
# 然後在主進程中合併為 .coverage，因此需要確保目錄可寫入
export COVERAGE_FILE="${COVERAGE_FILE:-/app/htmlcov/.coverage}"

# 可選逾時（秒）：若設定 PYTEST_TIMEOUT_SECONDS>0，則以 Python subprocess.run 套用逾時
export PYTEST_TIMEOUT_SECONDS="${PYTEST_TIMEOUT_SECONDS:-0}"

# 設置工具緩存目錄到可寫入的位置（非 root 用戶無法寫入 /app）
export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-/tmp/ruff_cache}"
export MYPY_CACHE_DIR="${MYPY_CACHE_DIR:-/tmp/mypy_cache}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export PYTEST_CACHE_DIR="${PYTEST_CACHE_DIR:-/tmp/pytest_cache}"

# 確保緩存目錄和覆蓋率目錄存在
mkdir -p "$RUFF_CACHE_DIR" "$MYPY_CACHE_DIR" "$XDG_CACHE_HOME" "$UV_CACHE_DIR" "$PYTEST_CACHE_DIR" 2>/dev/null || true
mkdir -p "$(dirname "$COVERAGE_FILE")" 2>/dev/null || true

# 檢查 htmlcov 是否可寫；不可寫時給出明確提示，避免卡住時難以診斷
if ! [ -w "$(dirname "$COVERAGE_FILE")" ]; then
    echo "⚠️  覆蓋率輸出目錄不可寫：$(dirname "$COVERAGE_FILE")" >&2
    echo "   建議：\n   1) 將 compose.yml 的 test 服務以 root 執行（已預設 user: 0:0），或\n   2) 調整本機 htmlcov 權限（例如：chmod 777 htmlcov）" >&2
fi

_run_pytest_with_timeout() {
    # $@: pytest 參數
    if [ "${PYTEST_TIMEOUT_SECONDS}" -gt 0 ]; then
        python3 - << 'PY'
import os, subprocess, sys
timeout = int(os.environ.get("PYTEST_TIMEOUT_SECONDS", "0"))
cmd = ["pytest"] + sys.argv[1:]
try:
    rc = subprocess.run(cmd, timeout=timeout).returncode
    sys.exit(rc)
except subprocess.TimeoutExpired:
    print(f"\n*** pytest 逾時（{timeout}s）— 已中止執行 ***\n", file=sys.stderr)
    sys.exit(124)
PY
        return $?
    else
        pytest "$@"
        return $?
    fi
}

usage() {
    cat <<EOF
用法: test.sh [類型]

類型:
  unit          - 執行單元測試
  contract      - 執行合約測試
  integration   - 執行整合測試（需要 Discord Token）
  performance   - 執行效能測試
  db            - 執行資料庫函數測試
  economy       - 執行經濟相關測試
  council       - 執行議會相關測試
  all           - 執行所有測試類型（不含整合測試）
  ci            - 執行完整 CI 流程（格式化、lint、型別檢查、所有測試）

預設: 執行所有測試（不含整合測試）
EOF
}

run_unit() {
    echo "執行單元測試..."
    # 使用 xdist 並行執行時，pytest-cov 會自動處理多進程覆蓋率合併
    # 每個 worker 會創建 .coverage.worker* 文件，主進程會自動合併
    _run_pytest_with_timeout tests/unit/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_contract() {
    echo "執行合約測試..."
    # 使用 xdist 並行執行時，pytest-cov 會自動處理多進程覆蓋率合併
    _run_pytest_with_timeout tests/contracts/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_integration() {
    echo "執行整合測試..."
    export RUN_DISCORD_INTEGRATION_TESTS=1
    # 整合測試不使用 xdist 並行執行，因為：
    # 1. 整合測試涉及共享資源（資料庫、Docker 容器），並行執行可能導致競爭條件
    # 2. pytest-xdist 與 pytest-cov 在多進程環境下可能導致死鎖
    # 3. 整合測試通常需要順序執行以確保資源狀態一致
    _run_pytest_with_timeout tests/integration/ -v -o cache_dir="$PYTEST_CACHE_DIR"
}

_run_optional_pytest() {
    # 對於空目錄（無測試）時，pytest 會以退出碼 5 結束；此處將其視為成功略過
    local rc=0
    pytest "$@" || rc=$?
    if [ $rc -eq 5 ]; then
        echo "（略過）此類別沒有測試"
        return 0
    fi
    return $rc
}

run_performance() {
    echo "執行效能測試..."
    # 使用 xdist 並行執行時，pytest-cov 會自動處理多進程覆蓋率合併
    _run_optional_pytest tests/performance/ -v -m performance -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_db() {
    echo "執行資料庫函數測試..."

    # 檢查是否有 SQL 測試檔案
    if [ ! -d tests/db ] || [ -z "$(find tests/db -maxdepth 1 -name '*.sql' 2>/dev/null)" ]; then
        echo "（略過）此類別沒有測試"
        return 0
    fi

    # 從 DATABASE_URL 解析連接資訊
    # DATABASE_URL 格式：postgresql://user:password@host:port/database
    if [ -z "${DATABASE_URL:-}" ]; then
        echo "錯誤: DATABASE_URL 環境變數未設定" >&2
        exit 1
    fi

    # 解析 DATABASE_URL
    # 移除 postgresql:// 前綴
    local conn_str="${DATABASE_URL#postgresql://}"
    # 提取 user:password@host:port/database
    local user_pass="${conn_str%%@*}"
    local host_db="${conn_str#*@}"
    local user="${user_pass%%:*}"
    local password="${user_pass#*:}"

    # 檢查是否有端口號（格式：host:port/database 或 host/database）
    if [[ "$host_db" == *:*/* ]]; then
        # 有端口號：host:port/database
        local host="${host_db%%:*}"
        local port_db="${host_db#*:}"
        local port="${port_db%%/*}"
        local database="${port_db#*/}"
    else
        # 無端口號：host/database
        local host="${host_db%%/*}"
        local database="${host_db#*/}"
        local port="5432"  # 預設端口
    fi

    # 設置 PostgreSQL 環境變數供 pg_prove 使用
    export PGHOST="$host"
    export PGPORT="$port"
    export PGUSER="$user"
    export PGPASSWORD="$password"
    export PGDATABASE="$database"

    # 在執行 SQL 測試前，確保資料庫遷移與函數已載入
    # 使用 Alembic 升級至最新版本，讓 schema 與函數（透過遷移檔載入）到位
    echo "遷移資料庫至最新版本（alembic upgrade head）..."
    alembic upgrade head || {
        echo "❌ Alembic 遷移失敗" >&2
        exit 1
    }

    # 防禦性：直接載入最新的治理（最高人民會議）函數，避免因為歷史資料庫狀態或遷移順序
    # 導致新函數尚未存在
    if [ -f /app/src/db/functions/governance/fn_supreme_assembly.sql ]; then
        echo "載入 fn_supreme_assembly.sql ..."
        psql -v ON_ERROR_STOP=1 -f /app/src/db/functions/governance/fn_supreme_assembly.sql || {
            echo "❌ 載入 fn_supreme_assembly.sql 失敗" >&2
            exit 1
        }
    fi

    # 使用 pg_prove 執行 SQL 測試
    pg_prove tests/db/*.sql
}

run_economy() {
    echo "執行經濟相關測試..."
    # 使用 xdist 並行執行時，pytest-cov 會自動處理多進程覆蓋率合併
    _run_optional_pytest tests/economy/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_council() {
    echo "執行議會相關測試..."
    # 使用 xdist 並行執行時，pytest-cov 會自動處理多進程覆蓋率合併
    _run_optional_pytest tests/integration/council/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_all() {
    echo "執行所有測試（不含整合測試）..."
    run_unit
    run_contract
    run_economy
    run_db
    run_council
    run_performance
}

run_ci() {
    echo "執行完整 CI 流程..."

    # 格式化檢查
    echo "檢查程式碼格式..."
    black --check src/ tests/ || {
        echo "❌ 格式化檢查失敗"
        exit 1
    }

    # Lint 檢查
    echo "執行 linting 檢查..."
    ruff check . || {
        echo "❌ Linting 檢查失敗"
        exit 1
    }

    # 型別檢查
    echo "執行型別檢查..."
    mypy src/ --cache-dir="$MYPY_CACHE_DIR" || {
        echo "❌ 型別檢查失敗"
        exit 1
    }

    # Pre-commit 檢查
    echo "執行 pre-commit 檢查..."
    # 在容器中沒有 git 倉庫，直接運行 hooks 而不依賴 git
    if command -v git >/dev/null 2>&1 && [ -d .git ]; then
        pre-commit run --all-files || {
            echo "❌ Pre-commit 檢查失敗"
            exit 1
        }
    else
        echo "⚠️  跳過 pre-commit 檢查（容器環境中沒有 git 倉庫）"
        echo "   提示：本機環境會自動執行 pre-commit hooks"
    fi

    # 執行所有測試（不含整合測試）
    run_all

    echo "✓ 完整的 CI 檢查通過！"
}

# 主邏輯
case "${1:-all}" in
    unit)
        run_unit
        ;;
    contract)
        run_contract
        ;;
    integration)
        run_integration
        ;;
    performance)
        run_performance
        ;;
    db)
        run_db
        ;;
    economy)
        run_economy
        ;;
    council)
        run_council
        ;;
    all)
        run_all
        ;;
    ci)
        run_ci
        ;;
    help|--help|-h)
        usage
        exit 0
        ;;
    *)
        echo "錯誤: 未知的測試類型: $1" >&2
        usage >&2
        exit 1
        ;;
esac
