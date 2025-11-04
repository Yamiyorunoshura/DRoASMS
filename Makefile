.PHONY: help install install-pre-commit format lint type-check test test-unit test-contract test-economy test-integration test-performance test-db test-council ci-local clean

help: ## 顯示此幫助訊息
	@echo "可用的命令："
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

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

test: ## 執行所有測試
	uv run pytest tests/ -v -n auto

test-unit: ## 執行單元測試
	uv run pytest tests/unit/ -v -n auto

test-contract: ## 執行合約測試
	uv run pytest tests/contracts/ -v -n auto

test-economy: ## 執行經濟相關測試
	uv run pytest tests/economy/ -v -n auto

test-integration: ## 執行整合測試
	uv run pytest tests/integration/ -v -n auto

test-performance: ## 執行效能測試
	uv run pytest tests/performance/ -v -m performance -n auto

test-db: ## 執行資料庫函數測試
	uv run pytest tests/db/ -v -n auto

test-council: ## 執行議會相關測試
	uv run pytest tests/council/ -v -n auto

ci-local: format-check lint type-check pre-commit-all ## 執行所有 CI 檢查（格式化、lint、型別檢查、pre-commit）
	@echo "✓ 所有 CI 檢查通過！"

ci-test: test-unit test-contract test-economy test-db test-council ## 執行所有測試（不含整合測試）
	@echo "✓ 所有測試通過！"

ci-full: ci-local ci-test ## 執行完整的 CI 檢查（包含所有測試）
	@echo "✓ 完整的 CI 檢查通過！"

clean: ## 清理快取和臨時檔案
	find . -type d -name "__pycache__" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -r {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -r {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .coverage .coverage.* || true
