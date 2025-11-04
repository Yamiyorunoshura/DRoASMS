#!/usr/bin/env bash
set -euo pipefail

# 測試執行腳本
# 支援不同測試類型：unit, contract, integration, performance, db, economy, council, ci

# 設置覆蓋率文件位置到可寫入的目錄（掛載的 htmlcov 目錄）
export COVERAGE_FILE="${COVERAGE_FILE:-/app/htmlcov/.coverage}"

# 設置工具緩存目錄到可寫入的位置（非 root 用戶無法寫入 /app）
export RUFF_CACHE_DIR="${RUFF_CACHE_DIR:-/tmp/ruff_cache}"
export MYPY_CACHE_DIR="${MYPY_CACHE_DIR:-/tmp/mypy_cache}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-/tmp}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/uv-cache}"
export PYTEST_CACHE_DIR="${PYTEST_CACHE_DIR:-/tmp/pytest_cache}"

# 確保緩存目錄存在
mkdir -p "$RUFF_CACHE_DIR" "$MYPY_CACHE_DIR" "$XDG_CACHE_HOME" "$UV_CACHE_DIR" "$PYTEST_CACHE_DIR" 2>/dev/null || true

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
    pytest tests/unit/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_contract() {
    echo "執行合約測試..."
    pytest tests/contracts/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_integration() {
    echo "執行整合測試..."
    export RUN_DISCORD_INTEGRATION_TESTS=1
    pytest tests/integration/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_performance() {
    echo "執行效能測試..."
    pytest tests/performance/ -v -m performance -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_db() {
    echo "執行資料庫函數測試..."
    pytest tests/db/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_economy() {
    echo "執行經濟相關測試..."
    pytest tests/economy/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
}

run_council() {
    echo "執行議會相關測試..."
    pytest tests/council/ -v -n auto -o cache_dir="$PYTEST_CACHE_DIR"
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
