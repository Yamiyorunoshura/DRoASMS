# development-tooling Specification

## Purpose
TBD - created by archiving change introduce-dev-tooling-stack. Update Purpose after archive.
## Requirements
### Requirement: Pylance 型別檢查支援
專案必須（MUST）提供 Pylance/Pyright 配置，支援 VS Code 編輯器內的即時型別檢查。

#### Scenario: Pylance 配置檔案存在
- **WHEN** 檢查專案根目錄
- **THEN** 必須存在 `pyrightconfig.json` 配置檔案
- **AND** 配置必須與 mypy strict mode 設定保持一致

#### Scenario: Pylance 提供即時型別檢查
- **WHEN** 開發者在 VS Code 中編輯 Python 檔案
- **THEN** Pylance 必須提供即時的型別錯誤提示和智能補全
- **AND** 型別檢查結果必須與 mypy 檢查結果一致

### Requirement: Mypyc 編譯支援
專案必須（MUST）配置 mypyc 支援，為未來效能優化提供編譯能力。專案必須（MUST）為經濟模塊啟用 mypyc 編譯，將 Python 代碼編譯為 C 擴展以提升執行效率。

#### Scenario: Mypyc 依賴已安裝
- **WHEN** 檢查 `pyproject.toml` 的開發依賴
- **THEN** 必須包含 `mypyc>=1.11.0` 在 `[dependency-groups.dev]` 中

#### Scenario: Mypyc 配置存在
- **WHEN** 檢查 `pyproject.toml`
- **THEN** 必須存在 `[tool.mypyc]` 配置區塊
- **AND** 配置必須為未來編譯優化做好準備

#### Scenario: 經濟模塊啟用 mypyc 編譯
- **WHEN** 執行構建流程
- **THEN** 經濟模塊的服務層和 gateway 層必須使用 mypyc 編譯為 C 擴展
- **AND** 編譯後的模塊必須保持與未編譯模塊的完全兼容性
- **AND** 編譯過程不得改變模塊的功能行為

#### Scenario: 編譯錯誤已修復
- **WHEN** mypyc 編譯經濟模塊時發現型別錯誤或不相容問題
- **THEN** 必須修復所有編譯錯誤
- **AND** 修復後的代碼必須通過所有現有測試
- **AND** 修復不得改變模塊的 API 或行為

#### Scenario: 編譯後的模塊功能完整
- **WHEN** 使用編譯後的經濟模塊執行操作
- **THEN** 所有功能必須與編譯前完全一致
- **AND** 所有單元測試和整合測試必須通過
- **AND** 型別檢查（mypy）必須通過

#### Scenario: 性能提升可測量
- **WHEN** 對編譯後的經濟模塊進行性能基準測試
- **THEN** 必須獲得可測量的性能提升（目標 10-30%）
- **AND** 性能測試結果必須記錄在文檔中

### Requirement: 型別檢查無錯誤
專案必須（MUST）通過 mypy strict mode 檢查，無任何編譯錯誤。

#### Scenario: Mypy 檢查通過
- **WHEN** 執行 `mypy src/` 指令
- **THEN** 必須無任何型別錯誤或警告
- **AND** 所有 `type: ignore` 註解必須有效且必要（不得有未使用的 `type: ignore` 註解）
- **AND** 所有變數賦值必須符合其類型註解，不得有類型不匹配錯誤

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
- **WHEN** 開發者執行 `git commit` 或在 CI 環境中執行 `pre-commit run --all-files`
- **THEN** pre-commit hooks 必須自動執行 black、ruff、mypy 檢查
- **AND** 檢查失敗時必須（MUST）阻止提交或 CI 流程
- **AND** Git 環境必須正確配置以支援 pre-commit hooks 執行
- **AND** 在 CI 環境中，如果沒有 git 倉庫，必須適當處理（跳過檢查或正確初始化 git 環境）

### Requirement: Tenacity 重試邏輯
專案必須（MUST）在實作重試邏輯時使用 Tenacity 簡化實作，減少手寫重試程式碼。

#### Scenario: 轉帳重試使用 Tenacity
- **WHEN** 實作轉帳檢查失敗的重試邏輯
- **THEN** 必須使用 Tenacity `@retry` 裝飾器搭配指數退避與抖動策略，而非手寫重試程式碼

### Requirement: Development Dependency Management
The development tooling SHALL maintain current and secure development dependencies compatible with Python 3.13.

#### Scenario: Security Vulnerability Resolution
- **WHEN** safety scanning is performed on dependencies
- **THEN** all reported security vulnerabilities shall be resolved
- **AND** dependency versions shall be aligned with current stable releases

#### Scenario: Code Quality Tool Consistency
- **WHEN** development tools are executed (ruff, mypy, black)
- **THEN** all tools shall run without version conflicts
- **AND** output formatting and behavior shall remain consistent

### Requirement: Linting and Type Checking Configuration
The development tooling SHALL provide linting and type checking with current rule sets and strict configuration.

#### Scenario: MyPy Strict Mode Validation
- **WHEN** mypy runs in strict mode
- **THEN** type checking shall pass without errors
- **AND** unused type ignore comments shall be eliminated

#### Scenario: Ruff Linting Execution
- **WHEN** ruff processes the codebase
- **THEN** configured rules shall pass without errors
- **AND** auto-fixable violations shall be addressed automatically

### Requirement: Hypothesis 屬性測試
專案必須（MUST）在測試複雜邏輯時使用 Hypothesis 進行屬性測試，自動生成邊界案例。

#### Scenario: 複雜邏輯使用 Hypothesis 測試
- **WHEN** 測試複雜邏輯（如轉帳驗證、餘額計算）
- **THEN** 必須使用 Hypothesis 自動生成邊界案例與異常輸入，而非手寫固定測試案例

### Requirement: CI 測試配置正確性
CI 管道必須（MUST）正確配置所有測試套件，確保測試可以正確執行。

#### Scenario: Contract Tests 正確執行
- **WHEN** CI 管道執行 Contract Tests
- **THEN** 所有必需的 schema 文件必須可以被找到（路徑解析正確）
- **AND** Contract Tests 必須能夠載入並驗證所有 schema 文件

#### Scenario: Council Tests 正確執行
- **WHEN** CI 管道執行 Council Tests
- **THEN** 必須使用正確的測試目錄路徑（`tests/integration/council/` 或相關單元測試）
- **AND** 測試必須能夠被發現並執行

#### Scenario: Database Function Tests 正確執行
- **WHEN** CI 管道執行 Database Function Tests
- **THEN** 必須使用 `pg_prove` 工具執行 SQL 測試文件（而非 `pytest`）
- **AND** CI 環境必須安裝 `pg_prove` 和 `pgtap` 工具
- **AND** 測試必須能夠連接到資料庫並執行 SQL 測試

#### Scenario: Integration Tests 正確執行
- **WHEN** CI 管道執行 Integration Tests
- **THEN** Docker-in-Docker 配置必須正確，測試容器可以連接到 Docker 服務
- **AND** Docker 網絡配置必須正確，避免連接錯誤

### Requirement: Major Version Update Compatibility
The development tooling SHALL handle major version updates of core development dependencies.

#### Scenario: Ruff Major Version Transition
- **WHEN** ruff is updated from 0.5.7 to 0.7.x
- **THEN** existing linting configurations shall remain functional
- **AND** any breaking changes in rules shall be identified and addressed

#### Scenario: Pytest Ecosystem Updates
- **WHEN** pytest packages are updated to latest stable versions
- **THEN** all existing test configurations and fixtures shall continue to work
- **AND** plugin compatibility shall be maintained

### Requirement: Development Environment Consistency
The development tooling SHALL ensure consistent behavior across development, CI, and test environments.

#### Scenario: Cross-Environment Tool Validation
- **WHEN** development tools are executed in different environments
- **THEN** tool behavior and output shall be consistent
- **AND** environment-specific configurations shall be properly isolated

#### Scenario: Dependency Conflict Prevention
- **WHEN** new dependencies are added or updated
- **THEN** version conflicts shall be automatically detected and resolved
- **AND** compatibility with Python 3.13 shall be maintained
