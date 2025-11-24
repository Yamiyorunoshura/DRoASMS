# infrastructure Specification

## Purpose
TBD - created by archiving change add-result-error-handling. Update Purpose after archive.
## Requirements
### Requirement: 指令處理錯誤管理
指令處理器 SHALL 使用 Result<T,E> 模式進行錯誤處理，替代傳統的異常捕獲機制。

#### Scenario: 命令執行錯誤
- **WHEN** 斜線指令執行過程中發生錯誤時
- **THEN** 指令處理器必須返回 Result.Err 而非拋出異常
- **AND** 錯誤回應必須使用標準化的 Discord 訊息格式
- **AND** 系統必須記錄詳細的錯誤上下文到日誌

#### Scenario: 參數驗證錯誤
- **WHEN** 指令參數驗證失敗時
- **THEN** 必須返回包含具體驗證錯誤的 Result
- **AND** 錯誤訊息必須指出哪些參數無效及原因
- **AND** 必須提供正確的參數使用範例

### Requirement: 服務層錯誤傳播
服務層 SHALL 統一使用 Result 類型進行錯誤傳播，避免異常跨層傳遞。

#### Scenario: 跨服務調用錯誤
- **WHEN** 服務 A 調用服務 B 時發生錯誤
- **THEN** 服務 B 必須返回 Result.Err
- **AND** 服務 A 必須正確處理和轉發錯誤
- **AND** 錯誤上下文必須保留完整的調用鏈資訊

#### Scenario: 資料庫操作錯誤
- **WHEN** 資料庫 gateway 操作失敗時
- **THEN** gateway 方法必須返回 Result.Err
- **AND** 服務層必須使用 Result.map 或 Result.and_then 處理
- **AND** 資料庫錯誤必須包含查詢參數和執行上下文

#### Scenario: 權限服務 Result 化
- **WHEN** Discord 指令或 UI 需要檢查治理權限
- **THEN** `src.bot.services.permission_service.PermissionService` MUST 回傳 `Result[PermissionResult, Error]`
- **AND** 呼叫端不得再依賴布林或例外判斷
- **AND** 當權限不足或服務回傳 Err 時，必須使用 `ErrorMessageTemplates` 產生統一訊息

### Requirement: 事務處理錯誤回滾
事務操作 SHALL 與 Result 機制集成，確保錯誤情況下的正確回滾。

#### Scenario: 事務執行錯誤
- **WHEN** 事務中的任何操作返回 Result.Err 時
- **THEN** 事務管理器必須自動回滾所有更改
- **AND** 必須返回包含回滾狀態的 Result
- **AND** 回滾失敗必須記錄為嚴重錯誤

#### Scenario: 部分成功操作
- **WHEN** 批次操作中部分成功、部分失敗時
- **THEN** 必須返回包含成功和失敗詳細信息的 Result
- **AND** 已成功的操作必須正確提交
- **AND** 失敗操作的錯誤必須詳細記錄

### Requirement: Container-based Deployment
The system SHALL provide Docker containers for all services including bot, database, and tooling, with environment-specific optimization for development and production deployments.

#### Scenario: Development environment startup
- **WHEN** developer runs `make start-dev`
- **THEN** all services start including bot, postgres, and pgadmin
- **AND** containers include complete development toolchain
- **AND** bot container mounts development volumes for live code updates

#### Scenario: Production environment startup
- **WHEN** operator runs `make start-prod`
- **THEN** only essential services start (bot and postgres)
- **AND** containers contain minimal runtime dependencies
- **AND** services run in detached mode with automatic restart policy

#### Scenario: Build optimization
- **WHEN** containers are built for specific environments
- **THEN** development containers include all dependency groups for comprehensive tooling
- **AND** production containers include only runtime dependencies
- **AND** build artifacts are optimized for target environment size and security

#### Scenario: Service health and dependencies
- **WHEN** containers start in any environment
- **THEN** bot container waits for postgres health check before starting
- **AND** database initialization scripts run automatically
- **AND** service startup order is maintained across environments

### Requirement: Container Build Optimization
容器建置過程 SHALL 實施階層化檔案複製和快取優化，以減少建置時間和映像大小。

#### Scenario: Efficient file copying during container build
- **WHEN** building Docker containers
- **THEN** only essential files SHALL be copied to the final image
- **AND** build dependencies SHALL be isolated in separate layers
- **AND** .dockerignore SHALL exclude development artifacts, documentation, and test files

#### Scenario: Optimized dependency caching
- **WHEN** dependencies haven't changed
- **THEN** dependency installation layers SHALL be cached
- **AND** source code changes SHALL not trigger dependency reinstallation

#### Scenario: Multi-stage build efficiency
- **WHEN** building production containers
- **THEN** build tools SHALL only exist in intermediate stages
- **AND** final image SHALL contain only runtime dependencies

### Requirement: Container Image Size Reduction
容器映像 SHALL 排除不必要的檔案以最小化映像大小，提升部署效率。

#### Scenario: Development files exclusion
- **WHEN** building production containers
- **THEN** test files, documentation, and development tools SHALL be excluded
- **AND** only runtime-critical files SHALL be included in final image

#### Scenario: Build artifact cleanup
- **WHEN** multi-stage builds complete
- **THEN** intermediate build artifacts SHALL be removed
- **AND** only compiled extensions and essential runtime files SHALL remain

### Requirement: Environment-Specific Container Builds
The system SHALL provide separate Docker container builds for development and production environments with optimized dependency management.

#### Scenario: Development container with full toolchain
- **WHEN** developer executes `make start-dev`
- **THEN** the system builds and starts containers containing all development dependencies including testing frameworks, linting tools, and compilation utilities
- **AND** pgadmin service is included for database management
- **AND** all development tools are available inside the bot container

#### Scenario: Production container with minimal dependencies
- **WHEN** operator executes `make start-prod`
- **THEN** the system builds and starts containers containing only runtime dependencies required for bot operation
- **AND** development tools are excluded to reduce attack surface
- **AND** only bot and postgres services are started in background mode

#### Scenario: Consistent build interface
- **WHEN** developers use either start-dev or start-prod commands
- **THEN** the build process uses consistent Docker layer caching strategy
- **AND** both environments produce functionally equivalent bot behavior
- **AND** environment-specific optimizations are applied transparently

#### Scenario: Development workflow preservation
- **WHEN** developers execute testing or compilation commands in development environment
- **THEN** all required tools (pytest, mypy, black, ruff, Cython, mypyc) are available
- **AND** compilation of performance modules works correctly
- **AND** full test suite can be executed without additional setup
