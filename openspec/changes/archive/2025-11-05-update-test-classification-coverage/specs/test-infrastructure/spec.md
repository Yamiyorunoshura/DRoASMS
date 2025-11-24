## ADDED Requirements

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
系統 SHALL 提供清晰的測試分類定義，確保測試案例按照 TDD 原則（單元 → 契約 → 整合 → 效能）漸進組織。

#### Scenario: 單元測試定義
- **WHEN** 測試針對單一模組或函式的邏輯行為
- **THEN** 測試 SHOULD 歸類為單元測試
- **AND** 測試 SHOULD 使用模擬（mock）或隔離（transaction rollback）確保無副作用
- **AND** 測試涵蓋：Services、Gateways、指令模組邏輯、基礎設施模組

#### Scenario: 契約測試定義
- **WHEN** 測試驗證輸入輸出格式、JSON Schema、日誌契約、API 形狀
- **THEN** 測試 SHOULD 歸類為契約測試
- **AND** 測試涵蓋：Slash 指令結構、日誌事件形狀、敏感資訊遮罩、面板互動契約

#### Scenario: 整合測試定義
- **WHEN** 測試涵蓋多個模組協作、外部依賴（DB、Discord API）或容器編排
- **THEN** 測試 SHOULD 歸類為整合測試
- **AND** 測試涵蓋：Docker Compose 就緒流程、多租戶隔離、錯誤恢復流程

#### Scenario: 效能測試定義
- **WHEN** 測試驗證系統效能指標（延遲、吞吐量）或 SLO 驗收
- **THEN** 測試 SHOULD 歸類為效能測試
- **AND** 測試涵蓋：轉帳確認延遲（P95 < 5s）、Council 投票延遲（P95 < 3s）、State Council 操作延遲（P95 < 2s）

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
系統 SHALL 補足效能測試，確保治理流程的效能符合 SLO。

#### Scenario: Council 投票流程效能測試
- **WHEN** 測試執行 `tests/performance/test_council_voting.py`
- **THEN** 測試驗證 Council 提案投票流程的 P95 延遲 < 3s
- **AND** 測試涵蓋提案建立、投票、達標執行的完整流程

#### Scenario: State Council 操作效能測試
- **WHEN** 測試執行 `tests/performance/test_state_council_operations.py`
- **THEN** 測試驗證 State Council 部門操作的 P95 延遲 < 2s
- **AND** 測試涵蓋福利發放、稅收、貨幣增發、跨部門轉帳的完整流程

### Requirement: pytest 配置更新
系統 SHALL 更新 `pyproject.toml` 中的 pytest 配置，新增測試分類 marker 定義。

#### Scenario: marker 定義
- **WHEN** 開發者查看 `pyproject.toml` 中的 `[tool.pytest.ini_options]`
- **THEN** 配置 MUST 包含以下 marker 定義：
  - `unit: Unit tests for individual modules and functions`
  - `integration: Integration tests requiring Docker/Discord`
  - `contract: Contract tests for input/output formats and schemas`
  - `performance: Performance and load tests for NFR validation`

#### Scenario: marker 執行篩選
- **WHEN** 開發者執行 `pytest -m unit`
- **THEN** pytest 僅執行標記為 `@pytest.mark.unit` 的測試
- **AND** 未標記的測試不會執行

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
