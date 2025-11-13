.PHONY: help install install-pre-commit format lint type-check pyright-check format-check pre-commit-all lint-fix ci-local ci ci-full clean test test-container test-container-build test-container-unit test-container-contract test-container-integration test-container-performance test-container-db test-container-economy test-container-council test-container-all test-container-ci unified-migrate unified-migrate-dry-run unified-compile unified-compile-test unified-compile-clean unified-status unified-refresh-baseline

.DEFAULT_GOAL := help

DOCKER_COMPOSE ?= docker compose
COMPOSE_RUN := $(DOCKER_COMPOSE) run --rm
TEST_RUN := $(COMPOSE_RUN) test

CLEAN_CACHE_DIRS := __pycache__ .pytest_cache .mypy_cache .ruff_cache htmlcov

# 與 README 對齊：提供 test-container-all 別名
# （等同於 test-all，會包含整合測試與 SQL 函數測試）
test-container-all: test-all

help: ## 顯示此幫助訊息
	@echo "可用的命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

start-dev: ## 啟動機器人（開發環境，會重建容器）
	$(DOCKER_COMPOSE) up --build --force-recreate

start-prod: ## 啟動機器人（生產環境，後台執行，只啟動 bot 和 postgres）
	$(DOCKER_COMPOSE) up -d postgres bot --build --force-recreate

install: ## 安裝專案依賴
	uv sync --group dev

install-pre-commit: ## 安裝並啟用 pre-commit hooks
	uv run pre-commit install

format: ## 自動格式化程式碼（black）
	uv run black src/ tests/

lint: ## 執行 linting 檢查（ruff）
	uv run ruff check .

lint-fix: ## 執行 linting 並自動修復（ruff）
	uv run ruff check --fix .

type-check: ## 執行型別檢查（mypy）
	uv run mypy src/

pyright-check: ## 執行 Pyright 型別檢查（嚴格模式）
	uv run pyright src/

format-check: ## 檢查程式碼格式是否正確（black --check）
	uv run black --check src/ tests/

pre-commit-all: ## 對所有檔案執行 pre-commit 檢查
	uv run pre-commit run --all-files

ci-local: format-check lint type-check pyright-check pre-commit-all ## 執行所有本地 CI 檢查（格式化、lint、型別檢查、pre-commit）
	@echo "✓ 所有本地 CI 檢查通過！"

ci: ## 執行完整的 CI 檢查（包含所有測試與整合測試）
	$(TEST_RUN) ci

clean: ## 清理快取和臨時檔案
	@for pattern in $(CLEAN_CACHE_DIRS); do \
		find . -type d -name "$$pattern" -exec rm -r {} + 2>/dev/null || true; \
	done
	@find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@rm -rf .coverage .coverage.* || true

## Docker 測試容器命令
test-container-build: ## 建置測試容器映像檔
	$(DOCKER_COMPOSE) build test

test: ## 執行測試容器（預設執行所有測試，不含整合測試）
	$(TEST_RUN)

test-unit: ## 使用測試容器執行單元測試
	$(TEST_RUN) unit

test-contract: ## 使用測試容器執行合約測試
	$(TEST_RUN) contract

test-integration: ## 使用測試容器執行整合測試
	$(TEST_RUN) integration

test-integration-timeout: ## 使用測試容器執行整合測試（支援逾時：環境變數 PYTEST_TIMEOUT_SECONDS，例如 900）
	# 範例：PYTEST_TIMEOUT_SECONDS=900 make test-integration-timeout
	PYTEST_TIMEOUT_SECONDS=${PYTEST_TIMEOUT_SECONDS} $(TEST_RUN) integration

test-performance: ## 使用測試容器執行效能測試
	$(TEST_RUN) performance

test-db: ## 使用測試容器執行資料庫函數測試
	$(TEST_RUN) db

test-economy: ## 使用測試容器執行經濟相關測試
	$(TEST_RUN) economy

test-council: ## 使用測試容器執行議會相關測試
	$(TEST_RUN) council

test-all: ## 使用測試容器執行所有測試類型（含整合測試與 SQL 函數測試）
	$(TEST_RUN) all && $(TEST_RUN) integration

# ---- 統一編譯器配置 ----
unified-migrate: ## 遷移配置到統一格式
	@echo "遷移編譯配置到統一格式..."
	uv run python scripts/migrate_unified_config.py

unified-migrate-dry-run: ## 試運行配置遷移（不修改文件）
	@echo "試運行配置遷移..."
	uv run python scripts/migrate_unified_config.py --dry-run

unified-compile: ## 使用統一編譯器編譯所有模組
	@echo "使用統一編譯器編譯模組..."
	uv run python scripts/compile_modules.py compile

unified-compile-test: ## 測試統一編譯器配置
	@echo "測試統一編譯器配置..."
	uv run python scripts/compile_modules.py test

unified-compile-clean: ## 清理統一編譯器文件
	@echo "清理統一編譯器文件..."
	uv run python scripts/compile_modules.py clean

unified-refresh-baseline: ## 重新編譯並刷新性能監控基線（確保結果穩定後再執行）
	@echo "刷新統一編譯器性能基線..."
	uv run python scripts/compile_modules.py compile --refresh-baseline

unified-status: ## 顯示統一編譯器狀態
	@echo "=== 統一編譯器狀態 ==="
	@if [ -f "build/unified/compile_report.json" ]; then \
		echo "編譯報告: ✅ 存在"; \
		echo "編譯時間: $$(grep '"compile_time_seconds"' build/unified/compile_report.json | cut -d':' -f2 | tr -d ' ,')"; \
		echo "成功率: $$(grep '"success_rate"' build/unified/compile_report.json | cut -d':' -f2 | tr -d ' ,')"; \
	else \
		echo "編譯報告: ❌ 不存在"; \
	fi
	@if [ -d "build/unified" ]; then \
		echo "編譯模組: $$(find build/unified -name "*.so" | wc -l | tr -d ' ') 個"; \
	else \
		echo "編譯模組: 0 個"; \
	fi
