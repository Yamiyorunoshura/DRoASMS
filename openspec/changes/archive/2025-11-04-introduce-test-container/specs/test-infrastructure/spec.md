## ADDED Requirements

### Requirement: 測試容器映像檔
系統 SHALL 提供一個獨立的測試容器映像檔，基於 Python 3.13，包含所有測試依賴（dev dependencies），使用 `uv` 管理依賴。

#### Scenario: 測試容器成功建置
- **WHEN** 開發者執行 `docker build -f docker/test.Dockerfile -t droasms-test .`
- **THEN** 測試容器映像檔成功建置，包含 Python 3.13、`uv`、所有測試依賴（pytest, pytest-cov, pytest-xdist, mypy, ruff, black 等）
- **AND** 測試容器使用非 root 用戶執行

#### Scenario: 測試容器包含所有測試工具
- **WHEN** 測試容器啟動
- **THEN** 容器內可用 `pytest`、`mypy`、`ruff`、`black` 等工具
- **AND** 所有工具版本與 `pyproject.toml` 中定義的版本一致

### Requirement: Compose 測試服務
系統 SHALL 在 `compose.yaml` 中提供 `test` 服務，使用測試容器映像檔，能夠連接到 PostgreSQL 服務進行資料庫測試。

#### Scenario: 測試服務成功啟動
- **WHEN** 開發者執行 `docker compose up test`
- **THEN** 測試服務等待 PostgreSQL 服務健康檢查通過後啟動
- **AND** 測試服務可以連接到 PostgreSQL 服務
- **AND** 測試服務使用專案根目錄作為工作目錄

#### Scenario: 測試服務環境變數支援
- **WHEN** 開發者透過 `.env` 或環境變數設定 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`
- **THEN** 測試服務可以讀取這些環境變數
- **AND** 整合測試可以使用這些環境變數執行

### Requirement: 測試執行腳本
系統 SHALL 提供統一的測試執行腳本 `docker/bin/test.sh`，支援執行不同類型的測試與 CI 檢查。

#### Scenario: 執行所有測試
- **WHEN** 開發者執行 `docker compose run test`
- **THEN** 腳本執行所有測試類型（unit, contract, integration, performance, db）
- **AND** 測試結果輸出到標準輸出
- **AND** 測試失敗時返回非零退出碼

#### Scenario: 執行單元測試
- **WHEN** 開發者執行 `docker compose run test unit`
- **THEN** 腳本僅執行單元測試（`tests/unit/`）
- **AND** 測試結果輸出到標準輸出

#### Scenario: 執行整合測試
- **WHEN** 開發者執行 `docker compose run test integration`
- **THEN** 腳本執行整合測試（`tests/integration/`）
- **AND** 腳本自動設置 `RUN_DISCORD_INTEGRATION_TESTS=1` 環境變數
- **AND** 測試可以連接到 Compose 中的 PostgreSQL 服務

#### Scenario: 執行完整 CI 流程
- **WHEN** 開發者執行 `docker compose run test ci`
- **THEN** 腳本執行格式化檢查（`black --check`）、lint（`ruff check`）、型別檢查（`mypy`）、所有測試
- **AND** 任何步驟失敗時返回非零退出碼並停止後續步驟

#### Scenario: 執行特定測試類型
- **WHEN** 開發者執行 `docker compose run test contract` 或 `docker compose run test performance`
- **THEN** 腳本執行對應的測試類型
- **AND** 測試結果輸出到標準輸出

### Requirement: 測試結果輸出
系統 SHALL 將測試結果（包括覆蓋率報告）輸出到標準輸出，並支援將覆蓋率報告持久化到主機。

#### Scenario: 測試結果輸出
- **WHEN** 測試執行完成
- **THEN** 測試結果（通過/失敗統計）輸出到標準輸出
- **AND** 覆蓋率報告輸出到標準輸出（如果啟用）

#### Scenario: 覆蓋率報告持久化
- **WHEN** 開發者掛載卷到 `/app/htmlcov`
- **THEN** HTML 覆蓋率報告寫入到掛載的卷
- **AND** 開發者可以在主機上查看 HTML 報告

### Requirement: 測試環境隔離
系統 SHALL 確保測試執行不影響應用容器的運行，測試資料與應用資料分離。

#### Scenario: 測試資料隔離
- **WHEN** 測試執行完成
- **THEN** 測試建立的資料庫資料不影響應用資料庫
- **AND** 測試使用交易回滾或獨立資料庫確保隔離

#### Scenario: 測試容器與應用容器分離
- **WHEN** 測試容器執行測試
- **THEN** 測試容器不影響應用容器的運行
- **AND** 測試容器可以獨立重建而不影響應用容器

### Requirement: Makefile 快捷命令
系統 SHALL 在 `Makefile` 中提供測試容器的快捷命令，讓開發者能夠快速執行不同類型的測試。

#### Scenario: 執行所有測試容器測試
- **WHEN** 開發者執行 `make test-container`
- **THEN** Makefile 執行 `docker compose run --rm test`，運行所有測試類型
- **AND** 測試結果輸出到標準輸出

#### Scenario: 執行單元測試容器
- **WHEN** 開發者執行 `make test-container-unit`
- **THEN** Makefile 執行 `docker compose run --rm test unit`，運行單元測試
- **AND** 命令遵循 Makefile 的命名慣例（與現有 `test-unit` 命令對應）

#### Scenario: 執行完整 CI 流程容器
- **WHEN** 開發者執行 `make test-container-ci`
- **THEN** Makefile 執行 `docker compose run --rm test ci`，運行格式化檢查、lint、型別檢查、所有測試
- **AND** 任何步驟失敗時停止並返回非零退出碼

#### Scenario: Makefile 命令說明
- **WHEN** 開發者執行 `make help`
- **THEN** Makefile 顯示所有測試容器相關命令的說明
- **AND** 命令說明清楚描述每個命令的功能
