.PHONY: help install install-pre-commit format lint type-check format-check pre-commit-all lint-fix ci-local ci ci-full clean test test-container test-container-build test-container-unit test-container-contract test-container-integration test-container-performance test-container-db test-container-economy test-container-council test-container-all test-container-ci

# 與 README 對齊：提供 test-container-all 別名
# （等同於 test-all，會包含整合測試與 SQL 函數測試）
test-container-all: test-all

help: ## 顯示此幫助訊息
	@echo "可用的命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

start-dev: ## 啟動機器人（開發環境，會重建容器）
	docker compose up --build --force-recreate

start-prod: ## 啟動機器人（生產環境，後台執行，只啟動 bot 和 postgres）
	docker compose up -d postgres bot --build --force-recreate

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

format-check: ## 檢查程式碼格式是否正確（black --check）
	uv run black --check src/ tests/

pre-commit-all: ## 對所有檔案執行 pre-commit 檢查
	uv run pre-commit run --all-files

ci-local: format-check lint type-check pre-commit-all ## 執行所有本地 CI 檢查（格式化、lint、型別檢查、pre-commit）
	@echo "✓ 所有本地 CI 檢查通過！"

ci: ## 執行完整的 CI 檢查（包含所有測試）
	docker compose run --rm test ci

clean: ## 清理快取和臨時檔案
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage .coverage.* || true

## Docker 測試容器命令
test-container-build: ## 建置測試容器映像檔
	docker compose build test

test: ## 執行測試容器（預設執行所有測試，不含整合測試）
	docker compose run --rm test

test-unit: ## 使用測試容器執行單元測試
	docker compose run --rm test unit

test-contract: ## 使用測試容器執行合約測試
	docker compose run --rm test contract

test-integration: ## 使用測試容器執行整合測試
	docker compose run --rm test integration

test-integration-timeout: ## 使用測試容器執行整合測試（支援逾時：環境變數 PYTEST_TIMEOUT_SECONDS，例如 900）
	# 範例：PYTEST_TIMEOUT_SECONDS=900 make test-integration-timeout
	PYTEST_TIMEOUT_SECONDS=${PYTEST_TIMEOUT_SECONDS} docker compose run --rm test integration

test-performance: ## 使用測試容器執行效能測試
	docker compose run --rm test performance

test-db: ## 使用測試容器執行資料庫函數測試
	docker compose run --rm test db

test-economy: ## 使用測試容器執行經濟相關測試
	docker compose run --rm test economy

test-council: ## 使用測試容器執行議會相關測試
	docker compose run --rm test council

test-all: ## 使用測試容器執行所有測試類型（含整合測試與 SQL 函數測試）
	docker compose run --rm test all && docker compose run --rm test integration
