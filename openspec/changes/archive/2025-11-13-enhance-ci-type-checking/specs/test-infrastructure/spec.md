## MODIFIED Requirements

### Requirement: 測試執行腳本
系統 SHALL 提供統一的測試執行腳本 `docker/bin/test.sh`，支援執行不同類型的測試與 CI 檢查，包括 SQL 函數測試、MyPy 和 Pyright 嚴格模式類型檢查。

#### Scenario: 執行完整 CI 流程
- **WHEN** 開發者執行 `docker compose run test ci` 或 `make ci`
- **THEN** 腳本執行格式化檢查（`black --check`）、lint（`ruff check`）、型別檢查（`mypy` 和 `pyright`，均使用嚴格模式）、所有測試（包括 SQL 函數測試和整合測試）
- **AND** SQL 函數測試在測試階段正確執行
- **AND** 整合測試作為標準 CI 流程的一部分被執行
- **AND** 任何步驟失敗時返回非零退出碼並停止後續步驟

### Requirement: 測試容器映像檔
系統 SHALL 提供一個獨立的測試容器映像檔，基於 Python 3.13，包含所有測試依賴（dev dependencies），使用 `uv` 管理依賴。測試容器 SHALL 包含執行 SQL 函數測試和雙重類型檢查所需的工具。

#### Scenario: 測試容器包含所有測試工具
- **WHEN** 測試容器啟動
- **THEN** 容器內可用 `pytest`、`mypy`、`pyright`、`ruff`、`black` 等工具
- **AND** 容器內可用 `pg_prove` 工具執行 SQL 測試
- **AND** 容器內可用 PostgreSQL client 工具（`psql`）連接到資料庫
- **AND** 所有工具版本與 `pyproject.toml` 中定義的版本一致
- **AND** MyPy 和 Pyright 均配置為使用 pyproject.toml 中的嚴格模式設定

### Requirement: 完整 CI 流程包含整合和資料庫測試
系統 SHALL 確保完整 CI 流程（`test.sh ci` 命令和 `make ci` 命令）執行所有必要的測試類型，包括整合測試和資料庫函數測試。

#### Scenario: CI 流程執行順序
- **WHEN** 開發者執行 `docker compose run test ci` 或 `make ci`
- **THEN** 腳本執行以下步驟（按順序）：
  1. 格式化檢查（`black --check`）
  2. Lint 檢查（`ruff check`）
  3. 型別檢查（`mypy src/`）
  4. 型別檢查（`pyright src/`）
  5. Pre-commit 檢查
  6. 單元測試
  7. 合約測試
  8. 經濟測試
  9. 資料庫測試（SQL 函數測試）**MUST** 被執行
  10. 議會測試
  11. 效能測試
  12. 整合測試
- **AND** 資料庫測試使用 `pg_prove` 執行所有 `tests/db/*.sql` 檔案
- **AND** 資料庫測試失敗時 CI 流程停止並返回非零退出碼
- **AND** 整合測試作為標準流程的一部分被執行，而非可選步驟
