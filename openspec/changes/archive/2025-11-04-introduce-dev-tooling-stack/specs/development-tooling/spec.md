## ADDED Requirements

### Requirement: Pydantic 設定管理
專案必須（MUST）使用 Pydantic 進行設定載入與驗證，提供型別安全與自動驗證環境變數。

#### Scenario: BotSettings 使用 Pydantic 模型
- **WHEN** 應用程式啟動時載入 `BotSettings`
- **THEN** 必須使用 Pydantic `BaseSettings` 模型驗證 `DISCORD_TOKEN`（必填）與 `DISCORD_GUILD_ALLOWLIST`（選填，逗號分隔整數）
- **AND** 驗證失敗時必須（MUST）提供清晰的錯誤訊息

#### Scenario: PoolConfig 使用 Pydantic 模型
- **WHEN** 資料庫連線池初始化時載入 `PoolConfig`
- **THEN** 必須使用 Pydantic 模型驗證 `DATABASE_URL`、`DB_POOL_MIN_SIZE`、`DB_POOL_MAX_SIZE`、`DB_POOL_TIMEOUT_SECONDS`
- **AND** 必須驗證 `DB_POOL_MAX_SIZE >= DB_POOL_MIN_SIZE`
- **AND** 驗證失敗時必須（MUST）提供清晰的錯誤訊息

### Requirement: Faker 測試資料生成
測試必須（MUST）使用 Faker 自動生成假資料，減少手寫測試資料。

#### Scenario: 測試使用 Faker 生成假資料
- **WHEN** 測試需要 guild_id、user_id、金額等假資料
- **THEN** 必須使用 Faker fixture 生成，而非手寫固定值
- **AND** Faker 必須支援中文與英文 locale

#### Scenario: Faker fixture 可用性
- **WHEN** 測試需要假資料
- **THEN** `tests/conftest.py` 必須提供 `faker` fixture，設定中文與英文 locale

### Requirement: 測試覆蓋率報告
專案必須（MUST）提供測試覆蓋率報告，用於評估測試品質。

#### Scenario: 執行測試時產生覆蓋率報告
- **WHEN** 執行 `pytest --cov` 指令
- **THEN** 必須產生 HTML 與終端覆蓋率報告
- **AND** 覆蓋率報告必須排除測試檔案、遷移檔案與設定檔案

#### Scenario: CI 整合覆蓋率報告
- **WHEN** CI 工作流程執行測試
- **THEN** 必須產生並上傳覆蓋率報告（可選）

### Requirement: 並行測試執行
測試必須（MUST）支援並行執行，以縮短測試時間。

#### Scenario: 使用 pytest-xdist 並行執行測試
- **WHEN** 執行 `pytest -n auto` 指令
- **THEN** 測試必須可並行執行，不影響測試隔離
- **AND** 資料庫連線池與交易必須正確隔離，避免狀態共享

### Requirement: Pre-commit 自動檢查
專案必須（MUST）使用 pre-commit hooks 確保提交前程式碼品質。

#### Scenario: 提交前自動執行檢查
- **WHEN** 開發者執行 `git commit`
- **THEN** pre-commit hooks 必須自動執行 black、ruff、mypy 檢查
- **AND** 檢查失敗時必須（MUST）阻止提交

#### Scenario: Pre-commit 設定檔存在
- **WHEN** 檢查專案根目錄
- **THEN** 必須存在 `.pre-commit-config.yaml` 檔案，定義 black、ruff、mypy 檢查

### Requirement: Tenacity 重試邏輯
專案必須（MUST）在實作重試邏輯時使用 Tenacity 簡化實作，減少手寫重試程式碼。

#### Scenario: 轉帳重試使用 Tenacity
- **WHEN** 實作轉帳檢查失敗的重試邏輯
- **THEN** 必須使用 Tenacity `@retry` 裝飾器搭配指數退避與抖動策略，而非手寫重試程式碼

### Requirement: Hypothesis 屬性測試
專案必須（MUST）在測試複雜邏輯時使用 Hypothesis 進行屬性測試，自動生成邊界案例。

#### Scenario: 複雜邏輯使用 Hypothesis 測試
- **WHEN** 測試複雜邏輯（如轉帳驗證、餘額計算）
- **THEN** 必須使用 Hypothesis 自動生成邊界案例與異常輸入，而非手寫固定測試案例
