## MODIFIED Requirements

### Requirement: Simplified Database Migration Strategy
資料庫遷移系統 SHALL 統一使用 `head` 作為遷移目標，移除複雜的版本設定和回退邏輯。

#### Scenario: Head migration execution
- **WHEN** container starts
- **THEN** alembic upgrade head SHALL be executed
- **AND** no fallback migration logic SHALL be applied
- **AND** migration failures SHALL result in immediate container termination

#### Scenario: Environment configuration simplification
- **WHEN** configuring database migrations
- **THEN** ALEMBIC_UPGRADE_TARGET environment variable SHALL be ignored
- **AND** migration configuration SHALL be handled by Alembic internally
- **AND** users SHALL NOT need to specify migration targets

## REMOVED Requirements

### Requirement: Migration Target Configuration
**Reason**: Simplified deployment and reduces user configuration errors by always using head migrations.
**Migration**: Existing deployments will automatically use head migrations; no manual intervention required.

- Previous requirement allowed configurable ALEMBIC_UPGRADE_TARGET with fallback logic
- Previous requirement supported specific migration version targeting (e.g., 003_economy_adjustments)
- Previous requirement implemented complex retry and fallback mechanisms

## ADDED Requirements

### Requirement: Migration Error Handling
遷移失敗時 SHALL 提供清晰的錯誤訊息和診斷資訊。

#### Scenario: Migration failure diagnostics
- **WHEN** alembic upgrade head fails
- **THEN** detailed error information SHALL be logged
- **AND** specific migration causing failure SHALL be identified
- **AND** remediation suggestions SHALL be provided

#### Scenario: Database compatibility validation
- **WHEN** migrations execute
- **THEN** database version compatibility SHALL be validated
- **AND** required PostgreSQL extensions SHALL be verified
- **AND** missing dependencies SHALL be clearly reported
