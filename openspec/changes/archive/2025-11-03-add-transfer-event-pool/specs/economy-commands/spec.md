## ADDED Requirements

### Requirement: Asynchronous Transfer Event Pool
系統必須（MUST）提供異步轉帳事件池機制，允許轉帳請求在檢查失敗時自動重試，無需使用者手動操作。

#### Scenario: 轉帳請求進入事件池
- **WHEN** 使用者執行 `/transfer` 指令，且系統啟用事件池模式
- **THEN** 轉帳請求被記錄到 `economy.pending_transfers` 表，狀態為 `pending`
- **AND** 觸發器自動啟動檢查流程，狀態變更為 `checking`

#### Scenario: 所有檢查通過後自動執行轉帳
- **WHEN** `pending_transfers` 記錄的所有檢查（餘額、冷卻、限額）都標記為通過（值為 1）
- **THEN** Python 層自動呼叫 `fn_transfer_currency` 執行實際轉帳
- **AND** 狀態更新為 `approved`，轉帳結果返回給使用者

#### Scenario: 檢查失敗時自動重試
- **WHEN** 轉帳檢查失敗（餘額不足、冷卻中、超過每日上限）
- **THEN** 系統使用指數退避策略自動重試（間隔為 `2^retry_count` 秒，上限 300 秒）
- **AND** 重試計數增加，最多重試 10 次
- **AND** 若超過重試上限或記錄過期，狀態標記為 `rejected`

#### Scenario: 檢查結果記錄在 JSONB 欄位
- **WHEN** 每項檢查（餘額、冷卻、限額）執行完成
- **THEN** 檢查結果（1=通過，0=失敗）記錄到 `pending_transfers.checks` JSONB 欄位
- **AND** 透過 `pg_notify` 發送檢查結果事件，Python 層可即時追蹤狀態

#### Scenario: 過期記錄自動清理
- **WHEN** `pending_transfers` 記錄超過過期時間（預設 24 小時）
- **THEN** 系統定期清理過期記錄（透過 `pg_cron` 或 Python 層定時任務）
- **AND** 清理前將狀態標記為 `rejected`（若仍為 `pending` 或 `checking`）

### Requirement: Transfer Event Pool Configuration
系統必須（MUST）允許透過配置啟用或停用事件池架構，預設行為應保持向後相容。

#### Scenario: 事件池模式可配置
- **WHEN** 環境變數 `TRANSFER_EVENT_POOL_ENABLED=true` 或配置檔案啟用事件池
- **THEN** `/transfer` 指令使用事件池架構處理轉帳請求
- **WHEN** 事件池未啟用
- **THEN** `/transfer` 指令使用現有同步轉帳路徑（直接呼叫 `fn_transfer_currency`）
