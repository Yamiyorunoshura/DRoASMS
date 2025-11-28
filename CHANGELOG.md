# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [3.3.1] - 2025-11-28

### Changed

- **Makefile 改進**：
  - `start-dev` 新增 `-d` 旗標以背景執行開發環境
  - `start-prod` 簡化指令，移除不必要的 `--build --force-recreate` 旗標
  - 新增 `update` 目標用於完整重建和更新專案

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v3.3.0...v3.3.1)

## [3.3.0] - 2025-11-28

### Added

- **公司管理系統**：完整的公司帳戶管理功能
  - 新增 `/company` 指令群組，支援公司建立、查詢、存取款等操作
  - 新增 `CompanyService` 服務層處理公司業務邏輯
  - 新增 `CompanyGateway` 資料庫閘道層
  - 新增 `CompanySelectView` UI 元件用於公司選擇
  - 新增資料庫函數 `fn_companies.sql` 處理公司相關 SQL 操作
- **資料庫遷移**：
  - `049_add_companies.py`：新增公司資料表結構
  - `050_company_functions.py`：新增公司相關資料庫函數
  - `051_fix_company_account_overflow.py`：修正公司帳戶溢位問題
  - `052_allow_council_targets.py`：擴展議會轉帳目標支援
- **轉帳 UI 增強**：
  - 新增 `test_council_transfer_proposal_ui.py`：議會轉帳提案 UI 測試
  - 新增 `test_personal_panel_transfer_ui.py`：個人面板轉帳 UI 測試
  - 新增 `test_state_council_transfer_ui.py`：國務院轉帳 UI 測試
  - 新增 `test_supreme_assembly_transfer_ui.py`：最高人民會議轉帳 UI 測試
  - 新增 `test_supreme_assembly_transfer_resolver.py`：轉帳解析器測試
  - 新增 `test_transfer_ui_cross_panel.py`：跨面板轉帳整合測試
- **Cython 擴展**：擴展 `state_council_models.py` 支援新資料模型

### Changed

- **議會服務重構**：
  - 重構 `council_service.py`，整合 Result 模式並移除獨立的 `council_service_result.py`
  - 更新 `council_errors.py` 擴展錯誤類型定義
- **國務院面板增強**：大幅擴展 `state_council.py` 支援更多操作流程
- **個人面板分頁器改進**：更新 `personal_panel_paginator.py` 支援轉帳 UI 流程
- **依賴注入更新**：更新 `bootstrap.py` 和 `result_container.py` 註冊新服務
- **遙測監聽器**：擴展 `listener.py` 支援新事件追蹤

### Removed

- **服務結果檔案合併**：移除 `council_service_result.py`，功能已整合至 `council_service.py`

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v3.2.0...v3.3.0)

## [3.2.0] - 2025-11-26

### Added

- **國務院面板使用指引改進**：重構 help embed 生成，使用 Discord embed fields 分區排版取代純文字
  - 總覽頁指引新增：功能總覽、權限說明、注意事項、快速開始四大區塊
  - 內政部指引新增：功能列表、操作步驟、注意事項、常見問題區塊
  - 財政部指引新增：功能列表、操作步驟、注意事項區塊
  - 國土安全部指引新增：功能列表、注意事項區塊
  - 中央銀行指引新增：功能列表、注意事項、風險警告區塊
  - 法務部指引新增：功能列表、操作步驟、注意事項、常見問題、權限說明區塊
  - 通用指引提供未知部門的基礎指引 fallback
- **Help Embed 單元測試**：新增 `TestHelpEmbedGeneration` 測試類別驗證所有指引 embed 結構

### Changed

- **Help Embed 樣式統一**：所有使用指引 embed 統一使用藍色主題（`discord.Color.blue()`）取代 blurple

### Fixed

- **型別註解修正**：移除 `_PatchedConnection` 類別上的 `# type: ignore[misc]` 註解

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v3.1.2...v3.2.0)

## [3.1.2] - 2025-11-26

### Added

- **Pyright Pre-commit Hook**：
  - 在 `.pre-commit-config.yaml` 新增 pyright 型別檢查 hook
  - 使用 `uv run pyright` 執行檢查，確保與專案環境一致
  - 檢查範圍與 mypy 一致（`src/` 目錄，排除 migrations）
  - 所有程式碼提交前必須同時通過 mypy 和 pyright 型別檢查

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v3.1.1...v3.1.2)

## [3.1.1] - 2025-11-26

### Fixed

- **Gateway 錯誤處理改進**：
  - 移除 `@async_returns_result` 裝飾器，改用顯式 try/except 區塊
  - `WelfareApplicationGateway.create_application` 和 `LicenseApplicationGateway.create_application` 增加異常捕獲
  - 確保所有資料庫例外都被正確包裝為 `Result[T, DatabaseError]` 類型

### Changed

- **測試程式碼格式化**：調整 `test_state_council_service.py` 中的程式碼格式

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v3.1.0...v3.1.1)

## [3.1.0] - 2025-11-26

### Added

- **統一持久化面板基礎架構**：
  - 新增 `PersistentPanelView` 基類，提供所有面板的持久化回應機制
  - 新增 `PersistentButton` 和 `PersistentSelect` 持久化互動元件
  - 新增 `generate_custom_id()` 統一 custom_id 生成機制
  - 預設 10 分鐘面板超時，統一超時提示訊息
  - 支援機器人重啟後仍能正常處理互動
- **政府申請服務**：
  - 新增 `ApplicationService` 處理福利和營業執照申請工作流程
  - 新增 `WelfareApplicationGateway` 和 `LicenseApplicationGateway`
  - 新增資料庫遷移 `048_add_government_applications.py`
  - 完整的單元測試和整合測試覆蓋

### Changed

- **面板持久化升級**：
  - 更新 Council、State Council、Personal、Supreme Assembly 面板繼承 `PersistentPanelView`
  - 所有互動元件在超時前可被重複回應
  - 統一註冊 persistent view 到 bot 啟動流程
- **UI 元件模組結構**：
  - 更新 `src/bot/ui/__init__.py` 導出持久化元件

### Removed

- **OpenSpec 清理**：
  - 移除已歸檔的 openspec 變更和規格檔案，精簡專案結構
  - 移除 `GEMINI.md` 和冗餘的 `openspec/AGENTS.md`

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v3.0.0...v3.1.0)

## [3.0.0] - 2025-11-25

### Added

- **擴展個人面板政府部門轉帳範圍**：
  - 新增常任理事會作為轉帳目標（帳戶 ID: `9_000_000_000_000_000 + guild_id`）
  - 新增最高人民會議作為轉帳目標（帳戶 ID: `9_200_000_000_000_000 + guild_id`）
  - 新增國務院主帳戶作為轉帳目標（帳戶 ID: `9_100_000_000_000_000 + guild_id`）
  - 保留現有國務院下屬部門轉帳功能
- **更新 departments.json**：
  - 新增 `supreme_assembly`（最高人民會議）項目，level 為 `legislative`

### Changed

- **個人面板轉帳選擇器重構**：
  - 將部門選擇器升級為政府機構選擇器，支援按層級分組顯示
  - 選項分組：最高決策機構 > 立法機構 > 行政機構 > 各部門

### Removed

- **BREAKING**: 移除 `/balance` 指令（功能已整合至 `/personal_panel` 首頁分頁）
- **BREAKING**: 移除 `/history` 指令（功能已整合至 `/personal_panel` 財產分頁）

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v2.2.1...v3.0.0)

## [2.2.1] - 2025-11-25

### Fixed

- **Type annotations**: Improved Pyright compatibility in `compile_modules.py`
  - Added explicit casts for `tomllib` and `cythonize` imports to suppress "partially unknown" warnings
  - Renamed unused variable `artifact` to `_artifact` for lint compliance

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v2.2.0...v2.2.1)

## [2.2.0] - 2025-11-25

### Added

- **Administrative Management Panel**: New dedicated panel for State Council department configuration
  - New `AdministrativeManagementView` class with ephemeral embed message
  - Displays current department leader role configuration status for all 5 departments
  - Department selector dropdown for choosing configuration target
  - Role selector dropdown for setting department leader role
  - Real-time refresh via `department_config_updated` event subscription
  - Permission-gated: Only State Council leaders can access
- **Unit Test Coverage**: Comprehensive test suite `test_administrative_management_panel.py`
  - Tests for view initialization and component validation
  - Tests for department selection and role configuration
  - Tests for real-time event handling and permission boundaries

### Changed

- **State Council Panel Refactor**: Removed inline department leader configuration UI from overview page
  - Removed `config_target_department` attribute from `StateCouncilPanelView`
  - Removed department selector and role selector from `_add_overview_actions`
  - Added "行政管理" button triggering the new dedicated panel
- **State Council Events**: Extended `StateCouncilEvent` with `department_config_updated` event kind

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v2.1.1...v2.2.0)

## [2.1.1] - 2025-11-25

### Fixed

- **Error mapping correction**: `VotingNotAllowedError` now raises `PermissionDeniedError` instead of `ValueError` in council service
- **Data integrity**: Added defensive copy of metadata in `TransferResult` to prevent external mutation
- **Test stability**: Added `mock_pool` fixture in council service benchmarks to avoid database dependency

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v2.1.0...v2.1.1)

## [2.1.0] - 2025-11-25

### Added

- **Interior Business Licensing System**: Complete business license management for State Council Interior Department
  - New database migrations: `046_add_business_licenses.py` and `047_business_license_functions.py`
  - New SQL functions: `fn_business_licenses.sql` for license application, approval, revocation, and queries
  - New `BusinessLicenseGateway` class with full CRUD operations returning `Result<T,E>`
  - Extended `StateCouncilService` with business license management methods
  - Added permission checks for Interior Department leadership and State Council leaders
- **UI Panel Updates**: Interior Department tab with business license management features
  - License application modal (target user, license type, validity period)
  - Authorized users paginated list view
  - License revocation functionality
- **Test Coverage**: Comprehensive tests for business licensing
  - SQL function unit tests (`test_fn_business_license.sql`)
  - Gateway layer tests
  - Service layer tests
  - Panel contract tests

### Changed

- Updated `state_council.py` commands with business license management subcommands
- Extended `state_council_errors.py` with business license error types
- Extended `state_council_service_result.py` with business license result types
- Updated `state_council_models.py` with business license data models
- Updated specs: `state-council-governance` and `state-council-panel`

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v2.0.1...v2.1.0)

## [2.0.1] - 2025-11-25

### Fixed

- Improved test coverage for slash commands with comprehensive test fixtures and extended test suites
- Added contract tests for Supreme Assembly command interactions
- Enhanced test infrastructure with Discord mocks and permission fixtures
- Added coverage checking script for automated test coverage validation

### Added

- Comprehensive test fixtures for command base, Discord mocks, and result helpers
- Extended test coverage for council, economy, help, and state council commands
- Integration tests for cross-command interactions
- Schema contracts for Docker environment configuration and log events

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v2.0.0...v2.0.1)

## [2.0.0] - 2025-11-24

### Added

- Council Service Result pattern implementation with unified error handling
- Comprehensive migration guide for transitioning from exception-based to Result pattern
- Performance benchmarks for council service operations
- New `CouncilServiceResult` class for type-safe error handling
- Enhanced test coverage for Result pattern operations

### Changed

- **BREAKING**: Refactored council service architecture to use Result pattern internally
- Updated all council-related commands to use unified service implementation
- Modified service dependencies to support both exception and Result patterns
- Improved error handling consistency across council operations
- Enhanced performance testing with detailed benchmarking

### Deprecated

- Direct exception handling in council services (use Result pattern for new code)

### Fixed

- Performance bottlenecks in error handling paths (Result pattern ~2x faster than exceptions)
- Type safety issues in council service error handling
- Memory efficiency improvements in service initialization

### Security

- No security changes in this release

### Migration Notes

This release introduces a major architectural change while maintaining backward compatibility. Existing code using `CouncilService()` will continue to work, but new development should use `CouncilServiceResult()` for better type safety and performance. See `docs/COUNCIL_SERVICE_MIGRATION_GUIDE.md` for detailed migration instructions.

[Compare changes](https://github.com/Yamiyorunoshura/DRoASMS/compare/v1.0.1...v2.0.0)

## [1.0.1] - 2025-11-23

### 修復

- **司法服務記錄更正**：修復 `justice_service.py` 中的記錄錯誤
  - 修正 `existing.id` 為 `existing.suspect_id`
  - 修正 `suspect.id` 為 `suspect.suspect_id`
  - 確保記錄的 ID 欄位與資料模型一致

## [1.0.0] - 2025-11-22

### ⚠️ 重大變更

- **資料模型結構調整**：
  - 將 `Suspect` 類別的 `id` 欄位更名為 `suspect_id`，統一識別碼命名規範
  - 更新所有相關的資料庫查詢、服務邏輯和 UI 元件以使用新欄位名稱
  - 此變更需要資料庫遷移，請確保在部署前執行完整的遷移流程

### 修改

- **資料庫結構優化**：
  - 統一 suspects 資料表的主鍵欄位名稱從 `id` 改為 `suspect_id`
  - 更新所有相關的 SQL 查詢語句和索引定義
  - 改進資料模型的可讀性和一致性
- **配置驗證增強**：
  - 優化 DATABASE_URL 的空白字元處理邏輯，移除所有空白字元後再進行驗證
  - 提升配置參數的驗證準確性

## [0.23.2] - 2025-11-21

### 修改

- **Docker 配置優化**：
  - 分離生產與開發環境配置，使用 profile 管理不同環境
  - 生產環境使用 `target: production` 優化建置流程
  - 新增 `bot-dev` 服務支援開發環境即時代碼更新
  - 改進測試容器，新增 `postgresql-client` 套件
- **測試系統改進**：
  - 使用 marker 系統替代硬編碼測試路徑，提升測試執行彈性
  - 新增測試環境專用變數：`RUN_DISCORD_INTEGRATION_TESTS`、`RUN_DOCKER_TESTS`、`TEST_MIGRATION_DB_URL`
  - 測試容器新增 Docker socket 掛載支援整合測試
- **代碼重構**：將 `Suspect` 類從 `council_governance_models.py` 移動到 `state_council_models.pyx`，改善模組職責分離
- **開發工具改進**：更新 Makefile 中的說明文字，澄清開發與生產環境啟動方式

### 修復

- **Docker 最佳化**：清理生產映像檔中的不必要建置檔案，減少映像檔大小
- **測試執行**：修正測試腳本使用 marker 執行特定類型測試

## [0.23.1] - 2025-11-21

### 修改

- **依賴更新**：更新多個開發依賴版本以提升穩定性
  - `pytest-asyncio` 從 0.23.0 更新到 0.24.0
  - `pytest-xdist` 從 3.6.0 更新到 3.6.1
  - `pytest-timeout` 從 2.3.0 更新到 2.3.1
  - `faker` 從 30.0.0 更新到 33.0.0
  - `mypy` 從 1.11.0 更新到 1.13.0
  - `ruff` 從 0.6.0 更新到 0.7.3
  - `black` 從 24.8.0 更新到 24.10.0
  - `hypothesis` 從 6.0.0 更新到 6.111.0
  - `rich` 從 14.0.0 更新到 13.9.0
  - `setuptools` 從 68.0.0 更新到 75.0.0
  - `wheel` 從 0.43.0 更新到 0.44.0
  - `psutil` 從 6.0.0 更新到 6.1.0
- **測試配置改進**：
  - 新增 `contract` 測試 marker 到 pyproject.toml
  - 更新測試腳本使用 marker 執行測試而非硬編碼路徑
  - 改進測試容器配置，新增整合測試和 Docker 測試環境變數
- **代碼重構**：將 `Suspect` 類從 `council_governance_models.py` 移動到 `state_council_models.pyx`，改善模組職責分離
- **Docker 配置增強**：
  - 新增測試環境專用變數：`RUN_DISCORD_INTEGRATION_TESTS`、`RUN_DOCKER_TESTS`、`TEST_MIGRATION_DB_URL`
  - 新增 Docker socket 掛載支援整合測試
  - 更新測試容器 Dockerfile，新增 `postgresql-client` 套件
- **代碼清理**：
  - 改進 `src/infra/retry.py` 中的類型註解
  - 更新 `.gitignore` 和 `.dockerignore` 排除臨時檔案
  - 清理文件結尾的換行符問題

### 修復

- **類型安全**：改進重試機制中的類型處理，移除不必要的 `type: ignore[misc]` 註釋
- **測試執行**：修復測試腳本中的路徑問題，改用統一的 marker 系統
- **依賴一致性**：更新 `uv.lock` 確保依賴版本一致性

## [0.23.0] - 2025-11-21

### 新增

- **權限邊界案例測試**：新增 `tests/unit/test_permission_boundary_cases.py`，涵蓋特殊場景權限檢查
- **權限邊界案例測試工具**：新增 `tests/unit/test_homeland_security_permission.py`，提供國土安全部門權限驗證
- **資料庫錯誤處理工具**：新增 `src/infra/db_errors.py`，提供統一的資料庫錯誤類型與處理
- **權限邊界案例測試框架**：整合測試文件進行系統權限組件健全性檢查
- **資料庫邊界案例測試**：新增 `tests/unit/test_permission_boundary_cases.py` 和 `tests/unit/test_homeland_security_permission.py`

### 修復

- 權限檢查邏輯增強：在多個權限檢查点加入更嚴格的邊界案例處理
- 資料庫操作穩定性改進：統一錯誤處理方式，提升穩定性
- 資源釋放機制優化：在各種邊緣情況下確保資源正確釋放

### 修改

- 權限檢查邏輯重構：精簡權限檢查邏輯，提高效能與可讀性
- 錯誤處理標準化：統一錯誤類型與處理方式
- 邊界檢查擴充：適應特殊場景的邊界檢查
- 安全機制加強：提高資源敏感度，提升系統安全強度

## [0.22.0] - 2025-11-19

### 新增

- **Result<T,E> 模式系統**：完整的 Rust 風格錯誤處理機制
  - 新增 `src/common/result.py` 和 `src/infra/result.py`：核心 Result 類型實現
  - 新增 `src/infra/result_compat.py`：向後相容性適配層
  - 新增 `src/infra/db_errors.py`：資料庫錯誤類型定義
  - 新增 `src/bot/utils/error_templates.py`：錯誤模板工具
- **服務結果層**：為主要服務新增 Result 類型包裝
  - 新增 `src/bot/services/council_service_result.py`：議會服務結果類型
  - 新增 `src/bot/services/state_council_service_result.py`：州議會服務結果類型
  - 新增 `src/bot/services/permission_service_result.py`：權限服務結果類型
  - 新增 `src/bot/services/council_errors.py`：議會錯誤定義
  - 新增 `src/bot/services/state_council_errors.py`：州議會錯誤定義
- **遷移工具**：新增 Result 模式遷移支援
  - 新增 `scripts/migrate_to_result.py`：自動遷移腳本
  - 新增 `src/infra/migration_tools.py`：遷移工具集合
  - 新增 `docs/RESULT_MIGRATION_GUIDE.md`：完整遷移指南
- **依賴注入擴展**：新增 `src/infra/di/result_container.py`：Result 類型的容器支援
- **測試覆蓋**：Result 模式的完整測試套件
  - 新增 `tests/test_result.py`：Result 類型單元測試
  - 新增 `tests/integration/test_result_integration.py`：整合測試

### 修改

- **服務層重構**：將異常處理模式遷移到 Result 模式
  - 更新 `src/bot/services/adjustment_service.py`：使用 Result 包裝錯誤處理
  - 更新 `src/bot/services/balance_service.py`：加入 Result 類型支援
  - 更新 `src/bot/services/state_council_reports.py`：整合 Result 模式
  - 更新 `src/bot/services/transfer_service.py`：Result 風格重構
  - 更新 `src/bot/services/transfer_event_pool.py`：錯誤處理優化
- **命令層適配**：更新所有命令以支援新的 Result 模式
  - 更新 `src/bot/commands/adjust.py`：Result 類型適配
  - 更新 `src/bot/commands/balance.py`：錯誤處理重構
  - 更新 `src/bot/commands/council.py`：Result 模式整合
  - 更新 `src/bot/commands/state_council.py`：大型重構支援 Result
  - 更新 `src/bot/commands/transfer.py`：服務層 Result 適配
  - 更新 `src/bot/commands/currency_config.py`：配置服務 Result 支援
  - 更新 `src/bot/commands/supreme_assembly.py`：輕微調整
- **基礎設施更新**：支援 Result 模式的核心設施
  - 更新 `src/infra/retry.py`：重試機制 Result 適配
  - 更新 `src/infra/telemetry/listener.py`：遙測 Result 支援
  - 更新 `src/infra/di/bootstrap.py`：容器初始化 Result 支援
- **資料庫閘道擴展**：錯誤處理 Result 模式遷移
  - 更新 `src/db/gateway/council_governance.py`：加入 Result 類型
  - 更新 `src/db/gateway/economy_adjustments.py`：調整服務 Result 支援
  - 更新 `src/db/gateway/economy_queries.py`：查詢 Result 包裝
  - 更新 `src/db/gateway/economy_transfers.py`：轉移 Result 適配
  - 更新 `src/db/gateway/state_council_governance.py`：州議會 Result 支援
  - 更新 `src/db/gateway/state_council_governance_mypc.py`：MYP Result 適配
- **Cython 模組同步**：更新擴展模組支援新的 Result 模式
  - 更新 `src/cython_ext/state_council_models.py`：Result 類型適配
- **測試更新**：所有單元測試適配新的 Result 模式
  - 更新 `tests/unit/test_adjust_command.py`：適配 Result 模式
  - 更新 `tests/unit/test_balance_service_pagination.py`：測試 Result 支援
  - 更新 `tests/unit/test_council_command.py`：命令層 Result 測試
  - 更新 `tests/unit/test_council_command_fixed.py`：修正測試 Result 適配
  - 更新 `tests/unit/test_result_types.py`：Result 類型測試擴展

### 修復

- **型別檢查**：更新 `pyrightconfig.json` 改善 Result 類型推斷
- **依賴鎖定**：更新 `uv.lock` 確保依賴一致性
- **Git 忽略**：更新 `.gitignore` 排除臨時檔案

### 破壞性變更

- **錯誤處理模式**：從基於異常的錯誤處理遷移到 Rust 風格的 Result<T,E> 模式
- **API 介面**：所有受影響的服務方法現在使用 Result 類型而非拋出異常
- **錯誤處理**：呼叫端需要適應新的 `result.is_ok()` 和 `result.unwrap()` 模式

## [0.21.0] - 2025-11-17

### 新增

- **司法系統模組**：完整的司法部門管理功能
  - 新增 `src/bot/services/justice_service.py`：司法服務核心邏輯
  - 新增 `src/db/gateway/justice_governance.py`：司法治理資料庫閘道
  - 新增資料庫遷移：`042_add_justice_department_suspects.py`（revision: `042_add_justice_department`）和 `043_add_charge_actions_to_identity_records.py`（revision: `043_add_charge_actions`）
- **結果類型系統**：新增 `src/infra/result.py` 提供統一的結果處理機制
- **測試覆蓋**：新增司法系統相關測試檔案
  - `tests/unit/test_justice_service.py`
  - `tests/unit/test_result_types.py`
  - 更新 `tests/unit/test_suspects_management.py`

### 修改

- **州議會命令擴展**：大幅擴展 `src/bot/commands/state_council.py` 支援司法領導權限檢查
- **調整命令優化**：更新 `src/bot/commands/adjust.py` 支援司法部門調整權限
- **部門註冊表更新**：擴展 `src/bot/services/department_registry.py` 支援司法部門
- **轉移池改進**：優化 `src/bot/services/transfer_event_pool.py` 的錯誤處理
- **配置更新**：更新 `src/config/departments.json` 新增司法部門配置
- **Cython 模組同步**：更新 `src/cython_ext/council_governance_models.py` 配合新功能
- **重試機制優化**：改進 `src/infra/retry.py` 的重試邏輯
- **測試更新**：更新 `tests/db/test_fn_create_identity_record.sql` 支援新的身份記錄功能

### 修復

- **依賴鎖定**：更新 `uv.lock` 確保依賴一致性

## [0.20.0] - 2025-11-15

### 修改

- **持續整合改善**：優化 GitHub Actions 工作流程配置
- **編譯系統優化**：改進 Cython 模組編譯流程
- **性能調整**：優化轉移池和經濟調整模組的運行效率
- **重試機制**：改善基礎設施的重試邏輯
- **測試覆蓋**：更新合約測試以適應最新變更

## [0.19.0] - 2025-11-14

### 新增

- **Cython 編譯器系統**：完整的 Cython 擴展模組架構，提升性能優化能力
  - 新增 `src/cython_ext/` 目錄，包含 13 個核心模組的 Cython 實現
  - 經濟模組：`currency_models`、`economy_configuration_models`、`economy_query_models`、`economy_balance_models`、`economy_transfer_models`、`economy_adjustment_models`、`pending_transfer_models`、`transfer_pool_core`
  - 治理模組：`council_governance_models`、`supreme_assembly_models`、`state_council_models`、`government_registry_models`
  - 每個模組都有對應的 `.pyx` 來源檔案和 `.py` 包裝檔案
- **性能基線測試工具**：新增完整的性能監控和基準測試框架
  - `scripts/performance_baseline_test.py`：主要性能基線測試工具，包含編譯時間、執行時間、記憶體使用等多項指標
  - `scripts/compile_time_benchmark.py`：專門測試編譯時間的基準工具
  - `scripts/concurrency_performance_test.py`：並發性能測試工具
  - `scripts/memory_leak_test.py`：記憶體洩漏檢測工具
  - `scripts/cython_compiler.py`：Cython 編譯器輔助工具
- **Cython 運行時測試**：新增 `tests/performance/test_cython_runtime.py` 測試編譯後模組的運行時性能
- **政府註冊表模組**：新增 `src/db/gateway/government_registry.py` 提供統一的政府註冊表管理
- **基線資料**：新增 `docs/baselines/cython_pre_migration.json` 作為遷移前的性能基線參考
- **依賴管理**：新增 `requirements.txt` 簡化依賴管理

### 修改

- **編譯器工作流程**：從 mypc 編譯器完全遷移到 Cython 編譯器
  - 移除 `.github/workflows/mypc-compile.yml`，新增 `.github/workflows/cython-compile.yml`
  - 更新 `Makefile` 支援 Cython 編譯流程
  - 更新 `docker/Dockerfile` 和 `docker/test.Dockerfile` 支援 Cython 模組編譯
- **統一編譯器配置**：大幅擴展 `pyproject.toml` 中的編譯器配置
  - 新增完整的 `[tool.cython-compiler]` 配置區段
  - 支援多階段編譯（week1、week2）
  - 包含性能監控、基線比較、錯誤閾值等進階功能
  - 定義 13 個編譯目標，涵蓋所有核心業務模組
- **文檔更新**：更新 `docs/unified-compiler-guide.md` 反映新的 Cython 編譯器架構
- **服務層優化**：更新多個服務模組以配合 Cython 編譯器
  - 優化 `src/bot/services/` 下的所有核心服務
  - 更新 `src/db/gateway/` 下的資料庫存取層
- **測試擴充**：更新現有測試檔案支援新的編譯器架構

### 修復

- **類型安全改進**：修復多個模組中的類型提示問題，提升代碼品質
- **錯誤處理優化**：改進編譯過程中的錯誤處理和回報機制

### 清理

- **舊檔案歸檔**：將不再需要的舊編譯器相關檔案移至 `scripts/archive/` 目錄
  - `bench_economy.py` → `scripts/archive/bench_economy.py`
  - `migrate_unified_config.py` → `scripts/archive/migrate_unified_config.py`
  - `test_mypyc_benchmarks.py` → `scripts/archive/tests/test_mypyc_benchmarks.py`
- **測試腳本移除**：刪除 `tests/scripts/test_performance_monitor.py`，由新的性能測試框架取代

### 注意

- 此版本為重大架構升級，從 mypc 編譯器完全遷移到 Cython
- 所有變更保持向後相容性，未編譯的 Python 版本仍可正常運行
- 新的性能基線測試工具將為後續的性能優化提供數據支撐
- 編譯過程包含完整的錯誤處理和性能監控機制

## [0.18.1] - 2025-11-13

### 修改

- **類型檢查增強**：新增 Pyright 到 CI 工作流程，提供更嚴格的類型檢查
  - 更新 `.github/workflows/ci.yml` 加入 pyright-check 工作項目
  - 透過 uv 執行 Pyright 類型檢查，確保代碼品質
- **類型注釋優化**：改進多個模組的類型安全性
  - 更新 `help_collector.py`，新增 `JsonValue` 類型定義，改善 JSON 類型處理
  - 優化 `council.py` 中的類型轉換，使用明確的 `cast()` 調用
  - 改進 `retry.py` 和 `pool.py` 中的類型處理
- **Docker 測試改進**：優化測試容器腳本
  - 更新 `docker/bin/test.sh`，改善測試執行流程
  - 微調 `docker/test.Dockerfile` 的構建配置
- **配置文件調整**：小幅更新 Makefile 和其他配置檔案

### 修復

- **類型安全修復**：解決多個模組中的類型提示問題
  - 修復 `src/bot/commands/help_collector.py` 中的 JSON 類型處理
  - 改進 `src/db/pool.py` 和 `src/infra/logging/config.py` 的類型注釋

### 注意

- 此版本為維護性發布，主要專注於代碼品質和類型安全改進
- 所有變更均保持向後兼容性，不影響現有功能運行

## [0.18.0] - 2025-11-13

### 新增

- **權限服務模組**：新增 `permission_service.py`，提供統一的權限檢查和管理機制
  - 實作角色權限驗證，支持治理系統的複雜權限需求
  - 新增國土安全部門特殊權限處理，增強系統安全性
- **交互兼容層**：新增 `interaction_compat.py`，提供 Discord 交互 API 的兼容性封裝
  - 支持不同版本的 Discord.py 庫，提升系統兼容性
  - 簡化交互處理邏輯，改善開發者體驗
- **資料庫遷移**：新增兩個重要的遷移文件
  - `040_council_multiple_roles.py`：支持議會多重角色功能
  - `041_sc_department_multi_roles.py`：支持州議會部門多重角色功能

### 修改

- **治理系統增強**：大幅改進治理相關的命令和服務
  - 重構 `council.py`，增強議會管理功能和用戶界面
  - 更新 `state_council.py`，改進州議會操作流程和權限控制
  - 改進 `supreme_assembly.py`，提升最高議會的決策和審議功能
- **服務層優化**：改進多個核心服務模組
  - 更新 `council_service.py`，增強議會服務的穩定性和性能
  - 重構 `state_council_service.py`，改善州議會服務的業務邏輯
  - 優化 `department_registry.py`，改進部門註冊和管理機制
- **分頁系統改進**：更新所有分頁器組件
  - 改進 `council_paginator.py`、`supreme_assembly_paginator.py` 和 `paginator.py`
  - 提升大量數據展示的性能和用戶體驗

### 修復

- **權限邊界案例**：修復多個權限檢查的邊界案例問題
  - 新增 `test_permission_boundary_cases.py` 測試確保權限系統穩定性
  - 修復國土安全部門的權限檢查邏輯

### 清理

- **備份文件移除**：清理 `backup/` 目錄下的舊版經濟模組文件
  - 移除超過 3000 行的重複代碼，減少維護負擔
  - 保留核心邏輯在主代碼庫中，確保系統整潔性

### 測試改進

- **新增測試文件**：擴展測試覆蓋範圍
  - `test_council_multiple_roles.py`：測試議會多重角色功能
  - `test_homeland_security_permission.py`：測試國土安全部門權限
  - `test_state_council_department_multiple_roles.py`：測試州議會部門多重角色

### 注意

- 此版本主要專注於治理系統的功能增強和權限管理改進
- 所有變更均保持向後兼容性，不影響現有系統運行
- 新增的權限服務將為未來的功能擴展提供堅實基礎

## [0.17.0] - 2025-11-12

### 新增

- **擴展的幫助系統**：大幅改進 Discord 機器人的幫助指令功能
  - 新增 `HelpParameter` 類型，提供更豐富的參數資訊展示
  - 重構 `help_collector.py`，提供更完善的指令資訊收集機制
  - 擴展 `commands.json` 格式，支援更詳細的指令說明和參數資訊
- **部門註冊表增強**：改進 `department_registry.py` 的功能
  - 新增測試環境支援，提升開發和測試流程
  - 改進類型定義和方法處理，提供更好的程式碼組織
- **服務層改進**：增強多個服務模組的功能
  - 改進 `council_service.py` 的錯誤處理和穩定性
  - 更新 `supreme_assembly_service.py` 的服務邏輯
  - 重構 `state_council_service.py`，提升代碼品質和效能

### 修改

- **錯誤處理優化**：改進多個模組的錯誤處理機制
  - 更新 `retry.py` 的重試邏輯，提供更可靠的錯誤恢復
  - 改進 `state_council.py` 的資料庫連接處理
- **遙測和監控改進**：增強 `listener.py` 的遙測功能
  - 新增更詳細的系統監控指標
  - 改進日誌記錄和性能追蹤
- **依賴更新**：更新專案依賴鎖定檔案 `uv.lock`，確保依賴版本的一致性

### 修復

- **State Council 指令修復**：修復 `state_council.py` 中的資料庫連接問題
- **類型提示改進**：修復多個模組中的類型提示問題，提升代碼品質

### 注意

- 此版本主要專注於穩定性改進和功能增強
- 保持完全向後相容性，不影響現有的治理和經濟系統功能
- 幫助系統的改進將提升使用者體驗和系統可用性

## [0.16.0] - 2025-11-12

### 新增

- **國務院嫌疑人管理系統重構**：全面重構 State Council 嫌疑人管理功能
  - 新增 `SuspectProfile` 和 `SuspectReleaseResult` 資料類型，提供完整的嫌疑人資訊管理
  - 實作自動釋放機制，支援定時釋放嫌疑人的排程功能
  - 新增嫌疑人狀態追蹤與管理介面
- **改進的重試機制**：更新 `retry.py` 提升錯誤處理的穩定性
- **State Council 調度器改進**：大幅重構 `state_council_scheduler.py`，提升效能與可維護性
- **測試覆蓋率擴充**：更新相關單元測試，確保新功能的穩定性

### 修改

- **State Council 指令重構**：大幅修改 `state_council.py`，移除舊的 suspects 指令實作
  - 重新設計指令架構，提升程式碼組織性
  - 更新幫助資料結構，移除過時的指令說明
- **服務層架構改進**：重構 `state_council_service.py`，新增嫌疑人管理相關的業務邏輯
- **測試檔案更新**：更新多個測試檔案以配合新功能的實作
- **依賴鎖定更新**：更新 `uv.lock` 以反映最新的依賴版本

### 注意

- 此版本為重大功能更新，新增了完整的嫌疑人生命週期管理
- 移除了舊版的嫌疑人管理指令，新的實作提供更好的擴展性
- 所有變更保持向後相容性，不影響現有的治理流程

## [0.15.0] - 2025-11-12

### 新增

- **統一編譯器系統（Unified Compiler）**：實現 mypyc 與 mypc 編譯後端的統一管理
  - 支援經濟模組使用 mypyc 編譯，治理模組使用 mypc 編譯
  - 新增 `scripts/compile_modules.py` 統一編譯腳本，支援自動依賴解析與並行編譯
  - 新增 `scripts/migrate_unified_config.py` 配置遷移工具
  - 支援編譯效能監控、基準測試與回滾機制
  - 新增完整的統一編譯器指南（`docs/unified-compiler-guide.md`）
- **Mypc 治理模組編譯支援**：新增治理模組的 mypc 編譯後端
  - 治理模組包含 `council_governance`、`supreme_assembly_governance`、`state_council_governance_mypc`
  - 新增 `scripts/compile_governance_modules.py` 與 `scripts/deploy_governance_modules.sh`
  - GitHub Actions 工作流程 `.github/workflows/mypc-compile.yml` 支援自動編譯
- **效能測試基礎設施**：新增完整的效能監控與基準測試框架
  - `tests/performance/test_mypc_benchmarks.py`：mypc 編譯模組的效能基準測試
  - `tests/performance/test_mypyc_benchmarks.py`：mypyc 編譯模組的效能基準測試
  - `tests/scripts/test_performance_monitor.py`：效能監控工具測試
- **開發者入門指南**：新增 `docs/developer-onboarding.md` 提供完整的開發環境設定指南
- **單元測試擴充**：
  - `test_council_command.py`：理事會指令單元測試
  - `test_state_council_command_core.py`：國務院指令核心功能測試
  - `test_supreme_assembly_command.py`：最高人民會議指令測試
  - `test_telemetry_listener_complete.py`：遙測監聽器完整測試
- **編譯模組備份機制**：在 `backup/` 目錄下儲存 Python 原始版本，用於對比測試

### 修改

- **pyproject.toml**：
  - 新增統一編譯器配置區段 `[tool.unified-compiler]`
  - 擴充 mypyc 配置支援經濟與治理模組
  - 新增統一編譯器的測試、部署、監控配置
- **Makefile**：
  - 新增統一編譯相關命令：`unified-migrate`、`unified-compile`、`unified-compile-test`、`unified-status` 等
  - 整合 mypc 編譯流程到現有建置系統
- **Docker 建置優化**：更新 Dockerfile 支援統一編譯器的多階段建置
- **服務層改進**：更新 `state_council_service.py` 與 `supreme_assembly_service.py` 以支援編譯後模組

### 注意

- 統一編譯器預設使用 mypyc 作為經濟模組後端，mypc 作為治理模組後端
- 編譯過程包含完整的錯誤處理與回滾機制
- 所有變更保持向後相容性，未編譯的 Python 版本仍可正常運行
- 效能監控與基準測試支援持續效能追蹤

## [0.14.0] - 2025-11-11

### 新增

- **國土安全部嫌疑人管理功能**：新增 `/council suspects` 指令，提供完整的嫌疑人管理介面
  - 支援查看所有嫌疑人（以嫌犯身分組成員為清單）
  - 提供下拉選單進行單選/多選釋放
  - 設定自動釋放時間（1-168 小時）
  - 完整的審計軌跡記錄
- **統一 JSON 指令註冊表**：建立標準化的指令資訊管理系統
  - 新增 `src/bot/commands/help_data/` 目錄結構
  - 支援階層式指令結構（主指令/子指令）
  - 優先從 JSON 註冊表讀取指令資訊，保持向後相容
  - 新增主要指令的 JSON 註冊檔
- **政府註冊表擴充**：增強政府組織結構管理
  - 新增「常任理事會」作為最高決策機構
  - 明確政府階層：常任理事會 → 國務院 → 各部門
  - 新增政府階層查詢函數
  - 更新 `departments.json` 支援新的組織結構
- **自動釋放排程功能**：新增記憶體式自動釋放系統
  - 整合至現有的 `state_council_scheduler.py`
  - 支援設定 1-168 小時的自動釋放時間
  - 最小實作（記憶體儲存，重啟後失效）

### 修改

- **help_collector.py**：調整優先順序，優先使用 JSON 註冊表
- **StateCouncilService**：新增 `record_identity_action()` 方法
- **DepartmentRegistry**：擴充支援政府階層結構
- **state_council.py**：新增 suspects 子指令和 SuspectsManagementView

### 測試

- 新增 `test_help_collector_json.py` - 測試 JSON 指令註冊表功能
- 新增 `test_suspects_management.py` - 測試嫌疑人管理功能
- 新增 `test_department_registry_hierarchy.py` - 測試政府層次結構
- 新增 `test_state_council_government_hierarchy.py` - 測試政府層次查詢

### 注意

- 自動釋放功能為最小實作，設定在機器人重啟後會失效
- 所有變更保持向後相容性
- 新的 JSON 註冊表系統不影響現有功能

## [0.13.1] - 2025-11-09

### Fixed

- **合併衝突修復**：修復 v0.13.0 發佈過程中的合併衝突
  - 修復 `src/bot/commands/state_council.py` 中的格式化衝突
  - 修復 `src/bot/services/state_council_service.py` 中的錯誤訊息格式化
  - 修復 `src/db/migrations/versions/039_add_arrest_action.py` 中的檔案結尾衝突

## [0.13.0] - 2025-11-09

### Added

- **國務院身分管理系統（State Council Identity Management）**：實現完整的公民與嫌犯身分管理機制
  - `/state_council config_citizen_role`：設定公民身分組（需管理員或管理伺服器權限）
  - `/state_council config_suspect_role`：設定嫌犯身分組（需管理員或管理伺服器權限）
  - 新增「逮捕」動作支援，國務院可對成員執行逮捕行動
- **資料庫架構擴展**：
  - 新增資料庫遷移 `037_add_identity_role_config.py`：為國務院配置表添加公民與嫌犯身分組欄位
  - 新增資料庫遷移 `038_backcompat_upsert_sc_wrapper.py`：提供向後相容的 upsert 包裝函數
  - 新增資料庫遷移 `039_add_arrest_action.py`：在身分動作枚舉中添加逮捕動作
- **服務層增強**：擴展 `StateCouncilService` 以支援身分管理與逮捕功能
- **最高人民會議傳召功能改進**：優化常任理事會成員傳召流程，提供多選介面
- **測試覆蓋提升**：新增完整的單元測試與整合測試覆蓋新功能

### Changed

- **重試機制優化**：改進 `src/infra/retry.py` 的錯誤處理邏輯
- **資料庫連線管理**：增強 `src/db/pool.py` 的連線池配置
- **測試基礎設施**：更新 `.gitignore` 與 `docker/bin/test.sh` 以支援新的測試需求

## [0.12.1] - 2025-11-08

### Fixed

- **CI/CD 管道修復**：修復 6 個 CI/CD 檢查失敗問題
  - 修復 pre-commit 檢查的 Git 環境配置，添加 `fetch-depth: 0` 和 git 安裝步驟
  - 修復 Integration Tests 的 Docker-in-Docker 連接問題，添加 Docker daemon 就緒等待機制
  - 修復 Database Function Tests 配置，改用 `pg_prove` 執行 pgTAP 測試並安裝 `pgtap` 擴充
  - 修復 Council Tests 路徑配置，將 `tests/council/` 更新為 `tests/integration/council/`
  - 修復 Contract Tests 的路徑解析邏輯，改進 `repo_root()` 函數以正確處理 CI 環境
- **類型安全改進**：
  - 移除 `src/infra/retry.py` 中不必要的 `type: ignore[misc]` 註釋
  - 為 `src/bot/commands/supreme_assembly.py` 中的 `view` 變數添加明確的類型註解

## [0.12.0] - 2025-11-08

### Added

- **最高人民會議治理系統（Supreme Assembly Governance）**：實現完整的最高人民會議提案與投票機制
  - `/supreme_assembly config_speaker_role`：設定最高人民會議議長身分組（需管理員或管理伺服器權限）
  - `/supreme_assembly config_member_role`：設定最高人民會議議員身分組（需管理員或管理伺服器權限）
  - `/supreme_assembly panel`：開啟最高人民會議面板，整合轉帳、表決、傳召與使用指引功能
  - 最高人民會議面板支援即時更新（透過事件訂閱機制）
  - 提案建立時自動鎖定議員名冊快照（N 人）並計算門檻（T = floor(N/2) + 1）
  - 72 小時投票期限，截止前 24 小時 DM 提醒未投票議員
  - 達門檻自動執行轉帳；餘額不足或錯誤記錄「執行失敗」
  - 結案時向全體議員與提案人揭露個別最終投票
  - 同一伺服器進行中提案上限 5 個
  - 投票後不可改選機制（與理事會的可改票機制區分）
  - 議長可發起表決提案、傳召議員或政府官員
- **轉帳功能擴展**：`/transfer` 和 `/adjust` 指令支援以議長身分組為目標（自動映射到最高人民會議帳戶 ID）
  - 議長身分組自動映射到帳戶 ID：`9_200_000_000_000_000 + guild_id`
  - 保持與現有理事會和國務院映射的兼容性
- **資料庫架構**：
  - 新增資料庫遷移 `035_supreme_assembly.py`：建立 `supreme_assembly_config`、`supreme_assembly_proposals`、`proposal_snapshots`、`votes`、`summons` 表
  - 新增資料庫遷移 `036_supreme_assembly_functions.py`：建立相關 SQL 函數
  - 新增 SQL 函數 `fn_supreme_assembly.sql`：提供配置管理、帳戶查詢、提案管理等功能
- **服務層實現**：
  - 新增 `SupremeAssemblyService`：治理邏輯服務層，包含帳戶管理、提案建立、投票邏輯、狀態轉移等
  - 新增 `SupremeAssemblyGovernanceGateway`：資料庫存取層，提供配置、提案、投票、傳召等 CRUD 操作
- **事件系統**：新增 `supreme_assembly_events.py`，支援提案建立、更新、狀態變更、投票等事件發布訂閱
- **完整測試覆蓋**：
  - 新增單元測試：`test_supreme_assembly_service.py`、`test_supreme_assembly_gateway.py`
  - 新增整合測試：`test_supreme_assembly_flow.py`
  - 新增資料庫函數測試：`test_fn_get_supreme_assembly_config.sql`、`test_fn_is_sa_account.sql`、`test_fn_sa_account_id.sql`、`test_fn_upsert_supreme_assembly_config.sql`

### Changed

- **依賴注入**：更新 `bootstrap.py` 以註冊 `SupremeAssemblyService` 和 `SupremeAssemblyGovernanceGateway`
- **重試機制**：更新 `src/infra/retry.py` 以支援新的錯誤類型
- **測試基礎設施**：更新 `conftest.py` 以支援最高人民會議相關測試

## [0.11.0] - 2025-11-08

### Added

- **Mypyc Compilation Support**: Enabled mypyc compilation for economy modules to improve performance
  - Configured mypyc compilation targets for core economy services (`adjustment_service`, `transfer_service`, `balance_service`, `transfer_event_pool`, `currency_config_service`)
  - Configured mypyc compilation targets for economy database gateways (`economy_adjustments`, `economy_transfers`, `economy_queries`, `economy_pending_transfers`, `economy_configuration`)
  - Added compilation scripts (`scripts/mypyc_economy_setup.py`) and Makefile targets (`mypyc-economy`, `mypyc-economy-check`)
  - Integrated mypyc compilation into Docker build process (both `Dockerfile` and `test.Dockerfile`)
  - Added performance benchmarking script (`scripts/bench_economy.py`) with `bench-economy` Makefile target
  - Added `setuptools>=68.0.0` and `wheel>=0.43.0` to dev dependencies for mypyc compilation support

### Changed

- **Build Process**: Updated Dockerfiles to include `build-essential` and compile economy modules during build
  - Production Dockerfile now compiles economy modules to `build/mypyc_out` during image build
  - Test Dockerfile includes compilation support for testing compiled modules
  - Set `PYTHONPATH` to prioritize compiled modules over pure Python versions

### Fixed

- **Type Safety**: Removed unnecessary `type: ignore[misc]` annotation in `src/infra/retry.py`

## [0.10.0] - 2025-11-08

### Added

- **Transfer Command Enhancement**: Support mapping State Council leader role to main government account
  - `/transfer` command now supports State Council leader role as target (automatically maps to main government account)
  - Added `StateCouncilService.derive_main_account_id()` method for stable account ID derivation
  - Comprehensive command-layer tests for council/leader/department role targets
- **Development Tools**: Added Pyright configuration (`pyrightconfig.json`) for enhanced type checking
  - Configured strict type checking mode aligned with mypy settings
  - Pre-configured mypyc settings in `pyproject.toml` for future compilation optimization

### Changed

- **Documentation**: Updated README.md examples to reflect role targets (Council, State Council leader, Department leader)
- **Code Quality**: Fixed type annotation in `retry.py` (`type: ignore[misc]` removed)

### Fixed

- Improved type safety in retry mechanism

## [0.9.0] - 2025-11-07

### Added

- **Currency Configuration Command**: New `/currency_config` command for administrators to customize currency name and icon per server
  - Supports setting currency name (1-20 characters) and icon (single emoji or Unicode character)
  - Currency configuration is displayed in all economy-related commands (`/balance`, `/transfer`, `/adjust`, `/history`) and State Council panel
  - Default currency name is "點" (point) with no icon if not configured
- **Currency Configuration Service**: New `CurrencyConfigService` for managing currency settings
- **Economy Configuration Gateway**: New `EconomyConfigurationGateway` for database operations related to currency configuration
- **Database Migrations**:
  - Migration 031: Add `currency_name` and `currency_icon` columns to `economy_configurations` table
  - Migration 032: Relax governance constraints to allow English enum values alongside Chinese values
  - Migration 033: Allow zero-amount currency issuances (change constraint from `amount > 0` to `amount >= 0`)
  - Migration 034: Allow zero-amount interdepartment transfers (change constraint from `amount > 0` to `amount >= 0`)
- **Comprehensive Test Coverage**: Added extensive SQL function test suite covering:
  - Transfer validation functions (`fn_check_and_approve_transfer`, `fn_check_transfer_cooldown`, `fn_check_transfer_daily_limit`)
  - Governance functions (council, state council, proposals, votes, tallies)
  - Department and government account management functions
  - Currency issuance and interdepartment transfer functions
  - History and reporting functions
- **Integration Tests**: New `test_currency_config_integration.py` for end-to-end currency configuration testing
- **Unit Tests**: New test files for currency configuration command, service, and gateway

### Changed

- **Enhanced Commands**: Updated `/balance`, `/adjust`, `/transfer`, and `/state_council` commands to display custom currency name and icon
- **State Council Reports**: Enhanced to use custom currency configuration in reports and exports
- **SQL Functions**: Updated multiple SQL functions to support relaxed constraints and zero-amount operations
  - Modified `fn_adjust_balance`, `fn_check_and_approve_transfer`, `fn_check_transfer_balance`, `fn_check_transfer_cooldown`, `fn_check_transfer_daily_limit`, `fn_create_pending_transfer`, `fn_get_balance`, `fn_transfer_currency`, `fn_update_pending_transfer_status`
  - Updated governance functions `fn_council` and `fn_state_council` to support relaxed constraints
- **Transfer Event Pool**: Minor updates to support enhanced currency display
- **Dependency Injection**: Updated bootstrap to include currency configuration service registration
- **Test Infrastructure**: Enhanced contract tests and unit tests to cover currency configuration scenarios

### Fixed

- Improved governance constraint flexibility by allowing both Chinese and English enum values
- Enhanced validation for zero-amount operations in currency issuance and interdepartment transfers

## [0.8.0] - 2025-11-07

### Added

- **Dependency Injection Infrastructure**: Introduced comprehensive DI container system
  - New DependencyContainer with lifecycle management (singleton, transient, scoped)
  - Automatic dependency resolution with type inference
  - Bootstrap utilities for container initialization
  - Thread-local scoped instances support
  - Comprehensive test coverage

### Changed

- **Command Registration**: Refactored command registration to support dependency injection
  - Commands now accept optional container parameter for service resolution
  - Backward compatible: falls back to direct instantiation if container not provided
  - Updated all command modules: adjust, balance, council, state_council, transfer
- **Bot Initialization**: Integrated DI container bootstrap in bot startup sequence
- **Test Infrastructure**: Enhanced test fixtures with DI container support

### Fixed

- Improved service lifecycle management and resource cleanup

## [0.6.1] - 2025-01-27

### Added

- **歷史記錄分頁輔助函數**：新增資料庫遷移 `030_history_pagination_helpers.py`，提供 `fn_has_more_history` 輔助函數，支援游標式分頁查詢
- **餘額快照查詢**：新增 `EconomyQueryGateway.fetch_balance_snapshot()` 方法，提供唯讀餘額查詢，避免 `fn_get_balance` 的副作用（鎖等待）

### Changed

- **測試基礎設施改進**：新增 `pytest-timeout>=2.3.0` 依賴，設定 300 秒測試超時時間
- **可觀測性改進**：改進 `TelemetryListener` 的餘額查詢邏輯，優先使用快照查詢以避免鎖等待
- **測試隔離改進**：增強 Docker Compose 測試隔離，使用唯一的專案名稱避免測試間衝突
- **測試清理改進**：改進非同步協調器清理邏輯，新增超時保護機制
- **開發工具改進**：更新 Makefile 命令，使用本地 `uv` 而非 Docker Compose，提升開發效率

### Fixed

- 修復 `test_multi_guild.py` 中的 SQL 佔位符問題
- 改進測試清理與資源管理

## [0.6.0] - 2025-11-07

### Added

- **測試容器基礎設施**：新增獨立的測試容器，提供一致的測試執行環境
  - 建立 `docker/test.Dockerfile`：基於 Python 3.13，包含所有測試依賴（dev dependencies）
  - 建立 `docker/bin/test.sh`：統一的測試執行腳本，支援不同測試類型（unit, contract, integration, performance, db, economy, council, ci）
  - 在 `compose.yaml` 中新增 `test` 服務：自動連接到 PostgreSQL，支援環境變數傳遞
  - 在 `Makefile` 中新增測試容器相關命令：
    - `test-container-build`：建置測試容器映像檔
    - `test-container`：執行所有測試（不含整合測試）
    - `test-container-unit`：執行單元測試
    - `test-container-contract`：執行合約測試
    - `test-container-integration`：執行整合測試
    - `test-container-performance`：執行效能測試
    - `test-container-db`：執行資料庫測試
    - `test-container-economy`：執行經濟相關測試
    - `test-container-council`：執行議會相關測試
    - `test-container-all`：執行所有測試（不含整合測試）
    - `test-container-ci`：執行完整 CI 流程（格式化、lint、型別檢查、所有測試）
  - 測試容器特性：
    - 環境隔離：測試容器與應用容器分離，確保測試環境不影響應用運行
    - 資料庫測試支援：測試容器能夠連接到 Compose 中的 PostgreSQL 服務
    - 覆蓋率報告：自動掛載到本地 `htmlcov/` 目錄
    - 開發時即時更新：測試目錄掛載為唯讀，開發時可即時更新測試檔案
  - 更新 `README.md`：添加測試容器使用說明與各種執行模式說明
- **測試覆蓋率大幅提升**：新增大量單元測試、整合測試與效能測試
  - 新增單元測試：`test_adjust_command.py`、`test_balance_command.py`、`test_transfer_command.py`、`test_retry.py`、`test_logging_config.py`
  - 新增整合測試：`test_multi_guild.py` 測試多伺服器支援
  - 新增效能測試：`test_council_voting.py`、`test_state_council_operations.py`
  - 新增合約測試：`test_council_panel_contract.py`、`test_state_council_panel_contract.py`
  - 改進現有測試：更新多個測試檔案以提升覆蓋率與穩定性

### Changed

- **重試機制改進**：改進 `src/infra/retry.py` 的重試邏輯，提升錯誤處理與可觀測性
- **國務院服務增強**：改進 `state_council_service.py` 與 `state_council_governance.py`，提升功能完整性
- **命令改進**：改進 `balance.py`、`state_council.py`、`transfer.py` 等命令的實作
- **服務層改進**：改進 `balance_service.py`、`transfer_service.py`、`state_council_reports.py` 等服務
- **資料庫測試改進**：更新 `test_fn_check_transfer_balance.sql` 與 `test_fn_create_pending_transfer.sql`

## [0.5.1] - 2025-11-04

### Fixed

- **資料庫連線重試邏輯**：修復 `entrypoint.sh` 中的重試機制，確保至少嘗試 `RETRY_MAX_ATTEMPTS` 次
  - 調整檢查順序，避免單次連線耗時過長導致過早終止
  - 新增負數保護，避免計算錯誤導致 sleep 時間為負
  - 改善可觀測性，確保完整的重試次數與退避行為可見

### Changed

- **轉帳事件池測試改進**：允許測試時傳入資料庫連線參數
  - `TransferEventPoolCoordinator._retry_checks()` 與 `_cleanup_expired()` 現在支援可選的 `connection` 參數
  - 允許測試在同一交易連線中執行，避免跨連線看不到未提交的變更
  - 更新整合測試以使用新的連線注入功能
- **測試容器配置**：在 `compose.yaml` 中新增 `docker/bin` 掛載點
  - 供整合測試呼叫入口腳本（`/app/docker/bin/entrypoint.sh`）
  - 改善測試環境的完整性與一致性

## [0.5.0] - 2025-11-04

### Added

- **開發工具堆疊**：引入業界標準工具提升開發效率與程式碼品質
  - **Pydantic v2**：重構設定管理為 Pydantic 模型，提供型別安全與自動驗證
    - `BotSettings`：Discord bot 設定（`src/config/settings.py`）
    - `PoolConfig`：資料庫連線池設定（`src/config/db_settings.py`）
    - 自動驗證環境變數格式與型別，提供友善的錯誤訊息
  - **pytest-cov**：新增測試覆蓋率報告，整合至 CI 與開發流程
    - HTML 與終端報告輸出
    - CI 中自動上傳覆蓋率報告作為 artifact
  - **Faker**：在測試中引入 Faker 自動生成假資料（中文/英文）
    - 減少手寫測試資料，提升測試效率
    - 在 `tests/conftest.py` 提供 `faker` fixture
  - **Tenacity**：重構重試邏輯使用 Tenacity 裝飾器
    - 簡化重試實作，支援指數退避與抖動策略
    - 應用於轉帳事件池的重試機制（`src/bot/services/transfer_event_pool.py`）
    - 建立共通重試策略模組（`src/infra/retry.py`）
  - **pytest-xdist**：支援並行執行測試，縮短測試時間
    - 預設使用 `-n auto` 自動偵測 CPU 核心數
    - CI 中所有測試套件使用並行執行
  - **pre-commit**：新增 Git hooks 自動執行格式化、lint、型別檢查
    - 設定檔案：`.pre-commit-config.yaml`
    - 包含 black、ruff、mypy 檢查
  - **Hypothesis**：引入屬性測試框架（選用）
    - 可用於複雜邏輯的邊界案例測試
    - 版本要求調整為 `>=6.0.0`（與可用版本相容）
  - **Typer + Rich**：為 CLI 工具預留架構（選用）
  - **watchfiles**：開發時自動重載支援（選用）

### Changed

- 設定載入：從手動 `os.getenv()` 遷移至 Pydantic 模型
  - `src/bot/main.py`：使用新的 `BotSettings` Pydantic 模型
  - `src/db/pool.py`：使用新的 `PoolConfig` Pydantic 模型
  - `tests/conftest.py`：更新測試 fixture 使用新的設定模型
- 重試邏輯：重構轉帳事件池重試機制使用 Tenacity
  - `_retry_checks` 方法使用 `@retry` 裝飾器自動重試資料庫錯誤
- CI 工作流程：整合覆蓋率報告與並行測試執行
  - 所有測試任務使用 `-n auto` 並行執行
  - 自動上傳覆蓋率報告作為 artifact
- 依賴修正：新增 `pydantic-settings>=2.0.0` 作為獨立依賴（Pydantic v2 中 BaseSettings 已分離）
- 測試修正：更新 `transfer_event_pool.py` 的異常處理，支援 Pydantic 驗證錯誤（ValueError）

## [0.4.0] - 2025-11-03

### Added

- **轉帳事件池（Transfer Event Pool）**：實現事件驅動的異步轉帳處理架構
  - 透過 PostgreSQL NOTIFY/LISTEN 機制實現自動檢查與重試
  - 支援餘額、冷卻時間、每日上限的異步檢查
  - 自動重試機制（指數退避，最多 10 次）
  - 預設過期時間 24 小時，定期清理過期請求
  - 環境變數 `TRANSFER_EVENT_POOL_ENABLED` 控制啟用（預設 false，向後相容）
  - 新增 `pending_transfers` 表與相關 SQL 函式（遷移 022-026）
  - 新增 `TransferEventPoolCoordinator` 協調器與 `TelemetryListener` 事件監聽器
  - 新增完整測試覆蓋與架構文檔（`docs/transfer-event-pool.md`）
- **幫助命令系統（/help）**：新增指令說明與查詢功能
  - `/help`：顯示所有可用指令列表或查詢特定指令詳細資訊
  - 自動收集指令樹中的指令資訊（名稱、描述、參數、權限、範例）
  - 支援分類顯示與搜尋功能
  - 新增 `HelpCollector`、`HelpFormatter`、`HelpData` 模組
- **國務院治理系統（State Council Governance）**：擴充完整的部門治理功能
  - `/state_council config_leader`：設定國務院領袖（使用者或身分組）
  - `/state_council panel`：開啟國務院面板（部門管理、發行點數、匯出）
  - 部門配置管理：各部門可設定領導人身分組、稅率、發行上限
  - 部門點數發行：國務院領袖可向各部門發行點數
  - 部門轉帳：各部門可向成員轉帳（透過政府帳戶）
  - 匯出功能：支援匯出部門配置與發行記錄
  - 新增 `StateCouncilService`、`StateCouncilReports`、`StateCouncilScheduler` 服務
  - 新增 `state_council_governance` 資料庫 schema 與相關 SQL 函式（遷移 006-020）
  - 新增完整測試覆蓋（單元、整合、契約測試）
- **CI/CD 工作流程**：新增 GitHub Actions CI 配置
  - 自動執行測試、型別檢查、程式碼品質檢查
  - 支援多 Python 版本測試（3.13）
  - 支援 Docker Compose 整合測試
  - 自動測試轉帳事件池、國務院治理等新功能

### Changed

- `/transfer`：支援事件池模式（當 `TRANSFER_EVENT_POOL_ENABLED=true` 時）
- `/adjust`：支援以部門領導人身分組為目標（自動映射至對應政府帳戶）
- `/balance`：改善分頁顯示與歷史記錄查詢
- `/council`：改善面板功能與指令同步
- 資料庫函式：擴充 `fn_transfer_currency` 支援政府帳戶豁免檢查
- 測試架構：擴充測試工具與契約測試覆蓋

### Planned

- 進一步的監控與可觀測性（metrics/log tracing）
- 更多治理功能與工作流程命令

## [0.3.1] - 2025-10-30

### Fixed

- **斜線指令重複顯示問題**：修復使用 Guild Allowlist 時，允許清單中的伺服器同時看到全域與 Guild 專屬兩份指令的問題
  - Guild Allowlist 現在會自動去重，避免同一 Guild 被重複同步造成潛在副作用或額外延遲
  - 完成 Guild 指令同步後，自動清除全域指令，避免歷史遺留的全域指令與 Guild 指令重複

### Changed

- 改善程式碼品質：優化 import 語句排序、加強類型註解、改善字串格式化

## [0.3.0] - 2025-10-30

### Added

- **治理系統（Council Governance）**：實現完整的常任理事會提案與投票機制
  - `/council config_role`：設定常任理事身分組（需管理員權限）
  - `/council panel`：開啟理事會面板，整合建案、投票、撤案與匯出功能
  - 理事會面板支援即時更新（透過事件訂閱機制）
  - 提案建立時自動鎖定理事名冊快照（N 人）並計算門檻（T = ⌊N/2⌋ + 1）
  - 72 小時投票期限，截止前 24 小時 DM 提醒未投票理事
  - 達門檻自動執行轉帳；餘額不足或錯誤記錄「執行失敗」
  - 結案時向全體理事與提案人揭露個別最終投票
  - 同一伺服器進行中提案上限 5 個
  - 提案人可於無票前撤案
- 新增 `src/infra/events/council_events.py`：治理事件發布訂閱機制（支援 Panel 即時更新）
- 新增 `src/db/gateway/council_governance.py`：治理資料層（CouncilConfig、Proposal、Vote、Tally）
- 新增 `src/bot/services/council_service.py`：治理業務邏輯層（建案、投票、執行、匯出）
- 新增 `src/bot/commands/council.py`：Discord UI（Panel、VotingView、Modal）與背景排程器
- 新增資料庫 migration `005_governance_council.py`：建立 governance schema（council_config、proposals、proposal_snapshots、votes）
- 新增完整測試覆蓋：
  - `tests/unit/test_council_service.py`：服務層單元測試
  - `tests/unit/test_council_math.py`：門檻計算邏輯測試
  - `tests/integration/council/test_council_flow.py`：完整提案流程整合測試
  - `tests/integration/council/test_panel_contract.py`：面板契約測試
- 新增 `AGENTS.md`：OpenSpec 指引（AI 助手開發規範）

### Changed

- `/adjust` 與 `/transfer` 命令支援以理事會身分組為目標（自動映射至理事會帳戶）
- `src/bot/main.py`：啟用成員 Intent（`intents.members = True`）以讀取角色成員清單
- `src/bot/main.py`：改進指令同步機制（使用 `copy_global_to()` 加速公會內指令可見性）
- `compose.yaml`：改用自訂 `docker/postgres.Dockerfile` 並啟用 pg_cron（`shared_preload_libraries=pg_cron`）
- `docker/init/001_extensions.sql`：新增 `CREATE EXTENSION pg_cron`
- `.gitignore`：新增 `*.pyc`、`.envrc`、`.claude/`、`.cursor/`、`openspec/`
- README.md：新增「治理（Council Governance，MVP）」與「理事會面板（Panel）」完整使用說明

### Removed

- 刪除 `.envrc`（已加入 .gitignore）
- 清理所有 `__pycache__/*.pyc` 編譯快取檔案

### Notes

- 治理功能需要 Discord 開發者後台啟用「成員 Intent」
- MVP 版本僅透過 DM 進行互動與通知，無公開頻道摘要
- 需要 PostgreSQL 安裝 pg_cron 擴充以支援背景排程任務

## [0.2.2] - 2025-10-24

### Added

- 新增 `docker/Dockerfile`（基於 uv 的精簡建置流程）與 `docker/bin/entrypoint.sh`（啟動前環境檢查、DB 連線重試、Alembic 自動遷移、結構化 JSON 日誌事件）。
- 新增 `src/infra/logging/config.py`：統一 JSON Lines 日誌格式（鍵包含 `ts`,`level`,`msg`,`event`），並內建敏感值遮罩（`token`/`authorization`/`password` 等）。
- 新增契約與規格（`specs/002-docker-run-bot`）：Compose 環境變數 Schema、日誌事件 Schema、OpenAPI 草案等。
- 新增測試覆蓋：
  - contracts：`.env.example` 必要鍵驗證、日誌事件 Schema、日誌遮罩。
  - integration：Compose 就緒（於 120s 內 `{"event":"bot.ready"}`）、依賴順序、外部 DB 覆寫/不可用（退出碼 69）、遷移失敗（退出碼 70）、缺少必要環境（退出碼 64）、重試退避參數行為等。
- 新增 `scripts/check_image_layers.sh` 供鏡像層級敏感字樣掃描；新增 `.envrc`（direnv）。

### Changed

- 將根目錄 `Dockerfile` 移至 `docker/Dockerfile`，`compose.yaml` 改以新路徑建置；調整 `.dockerignore` 以縮小映像內容。
- 更新 `.env.example`：新增 `ALEMBIC_UPGRADE_TARGET` 與 pgAdmin 預設設定與說明。
- README：新增「日誌與可觀測性」章節，補充就緒事件與退出碼說明。

### Security

- 日誌遮罩常見敏感鍵，避免在 stdout 泄露密碼或 Token。

### Notes

- 無安裝 `pg_cron` 的環境預設遷移目標為 `003_economy_adjustments`；如需每日歸檔請安裝 `pg_cron` 後升級至 `head`。
- 直接透過 Docker 建置時請使用 `-f docker/Dockerfile`。

## [0.2.1] - 2025-10-23

### Added

- 新增 `compose.yaml` + `Dockerfile`，可透過 `docker compose up -d` 一鍵啟動 Bot 與 PostgreSQL（與選用 pgAdmin），避免因未啟動資料庫導致連線被拒。
- 新增 `docker/init/001_extensions.sql`，首次啟動自動建立 `pgcrypto` 擴充。

### Changed

- README：擴充安裝與啟動指南，加入 Docker Compose（可直接啟動 Bot）、連線自測、故障排除，並新增「使用 Git 更新專案」章節。
- 專案版本提升至 0.2.1。

### Notes

- Alembic 遷移 `004_economy_archival` 需要 `pg_cron`。若環境未安裝 `pg_cron`，可先升級至 `003_economy_adjustments` 後再升級至 `head`。

## [0.2.0] - 2025-10-23

### Added

- 實現完整的 Discord 經濟系統功能
- 新增 `/balance` 斜杠命令，支援查詢個人和他人餘額
- 新增 `/history` 斜杠命令，支援查看交易歷史記錄
- 新增 `/transfer` 斜杠命令，支援成員間虛擬貨幣轉移
- 新增 `/adjust` 斜杠命令，支援管理員調整成員點數
- 實現基於 Discord 權限的分級權限系統
- 新增交易限流機制，包含每日轉帳限制和冷卻時間
- 實現 PostgreSQL 資料庫架構，包含經濟系統表和事務處理
- 新增自動歸檔機制，30 天後自動歸檔舊交易記錄
- 實現完整的審計系統，記錄所有管理員操作
- 新增多伺服器支援，每個 Discord 伺服器有獨立的經濟系統

### Changed

- 更新項目描述，反映經濟系統功能
- 更新安裝和配置說明，包含資料庫設定步驟
- 更新 README.md，添加詳細的功能說明和使用指南

### Fixed

- 修復餘額不能變為負數的保護機制
- 確保所有交易操作的 ACID 特性

## [0.1.0] - 2025-10-18

### Changed

- 將專案技術棧更新為 Python 與 PostgreSQL
- 調整 README 與開發流程文件以支援 Python 工具鏈
- 更新 `.gitignore` 以忽略 Python 相關暫存檔案與虛擬環境
