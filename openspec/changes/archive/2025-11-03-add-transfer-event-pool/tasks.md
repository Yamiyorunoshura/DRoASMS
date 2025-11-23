## 1. 資料庫層基礎設施

- [x] 1.1 建立資料庫遷移腳本，新增 `economy.pending_transfers` 表
  - 定義表結構（transfer_id, guild_id, initiator_id, target_id, amount, status, checks, retry_count, expires_at, metadata, created_at, updated_at）
  - 建立必要的索引（(guild_id, status), (expires_at), (status, updated_at)）
  - 驗證：執行遷移後確認表結構正確

- [x] 1.2 實作 SQL 函式 `fn_create_pending_transfer`
  - 參數：guild_id, initiator_id, target_id, amount, metadata, expires_at
  - 功能：插入 `pending_transfers` 記錄，狀態為 `pending`
  - 驗證：單元測試確認函式正確插入記錄

- [x] 1.3 實作觸發器 `trigger_pending_transfer_check`
  - 觸發時機：插入 `pending_transfers` 記錄時
  - 功能：將狀態更新為 `checking`，啟動檢查流程
  - 驗證：單元測試確認觸發器正確執行

- [x] 1.4 實作檢查函式 `fn_check_transfer_balance`
  - 參數：transfer_id
  - 功能：檢查餘額是否足夠，更新 `checks->>'balance'`，發送 NOTIFY 事件
  - 驗證：單元測試確認檢查邏輯正確

- [x] 1.5 實作檢查函式 `fn_check_transfer_cooldown`
  - 參數：transfer_id
  - 功能：檢查冷卻期間，更新 `checks->>'cooldown'`，發送 NOTIFY 事件
  - 驗證：單元測試確認檢查邏輯正確

- [x] 1.6 實作檢查函式 `fn_check_transfer_daily_limit`
  - 參數：transfer_id
  - 功能：檢查每日上限，更新 `checks->>'daily_limit'`，發送 NOTIFY 事件
  - 驗證：單元測試確認檢查邏輯正確

- [x] 1.7 實作 SQL 函式 `fn_get_pending_transfer`、`fn_list_pending_transfers`
  - 功能：查詢待處理轉帳記錄
  - 驗證：單元測試確認查詢功能正確

- [x] 1.8 實作 SQL 函式 `fn_update_pending_transfer_status`
  - 參數：transfer_id, new_status
  - 功能：更新狀態，更新 `updated_at`
  - 驗證：單元測試確認更新功能正確

- [x] 1.9 實作觸發器邏輯：所有檢查通過時自動標記為 `approved`
  - 功能：當 `checks` JSONB 中所有值為 1 時，更新狀態為 `approved`，發送 `transfer_check_approved` 事件
  - 驗證：單元測試確認觸發器邏輯正確

## 2. Python 層 Gateway

- [x] 2.1 在 `src/db/gateway/` 新增 `economy_pending_transfers.py`
  - 實作 `PendingTransferGateway` 類別
  - 方法：`create_pending_transfer`, `get_pending_transfer`, `list_pending_transfers`, `update_status`
  - 驗證：單元測試確認 Gateway 方法正確呼叫 SQL 函式

- [x] 2.2 定義 `PendingTransfer` 資料類別
  - 欄位對應 `pending_transfers` 表結構
  - 驗證：單元測試確認資料類別正確映射

## 3. Python 層事件監聽與協調

- [x] 3.1 擴展 `TelemetryListener` 監聽檢查結果事件
  - 新增事件處理器：`transfer_check_result`、`transfer_check_approved`
  - 驗證：單元測試確認事件監聽正確

- [x] 3.2 實作檢查狀態追蹤邏輯
  - 追蹤每個 `transfer_id` 的所有檢查狀態
  - 當所有檢查為 1 時，標記為「準備執行」
  - 驗證：單元測試確認狀態追蹤正確

- [x] 3.3 實作協調邏輯：所有檢查通過時執行轉帳
  - 當收到 `transfer_check_approved` 事件或狀態追蹤顯示所有檢查通過時
  - 呼叫 `fn_transfer_currency` 執行實際轉帳
  - 更新 `pending_transfers` 狀態為 `approved` 或 `rejected`（若轉帳失敗）
  - 驗證：整合測試確認完整流程正確

- [x] 3.4 實作重試機制（指數退避）
  - 檢查失敗時，計算下次重試時間（`2^retry_count` 秒，上限 300 秒）
  - 更新 `retry_count`，若超過 10 次則標記為 `rejected`
  - 排程下次重試
  - 驗證：單元測試確認重試邏輯正確

- [x] 3.5 實作過期清理機制
  - 定期查詢 `expires_at < now()` 的記錄
  - 將狀態標記為 `rejected`（若仍為 `pending` 或 `checking`）
  - 刪除過期記錄（或保留為歷史記錄）
  - 驗證：單元測試確認清理邏輯正確

## 4. Service 層整合

- [x] 4.1 擴展 `TransferService` 支援事件池模式
  - 新增參數或配置選項啟用事件池
  - 當啟用時，呼叫 `PendingTransferGateway.create_pending_transfer` 而非直接呼叫 `fn_transfer_currency`
  - 驗證：單元測試確認 Service 層正確處理兩種模式

- [x] 4.2 實作事件池模式的結果查詢
  - 當轉帳請求進入事件池時，返回 `transfer_id` 給使用者
  - 提供查詢方法檢查轉帳狀態
  - 驗證：整合測試確認使用者可查詢轉帳狀態

## 5. 配置與環境變數

- [x] 5.1 新增環境變數 `TRANSFER_EVENT_POOL_ENABLED`
  - 預設值：`false`（保持向後相容）
  - 驗證：確認配置正確載入

- [x] 5.2 更新 `.env.example` 文件
  - 新增 `TRANSFER_EVENT_POOL_ENABLED` 說明
  - 驗證：確認文件正確

## 6. 測試

- [x] 6.1 單元測試：資料庫函式與觸發器
  - 測試 `fn_create_pending_transfer`、檢查函式、觸發器邏輯
  - 驗證：所有單元測試通過

- [x] 6.2 單元測試：Gateway 層
  - 測試 `PendingTransferGateway` 所有方法
  - 驗證：所有單元測試通過

- [x] 6.3 單元測試：事件監聽與協調邏輯
  - 測試檢查狀態追蹤、協調邏輯、重試機制
  - 驗證：所有單元測試通過

- [x] 6.4 整合測試：完整轉帳流程（成功案例）
  - 測試轉帳請求進入事件池 → 檢查通過 → 自動執行轉帳 → 返回結果
  - 驗證：整合測試通過

- [x] 6.5 整合測試：重試流程（失敗案例）
  - 測試餘額不足 → 自動重試 → 餘額足夠後成功
  - 測試冷卻中 → 自動重試 → 冷卻結束後成功
  - 驗證：整合測試通過

- [x] 6.6 整合測試：過期清理
  - 測試過期記錄自動清理
  - 驗證：整合測試通過

- [x] 6.7 契約測試：事件格式
  - 測試 NOTIFY 事件格式符合預期
  - 驗證：契約測試通過

## 7. 文件與遷移

- [x] 7.1 更新資料庫遷移文件
  - 說明 `pending_transfers` 表用途與結構
  - 驗證：確認文件完整

- [x] 7.2 更新架構文件
  - 說明事件池架構設計與使用方式
  - 驗證：確認文件清晰易懂
