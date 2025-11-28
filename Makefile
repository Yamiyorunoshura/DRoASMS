.PHONY: help install install-pre-commit format lint type-check pyright-check format-check pre-commit-all lint-fix ci-local ci ci-full clean test test-container test-container-build test-container-unit test-container-contract test-container-integration test-container-performance test-container-db test-container-economy test-container-council test-container-all test-container-ci unified-migrate unified-migrate-dry-run unified-compile unified-compile-test unified-compile-clean unified-status unified-refresh-baseline compile-check

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

start-dev: ## 啟動機器人（開發環境，包含完整開發工具和 pgadmin）
	$(DOCKER_COMPOSE) --profile dev up -d --build --force-recreate

start-prod: ## 啟動機器人（生產環境，僅啟動 bot 和 postgres，後台執行）
	$(DOCKER_COMPOSE) --profile prod up -d

restart: ## 重啟機器人
	docker compose down && make start-prod

restart-in-dev-mode: ## 重啟機器人（開發環境）
	docker compose down && make start-dev

update: ## 更新專案
	docker compose down && $(DOCKER_COMPOSE) --profile prod up -d --build --force-recreate

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

compile-check: ## 執行 Cython 編譯檢查（增量編譯，錯誤不阻止執行）
	@echo "🔍 執行 Cython 編譯檢查..."
	@uv run python scripts/compile_modules.py compile --incremental; \
	if [ $$? -eq 0 ]; then \
		echo "✅ Cython 編譯檢查通過"; \
	else \
		echo "⚠️  Cython 編譯檢查發現錯誤，但不阻止 CI 繼續執行"; \
	fi

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
