# test-infrastructure Specification

## Purpose
TBD - created by archiving change introduce-test-container. Update Purpose after archive.
## Requirements
### Requirement: 測試容器映像檔
系統 SHALL 提供一個獨立的測試容器映像檔，基於 Python 3.13，包含所有測試依賴（dev dependencies），使用 `uv` 管理依賴。測試容器 SHALL 包含執行 SQL 函數測試和雙重類型檢查所需的工具。

#### Scenario: 測試容器包含所有測試工具
- **WHEN** 測試容器啟動
- **THEN** 容器內可用 `pytest`、`mypy`、`pyright`、`ruff`、`black` 等工具
- **AND** 容器內可用 `pg_prove` 工具執行 SQL 測試
- **AND** 容器內可用 PostgreSQL client 工具（`psql`）連接到資料庫
- **AND** 所有工具版本與 `pyproject.toml` 中定義的版本一致
- **AND** MyPy 和 Pyright 均配置為使用 pyproject.toml 中的嚴格模式設定

### Requirement: Compose 測試服務
系統 SHALL 在 `compose.yaml` 中提供 `test` 服務，使用測試容器映像檔，能夠連接到 PostgreSQL 服務進行資料庫測試。測試服務 SHALL 預設啟用整合測試執行，確保所有整合測試所需的環境變數都已配置。測試專用的環境變數（如 `RUN_DISCORD_INTEGRATION_TESTS`）SHALL 在 `compose.yaml` 中設定，而非在 `.env` 檔案中，以保持生產環境配置檔案的乾淨。測試服務 SHALL 提供 Docker CLI 存取（透過掛載 Docker socket 或 Docker-in-Docker），使整合測試能夠執行 `docker compose` 命令。測試服務 SHALL 配置所有整合測試所需的環境變數（包括 `RUN_DOCKER_TESTS` 和 `TEST_MIGRATION_DB_URL`），確保測試不會因為缺少配置而被跳過。

#### Scenario: 測試服務成功啟動
- **WHEN** 開發者執行 `docker compose up test`
- **THEN** 測試服務等待 PostgreSQL 服務健康檢查通過後啟動
- **AND** 測試服務可以連接到 PostgreSQL 服務
- **AND** 測試服務使用專案根目錄作為工作目錄
- **AND** 測試服務可以存取 Docker socket，能夠執行 `docker compose` 命令

#### Scenario: 測試服務環境變數支援
- **WHEN** 開發者透過主機環境變數傳遞 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`（例如：`docker compose run -e TEST_DISCORD_TOKEN=... test integration`）
- **THEN** 測試服務可以讀取這些環境變數
- **AND** 整合測試可以使用這些環境變數執行
- **AND** 測試專用的環境變數不會污染 `.env` 檔案（`.env` 僅用於生產環境配置）

#### Scenario: 整合測試預設啟用
- **WHEN** 開發者執行 `docker compose run test integration`
- **THEN** 測試服務環境變數 `RUN_DISCORD_INTEGRATION_TESTS` 在 `compose.yaml` 中預設設為 `1`（不在 `.env` 中設定）
- **AND** 所有標記為 `@pytest.mark.integration` 的測試不會因為缺少 `RUN_DISCORD_INTEGRATION_TESTS` 而被跳過
- **AND** 開發者可以透過主機環境變數傳遞 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`（例如：`docker compose run -e TEST_DISCORD_TOKEN=token test integration`）
- **AND** 如果 `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN` 未設定，測試會明確跳過並顯示清楚的訊息，而非因為缺少 `RUN_DISCORD_INTEGRATION_TESTS` 而跳過

#### Scenario: 整合測試環境變數完整性
- **WHEN** 開發者在 Docker 測試容器中執行整合測試
- **THEN** 所有整合測試所需的環境變數都已配置：
  - `RUN_DISCORD_INTEGRATION_TESTS=1`（在 `compose.yaml` 測試服務環境中預設啟用，不在 `.env` 中）
  - `RUN_DOCKER_TESTS=1`（在 `compose.yaml` 測試服務環境中預設啟用，用於需要 Docker Compose 操作的測試）
  - `TEST_MIGRATION_DB_URL`（在 `compose.yaml` 測試服務環境中設定，可從主機環境變數覆寫，用於遷移失敗測試）
  - `DATABASE_URL`（從 `.env` 或預設值）
  - `TEST_DISCORD_TOKEN` 或 `DISCORD_TOKEN`（從主機環境變數傳遞，不在 `.env` 中）
- **AND** 測試不會因為缺少必要的環境變數配置而被跳過（除非明確需要外部資源如 Discord Token）
- **AND** `.env` 檔案保持乾淨，不包含測試專用的配置

#### Scenario: Docker CLI 存取可用性
- **WHEN** 整合測試需要執行 `docker compose` 命令（如 `test_compose_dependencies.py`、`test_compose_ready.py`、`test_compose_restart_update.py`、`test_db_not_ready_retry.py`、`test_external_db_override.py`）
- **THEN** 測試容器內可以執行 `docker` 和 `docker compose` 命令
- **AND** Docker socket 已掛載到測試容器（`/var/run/docker.sock`）或 Docker-in-Docker 已配置
- **AND** 測試不會因為 Docker/Compose 不可用而被跳過
- **AND** 測試可以成功啟動和管理獨立的 Docker Compose 專案（使用 `docker_compose_project` fixture）

#### Scenario: 整合測試不因配置缺失而跳過
- **WHEN** 開發者執行 `make test-integration` 且已提供必要的資源（如 Discord token）
- **THEN** 所有整合測試都不會因為缺少 Docker/Compose 存取或缺少環境變數而被跳過
- **AND** 只有明確需要外部資源（如 Discord token）的測試才會在缺少資源時跳過
- **AND** 測試輸出清楚顯示跳過原因（例如："未提供 TEST_DISCORD_TOKEN/DISCORD_TOKEN"）

### Requirement: 測試執行腳本
系統 SHALL 提供統一的測試執行腳本 `docker/bin/test.sh`，支援執行不同類型的測試與 CI 檢查，包括 SQL 函數測試、MyPy 和 Pyright 嚴格模式類型檢查。

#### Scenario: 執行完整 CI 流程
- **WHEN** 開發者執行 `docker compose run test ci` 或 `make ci`
- **THEN** 腳本執行格式化檢查（`black --check`）、lint（`ruff check`）、型別檢查（`mypy` 和 `pyright`，均使用嚴格模式）、所有測試（包括 SQL 函數測試和整合測試）
- **AND** SQL 函數測試在測試階段正確執行
- **AND** 整合測試作為標準 CI 流程的一部分被執行
- **AND** 任何步驟失敗時返回非零退出碼並停止後續步驟

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
系統 SHALL 確保測試執行不影響應用容器的運行，測試資料與應用資料分離。整合測試 SHALL 使用獨立的資源（Docker Compose 專案名稱、資料庫連線）確保測試間隔離，避免資源衝突導致測試卡住。

#### Scenario: 測試資料隔離
- **WHEN** 測試執行完成
- **THEN** 測試建立的資料庫資料不影響應用資料庫
- **AND** 測試使用交易回滾或獨立資料庫確保隔離
- **AND** 測試使用的資料庫連線在測試結束時正確釋放

#### Scenario: 測試容器與應用容器分離
- **WHEN** 測試容器執行測試
- **THEN** 測試容器不影響應用容器的運行
- **AND** 測試容器可以獨立重建而不影響應用容器
- **AND** 整合測試使用獨立的 Docker Compose 專案名稱，避免容器和網路衝突

#### Scenario: 整合測試資源隔離
- **WHEN** 多個整合測試同時執行
- **THEN** 每個測試使用獨立的 Docker Compose 專案名稱（如 `droasms-test-{test_id}`）
- **AND** 每個測試的 Docker Compose 容器和網路在測試結束時正確清理
- **AND** 測試間不會因為資源衝突而卡住或失敗

#### Scenario: 非同步資源清理
- **WHEN** 整合測試使用非同步協調器（如 TransferEventPoolCoordinator）
- **THEN** 協調器在測試結束時（無論成功或失敗）正確停止
- **AND** 所有非同步任務在測試結束前完成或取消
- **AND** 測試不會因為協調器未停止而卡住

#### Scenario: 資料庫連線池管理
- **WHEN** 整合測試使用資料庫連線池
- **THEN** 測試結束時連線池正確關閉，所有連線正確釋放
- **AND** 測試使用的交易在測試結束時正確回滾
- **AND** 連線池不會因為連線未釋放而耗盡

### Requirement: Makefile 快捷命令
系統 SHALL 在 `Makefile` 中統一提供測試容器的快捷命令，移除本地測試命令，讓開發者通過 Docker 容器執行所有測試。

#### Scenario: 本地測試命令被移除
- **WHEN** 開發者查看 `Makefile` 的可用命令列表
- **THEN** 本地測試命令已被移除（`test-unit`, `test-contract`, `test-integration`, `test-performance`, `test-db`, `test-council`, `test-economy`, 基於 marker 的命令）
- **AND** 只有 Docker 測試命令保留

#### Scenario: 基礎測試命令
- **WHEN** 開發者執行 `make test` 或 `make test-container`
- **THEN** 系統執行 `docker compose run --rm test`，運行所有測試類型（不含整合測試）
- **AND** 測試結果輸出到標準輸出

#### Scenario: 執行特定類型的測試
- **WHEN** 開發者執行 `make test-container-unit`, `make test-container-contract`, `make test-container-db`, `make test-container-economy`, `make test-container-council`, `make test-container-performance`
- **THEN** 系統執行對應的 Docker 測試命令
- **AND** 命令說明清楚描述每個命令的功能

#### Scenario: 執行整合測試
- **WHEN** 開發者執行 `make test-container-integration`
- **THEN** 系統執行 `docker compose run --rm test integration`
- **AND** 整合測試被正確執行

#### Scenario: 完整 CI 流程包含所有測試
- **WHEN** 開發者執行 `make test-container-ci` 或 `make ci` 或 `make ci-full`
- **THEN** 系統執行 `docker compose run --rm test ci`
- **AND** CI 流程包含：格式化檢查、lint、型別檢查、pre-commit 檢查、所有測試類型（包括整合測試和資料庫測試）
- **AND** 任何步驟失敗時返回非零退出碼並停止後續步驟

#### Scenario: Makefile 幫助命令清晰列出所有Docker測試命令
- **WHEN** 開發者執行 `make help`
- **THEN** 輸出清楚列出所有可用的 Docker 測試命令
- **AND** 每個命令都有簡明的說明

### Requirement: 測試分類標記系統
系統 SHALL 為所有測試案例提供明確的分類標記（pytest marker），將測試分為單元（unit）、整合（integration）、契約（contract）、效能（performance）四大類。

#### Scenario: 單元測試標記
- **WHEN** 測試檔案位於 `tests/unit/` 目錄
- **THEN** 測試函式或類別 MUST 標記 `@pytest.mark.unit`
- **AND** 測試執行時可透過 `pytest -m unit` 篩選執行

#### Scenario: 整合測試標記
- **WHEN** 測試檔案位於 `tests/integration/` 目錄
- **THEN** 測試函式或類別 MUST 標記 `@pytest.mark.integration`
- **AND** 測試執行時可透過 `pytest -m integration` 篩選執行

#### Scenario: 契約測試標記
- **WHEN** 測試檔案位於 `tests/contracts/` 目錄
- **THEN** 測試函式或類別 MUST 標記 `@pytest.mark.contract`
- **AND** 測試執行時可透過 `pytest -m contract` 篩選執行

#### Scenario: 效能測試標記
- **WHEN** 測試檔案位於 `tests/performance/` 目錄
- **THEN** 測試函式或類別 MUST 標記 `@pytest.mark.performance`
- **AND** 測試執行時可透過 `pytest -m performance` 篩選執行

### Requirement: 測試分類定義與範疇
系統 SHALL 提供清晰的測試分類定義，確保測試案例按照 TDD 原則（單元 → 契約 → 整合 → 效能）漸進組織。新增的性能基準測試 SHALL 歸類為效能測試。

#### Scenario: 效能測試定義擴展
- **WHEN** 測試驗證系統性能指標或mypc編譯效果
- **THEN** 測試 SHOULD 歸類為效能測試
- **AND** 測試涵蓋：治理模組性能基準、mypc編譯前後對比、回歸性能驗證
- **AND** 效能測試 SHALL 生成可重複的基準和對比報告

### Requirement: 測試執行腳本支援分類篩選
系統 SHALL 更新測試執行腳本 `docker/bin/test.sh`，支援依 marker 執行特定分類的測試。

#### Scenario: 依 marker 執行單元測試
- **WHEN** 開發者執行 `docker compose run test --unit`
- **THEN** 腳本執行 `pytest -m unit`，僅執行標記為 `@pytest.mark.unit` 的測試
- **AND** 測試結果輸出到標準輸出

#### Scenario: 依 marker 執行整合測試
- **WHEN** 開發者執行 `docker compose run test --integration`
- **THEN** 腳本執行 `pytest -m integration`，僅執行標記為 `@pytest.mark.integration` 的測試
- **AND** 腳本自動設置 `RUN_DISCORD_INTEGRATION_TESTS=1` 環境變數

#### Scenario: 依 marker 執行契約測試
- **WHEN** 開發者執行 `docker compose run test --contract`
- **THEN** 腳本執行 `pytest -m contract`，僅執行標記為 `@pytest.mark.contract` 的測試

#### Scenario: 依 marker 執行效能測試
- **WHEN** 開發者執行 `docker compose run test --performance`
- **THEN** 腳本執行 `pytest -m performance`，僅執行標記為 `@pytest.mark.performance` 的測試

### Requirement: 測試覆蓋率提升 - 單元測試
系統 SHALL 補足以下單元測試，提高核心模組的測試覆蓋率。

#### Scenario: 指令模組單元測試
- **WHEN** 測試執行 `tests/unit/test_adjust_command.py`、`tests/unit/test_balance_command.py`、`tests/unit/test_transfer_command.py`
- **THEN** 測試涵蓋 `/adjust`、`/balance`、`/history`、`/transfer` 指令的參數驗證、權限檢查、服務層呼叫
- **AND** 測試涵蓋身分組提及（Council 與 State Council 帳戶）的處理邏輯

#### Scenario: 基礎設施模組單元測試
- **WHEN** 測試執行 `tests/unit/test_retry.py`、`tests/unit/test_logging_config.py`
- **THEN** 測試涵蓋 `src/infra/retry.py` 的指數退避與抖動邏輯
- **AND** 測試涵蓋 `src/infra/logging/config.py` 的日誌設定與敏感資訊遮罩

### Requirement: 測試覆蓋率提升 - 契約測試
系統 SHALL 補強契約測試，確保 UI 互動與 API 形狀的穩定性。

#### Scenario: Council 面板契約測試
- **WHEN** 測試執行 `tests/contracts/test_council_panel_contract.py`
- **THEN** 測試涵蓋 Council 面板所有互動（提案、投票、執行、匯出）的契約
- **AND** 測試涵蓋面板錯誤處理契約（權限不足、參數錯誤）

#### Scenario: State Council 面板契約測試
- **WHEN** 測試執行 `tests/contracts/test_state_council_panel_contract.py`
- **THEN** 測試涵蓋 State Council 面板所有部門操作（福利、稅收、身分、增發、轉帳）的契約
- **AND** 測試涵蓋面板錯誤處理契約（權限不足、參數錯誤）

### Requirement: 測試覆蓋率提升 - 整合測試
系統 SHALL 補足整合測試，確保多租戶場景與錯誤恢復流程的穩定性。

#### Scenario: 多租戶隔離測試
- **WHEN** 測試執行 `tests/integration/test_multi_guild.py`
- **THEN** 測試涵蓋多個 guild 同時操作的場景（轉帳、調整、Council 提案）
- **AND** 測試驗證不同 guild 的資料隔離（餘額、交易歷史、Council 狀態）

#### Scenario: 錯誤恢復流程測試
- **WHEN** 測試執行現有整合測試（`test_db_not_ready_retry.py`、`test_migration_failure_exit_code.py`）
- **THEN** 測試涵蓋 DB 連線失敗重試、遷移失敗的錯誤處理
- **AND** 測試驗證錯誤事件（`db.unavailable`、`bot.migrate.error`）與退出碼

### Requirement: 測試覆蓋率提升 - 效能測試
系統 SHALL 補足效能測試，確保治理流程的效能符合 SLO。效能測試 SHALL 包含mypc編譯前後的對比驗證。

#### Scenario: Council 投票流程效能測試
- **WHEN** 測試執行 `tests/performance/test_council_voting.py`
- **THEN** 測試驗證 Council 提案投票流程的 P95 延遲 < 3s
- **AND** 測試涵蓋提案建立、投票、達標執行的完整流程
- **AND** mypc編譯版本 SHALL 顯著優於未編譯版本的性能指標

#### Scenario: State Council 操作效能測試
- **WHEN** 測試執行 `tests/performance/test_state_council_operations.py`
- **THEN** 測試驗證 State Council 部門操作的 P95 延遲 < 2s
- **AND** 測試涵蓋福利發放、稅收、貨幣增發、跨部門轉帳的完整流程
- **AND** mypc編譯 SHALL 明顯提升批量操作的性能

#### Scenario: Supreme Assembly 議案處理效能測試
- **WHEN** 測試執行 Supreme Assembly 議案處理流程
- **THEN** 測試驗證議案建立、審議、投票、執行的效能基準
- **AND** 測試 SHALL 包含複雜議案場景的性能驗證
- **AND** mypc編譯 SHALL 在複雜邏輯處理上展現性能優勢

### Requirement: Pytest Configuration Management
The test infrastructure SHALL provide pytest configuration with all required markers and settings properly defined.

#### Scenario: Test Collection Without Markers Warnings
- **WHEN** pytest is executed without specific test selection
- **THEN** all tests shall be collected successfully without "Unknown pytest.mark.contract" warnings
- **AND** the contract marker shall be properly defined in pyproject.toml

#### Scenario: Test Suite Execution
- **WHEN** pytest runs the full test suite
- **THEN** all 29 test files shall be collected without import errors
- **AND** test execution shall complete with 98%+ coverage maintained

### Requirement: 測試文件更新
系統 SHALL 更新測試相關文件，說明測試分類標準與執行方式。

#### Scenario: README 測試章節更新
- **WHEN** 開發者查看 `README.md` 的「測試與品質維護」章節
- **THEN** 文件 MUST 包含測試分類標準說明（單元、整合、契約、效能）
- **AND** 文件 MUST 包含依 marker 執行測試的範例（`pytest -m unit`、`pytest -m integration`）
- **AND** 文件 MUST 包含測試執行腳本的使用方式（`docker compose run test --unit`）

#### Scenario: 測試 docstring 要求
- **WHEN** 開發者新增或修改測試案例
- **THEN** 測試函式 SHOULD 包含清晰的 docstring，說明測試意圖、涵蓋場景、預期行為
- **AND** docstring SHOULD 遵循專案慣例（中文或英文，格式一致）

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

### Requirement: 統一 Docker 測試執行環境
系統 SHALL 確保所有測試都通過 Docker 容器執行，提供一致的開發和 CI 環境。

#### Scenario: 本地開發環境中使用 Docker 測試
- **WHEN** 開發者在本地環境執行測試
- **THEN** 開發者使用 `make test-container-*` 或 `make test` 命令通過 Docker 執行測試
- **AND** 測試環境與 CI 環境完全相同

#### Scenario: 命令一致性
- **WHEN** 開發者執行本地 `make test-container-*` 或 CI 中的 `docker compose run test`
- **THEN** 兩者使用相同的容器映像檔和測試腳本
- **AND** 測試結果應該一致

### Requirement: 測試超時保護
系統 SHALL 為所有整合測試提供超時保護機制，防止測試無限等待導致測試套件卡住。

#### Scenario: Compose 測試超時保護
- **WHEN** 整合測試涉及 Docker Compose 操作（啟動、日誌追蹤）
- **THEN** 測試 MUST 使用 `@pytest.mark.timeout` 裝飾器設定超時（Compose 測試 180-300s）
- **AND** 超時時測試正確清理資源（容器、連線、協調器）
- **AND** 超時錯誤訊息清楚說明測試卡住的原因

#### Scenario: 資料庫測試超時保護
- **WHEN** 整合測試涉及資料庫操作
- **THEN** 測試 MUST 使用 `@pytest.mark.timeout` 裝飾器設定超時（資料庫測試 60s）
- **AND** 超時時資料庫連線正確釋放
- **AND** 超時時交易正確回滾

#### Scenario: 非同步操作超時保護
- **WHEN** 整合測試涉及非同步操作（協調器啟動/停止、事件等待）
- **THEN** 測試 MUST 設定合理的超時值
- **AND** 超時時非同步操作正確取消或停止
- **AND** 超時時資源正確清理

### Requirement: 測試資源清理保證
系統 SHALL 確保所有測試資源（Docker Compose 容器、資料庫連線、非同步協調器、子進程）在測試結束時正確清理，無論測試成功或失敗。

#### Scenario: Fixture 清理保證
- **WHEN** 測試使用 `db_pool` 或 `db_connection` fixture
- **THEN** fixture 的 `finally` 區塊 MUST 確保連線池關閉和連線釋放
- **AND** fixture 的 `finally` 區塊 MUST 確保交易回滾
- **AND** 即使測試失敗或異常，清理邏輯也會執行

#### Scenario: Docker Compose 清理保證
- **WHEN** 測試使用 Docker Compose 啟動容器
- **THEN** 測試的 `finally` 區塊 MUST 執行 `docker compose down` 清理容器
- **AND** 清理操作必須使用測試專用的專案名稱
- **AND** 即使測試失敗或超時，清理邏輯也會執行

#### Scenario: 非同步協調器清理保證
- **WHEN** 測試啟動非同步協調器（如 TransferEventPoolCoordinator）
- **THEN** 測試的 `finally` 區塊 MUST 調用協調器的 `stop()` 方法
- **AND** 協調器停止操作必須設定超時，防止無限等待
- **AND** 即使測試失敗或異常，清理邏輯也會執行

### Requirement: Cython 匯入解析
測試基礎設施 SHALL 確保所有 Cython 擴充套件能正確地被測試模組匯入。

#### Scenario: Suspect 類別匯入
- **WHEN** `src/bot/services/justice_service.py` 從 Cython 擴充套件匯入
- **THEN** Suspect 相關類別應從正確模組成功匯入
- **AND** 測試收集期間不應引發 ImportError

#### Scenario: Cython 擴充套件編譯
- **WHEN** pytest 發現需要 Cython 擴充套件的測試
- **THEN** 所有必需的 Cython 模組應被編譯且可匯入
- **AND** 測試應能存取所有 Cython 定義的類別和函式

### Requirement: 測試診斷工具
系統 SHALL 提供診斷工具，協助識別和解決測試卡住問題。

#### Scenario: 資源監控輸出
- **WHEN** 整合測試失敗或超時
- **THEN** 測試輸出包含資源使用狀況（活躍的 Docker 容器、資料庫連線數、非同步任務數）
- **AND** 測試輸出包含清理操作的執行狀態
- **AND** 測試輸出包含可能的資源衝突提示

#### Scenario: 測試日誌收集
- **WHEN** 整合測試失敗或超時
- **THEN** 測試收集相關的 Docker Compose 日誌
- **AND** 測試收集資料庫連線池狀態
- **AND** 測試收集非同步協調器狀態

### Requirement: SQL 函式測試完整性
系統 SHALL 為所有 SQL 函式（economy 與 governance schema）提供完整的 pgTAP 測試，確保資料庫層業務邏輯的正確性與穩定性。

#### Scenario: Economy Schema 函式測試覆蓋
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** 所有 economy schema 的 SQL 函式都有對應的 pgTAP 測試檔案（`tests/db/test_fn_*.sql`）
- **AND** 測試涵蓋以下函式：
  - `fn_adjust_balance`、`fn_transfer_currency`、`fn_get_balance`、`fn_get_history`、`fn_has_more_history`
  - `fn_record_throttle`、`fn_notify_adjustment`
  - `fn_create_pending_transfer`、`fn_get_pending_transfer`、`fn_list_pending_transfers`、`fn_update_pending_transfer_status`
  - `fn_check_transfer_balance`、`fn_check_transfer_cooldown`、`fn_check_transfer_daily_limit`、`fn_check_and_approve_transfer`
  - `trigger_pending_transfer_check`
- **AND** 每個測試檔案驗證函式簽名、成功路徑、邊界條件與錯誤處理

#### Scenario: Governance Schema - Council 函式測試覆蓋
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** 所有 governance schema 的 Council 相關 SQL 函式都有對應的 pgTAP 測試檔案
- **AND** 測試涵蓋以下函式：
  - 設定：`fn_upsert_council_config`、`fn_get_council_config`
  - 提案：`fn_create_proposal`、`fn_get_proposal`、`fn_get_snapshot_members`、`fn_count_active_proposals`、`fn_attempt_cancel_proposal`
  - 投票：`fn_upsert_vote`、`fn_fetch_tally`、`fn_list_votes_detail`、`fn_list_unvoted_members`
  - 狀態：`fn_mark_status`、`fn_list_due_proposals`、`fn_list_reminder_candidates`、`fn_list_active_proposals`、`fn_mark_reminded`
  - 匯出：`fn_export_interval`
- **AND** 測試驗證提案建立限制（最多 5 個進行中提案）、投票邏輯、狀態轉換、執行轉帳等關鍵業務邏輯

#### Scenario: Governance Schema - State Council 函式測試覆蓋
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** 所有 governance schema 的 State Council 相關 SQL 函式都有對應的 pgTAP 測試檔案
- **AND** 測試涵蓋以下函式：
  - 設定：`fn_upsert_state_council_config`、`fn_get_state_council_config`、`fn_upsert_department_config`、`fn_list_department_configs`、`fn_get_department_config`
  - 帳戶：`fn_upsert_government_account`、`fn_list_government_accounts`、`fn_update_government_account_balance`
  - 福利：`fn_create_welfare_disbursement`、`fn_list_welfare_disbursements`
  - 稅收：`fn_create_tax_record`、`fn_list_tax_records`
  - 身分：`fn_create_identity_record`、`fn_list_identity_records`
  - 貨幣：`fn_create_currency_issuance`、`fn_list_currency_issuances`、`fn_sum_monthly_issuance`
  - 轉帳：`fn_create_interdepartment_transfer`、`fn_list_interdepartment_transfers`
  - 查詢：`fn_list_all_department_configs_with_welfare`、`fn_list_all_department_configs_for_issuance`
- **AND** 測試驗證各部門操作的正確性、餘額更新、跨部門轉帳等關鍵業務邏輯

#### Scenario: SQL 測試品質標準
- **WHEN** 開發者新增或更新 SQL 函式測試
- **THEN** 測試檔案 MUST 使用 pgTAP 框架（`SELECT plan(...)`、`SELECT ok(...)`、`SELECT throws_like(...)` 等）
- **AND** 測試 MUST 驗證函式簽名（`SELECT has_function(...)`）
- **AND** 測試 MUST 涵蓋成功路徑、邊界條件（NULL、空值、極值）、錯誤處理（例外、約束違反）
- **AND** 測試 MUST 使用交易隔離（`BEGIN; ... ROLLBACK;`）確保不影響其他測試
- **AND** 測試 MUST 使用唯一的測試資料（snowflake ID）避免衝突

#### Scenario: SQL 測試執行與報告
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** `pg_prove` 正確執行所有 `tests/db/*.sql` 檔案
- **AND** 測試結果輸出到標準輸出，包含通過/失敗統計
- **AND** 測試失敗時返回非零退出碼
- **AND** 如果 `tests/db/` 目錄為空或沒有 SQL 檔案，腳本優雅處理（不失敗）

### Requirement: 治理模組性能基準測試
系統 SHALL 為治理模組提供專門的性能基準測試，用於驗證mypyc編譯的性能提升效果。性能測試 SHALL 覆蓋常見操作場景，包括議案處理、投票統計、部門操作等。

#### Scenario: 議案處理性能基準測試
- **WHEN** 測試執行議案創建、投票、執行的完整流程
- **THEN** 測量每個步驟的執行時間並記錄基準
- **AND** 編譯後版本 SHALL 比 Python 版本快至少5倍
- **AND** 測試 SHALL 生成性能報告供對比分析

#### Scenario: 部門操作性能基準測試
- **WHEN** 測試執行State Council部門操作（福利發放、稅收徵收等）
- **THEN** 測量批量操作的執行時間
- **AND** 編譯後版本 SHALL 顯著優於未編譯版本
- **AND** 測試 SHALL 驗證內存使用效率

#### Scenario: 數據查詢性能基準測試
- **WHEN** 測試執行複雜的治理數據查詢（投票統計、議案列表等）
- **THEN** 測量查詢響應時間和數據處理效率
- **AND** 編譯後版本 SHALL 展現明顯性能優勢
- **AND** 測試 SHALL 驗證結果正確性不受編譯影響

### Requirement: Mypc編譯性能驗證測試
系統 SHALL 提供自動化的mypc編譯性能驗證測試，確保編譯後的代碼在保持功能正確性的同時達到預期性能提升。

#### Scenario: 編譯前後功能一致性驗證
- **WHEN** 運行相同的測試套件於未編譯和編譯版本
- **THEN** 兩者版本的所有測試結果 SHALL 完全一致
- **AND** API 輸入輸出行為 SHALL 保持完全兼容
- **AND** 錯誤處理和異常情況 SHALL 表現一致

#### Scenario: 性能提升量化測試
- **WHEN** 使用性能基準測試對比編譯前後性能
- **THEN** 系統 SHALL 生成詳細的性能對比報告
- **AND** 關鍵操作 SHALL 達到至少5倍性能提升
- **AND** 整體系統響應時間 SHALL 顯著改善

### Requirement: 治理模組測試覆蓋率監控
系統 SHALL 為治理模組提供專門的測試覆蓋率監控，確保關鍵邏輯得到充分測試，特別是當前覆蓋率較低的模組。

#### Scenario: Supreme Assembly模組覆蓋率提升
- **WHEN** 測試執行 `tests/unit/test_supreme_assembly_command.py`
- **THEN** Supreme Assembly 模組的覆蓋率 SHALL 從0%提升到至少80%
- **AND** 所有公開API和關鍵邏輯路徑 SHALL 被測試覆蓋
- **AND** 錯誤處理和邊界條件 SHALL 包含在測試中

#### Scenario: Council模組覆蓋率提升
- **WHEN** 增強Council相關測試
- **THEN** Council 模組的覆蓋率 SHALL 從13%提升到至少70%
- **AND** 議會管理功能 SHALL 得到全面測試
- **AND** 面板互動和配置管理 SHALL 包含在測試範圍內

#### Scenario: State Council模組覆蓋率提升
- **WHEN** 增強State Council相關測試
- **THEN** State Council 模組的覆蓋率 SHALL 從23%提升到至少60%
- **AND** 部門操作和權限管理 SHALL 得到充分測試
- **AND** 政府帳戶和交易邏輯 SHALL 包含在測試中

#### Scenario: 整體覆蓋率目標達成驗證
- **WHEN** 運行完整測試套件
- **THEN** 整體測試覆蓋率 SHALL 達到至少50%
- **AND** 關鍵治理模組 SHALL 超過設定目標
- **AND** 新增測試 SHALL 提供實際價值而非形式主義

### Requirement: Cython Import Resolution
The test infrastructure SHALL ensure all Cython extensions can be imported correctly by test modules.

#### Scenario: Suspect Class Import
- **WHEN** src/bot/services/justice_service.py imports from Cython extensions
- **THEN** the Suspect-related classes shall be successfully imported from the correct module
- **AND** no ImportError shall be raised during test collection

#### Scenario: Cython Extension Compilation
- **WHEN** pytest discovers tests requiring Cython extensions
- **THEN** all required Cython modules shall be compiled and importable
- **AND** tests shall have access to all Cython-defined classes and functions

### Requirement: Dependency Compatibility Validation
The test infrastructure SHALL validate that all dependency updates remain compatible with existing test patterns.

#### Scenario: Ruff Compatibility Testing
- **WHEN** ruff is updated to version 0.7.x
- **THEN** existing linting rules shall continue to pass
- **AND** any new rules shall be addressed without breaking existing code patterns

#### Scenario: Pytest Ecosystem Updates
- **WHEN** pytest and related packages are updated
- **THEN** all existing test markers, fixtures, and assertions shall continue to function
- **AND** test discovery and execution patterns shall remain unchanged
