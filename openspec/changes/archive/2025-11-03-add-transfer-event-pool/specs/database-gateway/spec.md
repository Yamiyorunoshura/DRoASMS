## ADDED Requirements

### Requirement: Pending Transfers Table
資料庫必須（MUST）提供 `economy.pending_transfers` 表，用於記錄待處理轉帳請求及其檢查狀態。

#### Scenario: 建立 pending_transfers 表
- **WHEN** 執行資料庫遷移
- **THEN** 建立 `economy.pending_transfers` 表，包含以下欄位：
  - `transfer_id` (UUID, PRIMARY KEY)
  - `guild_id` (bigint, NOT NULL)
  - `initiator_id` (bigint, NOT NULL)
  - `target_id` (bigint, NOT NULL)
  - `amount` (bigint, NOT NULL)
  - `status` (text, NOT NULL, 值為 `pending`、`checking`、`approved`、`rejected`)
  - `checks` (jsonb, 記錄各項檢查狀態：`balance`、`cooldown`、`daily_limit`，值為 1 或 0)
  - `retry_count` (integer, DEFAULT 0)
  - `expires_at` (timestamptz, NOT NULL)
  - `metadata` (jsonb, DEFAULT '{}')
  - `created_at` (timestamptz, DEFAULT now())
  - `updated_at` (timestamptz, DEFAULT now())

#### Scenario: pending_transfers 表索引
- **WHEN** 建立 `pending_transfers` 表
- **THEN** 必須建立以下索引：
  - `(guild_id, status)` 複合索引，用於查詢特定 guild 的待處理轉帳
  - `(expires_at)` 索引，用於過期記錄清理
  - `(status, updated_at)` 複合索引，用於查詢需要重試的記錄

### Requirement: Transfer Check Trigger
資料庫必須（MUST）在插入 `pending_transfers` 記錄時自動觸發檢查流程。

#### Scenario: 插入記錄時觸發檢查
- **WHEN** 插入新的 `pending_transfers` 記錄，狀態為 `pending`
- **THEN** 觸發器自動將狀態更新為 `checking`
- **AND** 啟動各項檢查（餘額、冷卻、限額）的異步執行流程

#### Scenario: 檢查結果更新到 checks 欄位
- **WHEN** 每項檢查執行完成
- **THEN** 檢查結果（1=通過，0=失敗）更新到 `checks` JSONB 欄位的對應鍵
- **AND** 透過 `pg_notify` 發送檢查結果事件到 `economy_events` 通道

#### Scenario: 所有檢查通過時標記為 approved
- **WHEN** `checks` JSONB 欄位中所有檢查項目的值都為 1
- **THEN** 狀態自動更新為 `approved`
- **AND** 透過 `pg_notify` 發送 `transfer_check_approved` 事件

### Requirement: Transfer Check Functions
資料庫必須（MUST）提供 SQL 函式執行各項轉帳檢查（餘額、冷卻、限額），並將結果更新到 `pending_transfers.checks` 欄位。

#### Scenario: 餘額檢查函式
- **WHEN** 呼叫檢查餘額的 SQL 函式（如 `fn_check_transfer_balance`）
- **THEN** 函式檢查 `initiator_id` 的餘額是否足夠
- **AND** 將檢查結果（1 或 0）更新到 `pending_transfers.checks->>'balance'`
- **AND** 透過 `pg_notify` 發送檢查結果事件

#### Scenario: 冷卻檢查函式
- **WHEN** 呼叫檢查冷卻的 SQL 函式（如 `fn_check_transfer_cooldown`）
- **THEN** 函式檢查 `initiator_id` 是否在冷卻期間（`throttled_until > now()`）
- **AND** 將檢查結果（1 或 0）更新到 `pending_transfers.checks->>'cooldown'`
- **AND** 透過 `pg_notify` 發送檢查結果事件

#### Scenario: 每日上限檢查函式
- **WHEN** 呼叫檢查每日上限的 SQL 函式（如 `fn_check_transfer_daily_limit`）
- **THEN** 函式檢查 `initiator_id` 今日轉帳總額是否超過每日上限（500）
- **AND** 將檢查結果（1 或 0）更新到 `pending_transfers.checks->>'daily_limit'`
- **AND** 透過 `pg_notify` 發送檢查結果事件

### Requirement: Gateway Methods for Pending Transfers
Gateway 層必須（MUST）提供方法操作 `pending_transfers` 表，透過 SQL 函式而非直接查詢資料表。

#### Scenario: 建立待處理轉帳記錄
- **WHEN** Gateway 需要建立待處理轉帳記錄
- **THEN** 必須呼叫 SQL 函式（如 `fn_create_pending_transfer`）而非直接 `INSERT INTO pending_transfers`

#### Scenario: 查詢待處理轉帳記錄
- **WHEN** Gateway 需要查詢待處理轉帳記錄
- **THEN** 必須呼叫 SQL 函式（如 `fn_get_pending_transfer`、`fn_list_pending_transfers`）而非直接 `SELECT FROM pending_transfers`

#### Scenario: 更新待處理轉帳狀態
- **WHEN** Gateway 需要更新待處理轉帳狀態
- **THEN** 必須呼叫 SQL 函式（如 `fn_update_pending_transfer_status`）而非直接 `UPDATE pending_transfers`
