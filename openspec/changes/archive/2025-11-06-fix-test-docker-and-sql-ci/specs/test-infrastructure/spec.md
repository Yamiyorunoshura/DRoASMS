## MODIFIED Requirements
### Requirement: 測試容器映像檔
系統 SHALL 提供一個獨立的測試容器映像檔，基於 Python 3.13，包含所有測試依賴（dev dependencies），使用 `uv` 管理依賴。測試容器 SHALL 包含執行 SQL 函數測試所需的工具（`pg_prove` 和 PostgreSQL client）。

#### Scenario: 測試容器成功建置
- **WHEN** 開發者執行 `docker build -f docker/test.Dockerfile -t droasms-test .`
- **THEN** 測試容器映像檔成功建置，包含 Python 3.13、`uv`、所有測試依賴（pytest, pytest-cov, pytest-xdist, mypy, ruff, black 等）
- **AND** 測試容器使用非 root 用戶執行
- **AND** 測試容器包含 `pg_prove` 工具（用於執行 pgTAP SQL 測試）

#### Scenario: 測試容器包含所有測試工具
- **WHEN** 測試容器啟動
- **THEN** 容器內可用 `pytest`、`mypy`、`ruff`、`black` 等工具
- **AND** 容器內可用 `pg_prove` 工具執行 SQL 測試
- **AND** 容器內可用 PostgreSQL client 工具（`psql`）連接到資料庫
- **AND** 所有工具版本與 `pyproject.toml` 中定義的版本一致

### Requirement: 測試執行腳本
系統 SHALL 提供統一的測試執行腳本 `docker/bin/test.sh`，支援執行不同類型的測試與 CI 檢查，包括 SQL 函數測試。

#### Scenario: 執行所有測試
- **WHEN** 開發者執行 `docker compose run test`
- **THEN** 腳本執行所有測試類型（unit, contract, integration, performance, db）
- **AND** SQL 函數測試使用 `pg_prove` 正確執行
- **AND** 測試結果輸出到標準輸出
- **AND** 測試失敗時返回非零退出碼

#### Scenario: 執行資料庫函數測試
- **WHEN** 開發者執行 `docker compose run test db`
- **THEN** 腳本使用 `pg_prove` 執行 `tests/db/*.sql` 檔案
- **AND** `pg_prove` 正確連接到 PostgreSQL 服務（使用 `DATABASE_URL` 環境變數）
- **AND** SQL 測試結果輸出到標準輸出
- **AND** 如果 `tests/db/` 目錄為空或沒有 SQL 檔案，腳本不會失敗（優雅處理）

#### Scenario: 執行完整 CI 流程
- **WHEN** 開發者執行 `docker compose run test ci`
- **THEN** 腳本執行格式化檢查（`black --check`）、lint（`ruff check`）、型別檢查（`mypy`）、所有測試（包括 SQL 函數測試）
- **AND** SQL 函數測試在測試階段正確執行
- **AND** 任何步驟失敗時返回非零退出碼並停止後續步驟

### Requirement: 完整 CI 流程包含整合和資料庫測試
系統 SHALL 確保完整 CI 流程（`test.sh ci` 命令）執行所有必要的測試類型，包括整合測試和資料庫函數測試。

#### Scenario: CI 流程執行順序
- **WHEN** 開發者執行 `docker compose run test ci`
- **THEN** 腳本執行以下步驟（按順序）：
  1. 格式化檢查（`black --check`）
  2. Lint 檢查（`ruff check`）
  3. 型別檢查（`mypy`）
  4. Pre-commit 檢查
  5. 單元測試
  6. 合約測試
  7. 經濟測試
  8. 資料庫測試（SQL 函數測試）
  9. 議會測試
  10. 效能測試
  11. 整合測試

#### Scenario: 資料庫測試在 CI 中執行
- **WHEN** 完整 CI 流程執行
- **THEN** 資料庫函數測試（`tests/db/*.sql`）使用 `pg_prove` 被包含在流程中
- **AND** SQL 測試正確連接到 PostgreSQL 服務
- **AND** 測試結果被正確報告
- **AND** SQL 測試失敗時 CI 流程停止並返回非零退出碼
