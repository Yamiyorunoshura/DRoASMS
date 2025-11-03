# 轉帳事件池架構文件

## 概述

轉帳事件池（Transfer Event Pool）是一個事件驅動的異步轉帳處理架構，將轉帳檢查與執行分離，透過 PostgreSQL 的 NOTIFY/LISTEN 機制實現自動重試與協調。

## 架構設計

### 核心組件

1. **資料庫層**
   - `economy.pending_transfers` 表：儲存待處理轉帳請求
   - SQL 函式：建立、查詢、更新待處理轉帳
   - 檢查函式：`fn_check_transfer_balance`、`fn_check_transfer_cooldown`、`fn_check_transfer_daily_limit`
   - 觸發器：自動觸發檢查流程

2. **Python 層 Gateway**
   - `PendingTransferGateway`：封裝資料庫操作
   - `PendingTransfer`：資料類別

3. **事件協調層**
   - `TransferEventPoolCoordinator`：協調檢查結果與執行轉帳
   - `TelemetryListener`：監聽 PostgreSQL NOTIFY 事件

4. **Service 層**
   - `TransferService`：支援同步與事件池兩種模式

## 工作流程

### 1. 建立待處理轉帳

```python
transfer_id = await service.transfer_currency(
    guild_id=guild_id,
    initiator_id=initiator_id,
    target_id=target_id,
    amount=100,
    reason="test",
)
# 在事件池模式下返回 UUID，而非 TransferResult
```

### 2. 自動檢查流程

當 `pending_transfers` 記錄被插入時：
1. 觸發器自動將狀態更新為 `checking`
2. 自動執行三個檢查函式：
   - `fn_check_transfer_balance`：檢查餘額
   - `fn_check_transfer_cooldown`：檢查冷卻時間
   - `fn_check_transfer_daily_limit`：檢查每日上限
3. 每個檢查函式發送 `transfer_check_result` 事件

### 3. 檢查結果處理

`TransferEventPoolCoordinator` 監聽檢查結果：
- 當所有檢查通過（都為 1）時，自動執行轉帳
- 當有檢查失敗時，排程重試（指數退避）

### 4. 轉帳執行

當所有檢查通過：
1. 狀態自動更新為 `approved`（透過 `_check_and_approve_transfer`）
2. 發送 `transfer_check_approved` 事件
3. `TransferEventPoolCoordinator` 執行實際轉帳
4. 轉帳成功後，狀態更新為 `completed`

## 狀態轉換

```
pending → checking → approved → completed
                ↓
            rejected (檢查失敗或轉帳失敗)
```

狀態說明：
- `pending`：剛建立的待處理轉帳
- `checking`：正在進行檢查
- `approved`：所有檢查通過，準備執行
- `completed`：轉帳已成功執行
- `rejected`：檢查失敗、轉帳失敗、或過期

## 重試機制

### 指數退避策略

- 重試延遲：`min(2^retry_count, 300)` 秒
- 最大重試次數：10 次
- 超過重試上限後，狀態標記為 `rejected`

### 重試觸發條件

當以下任一檢查失敗時會自動重試：
- 餘額不足
- 冷卻中
- 每日上限已達

## 過期清理

- 定期清理（每分鐘執行一次）
- 查詢 `expires_at < now()` 且狀態為 `pending` 或 `checking` 的記錄
- 將過期記錄標記為 `rejected`

## 事件格式

### transfer_check_result

```json
{
  "event_type": "transfer_check_result",
  "transfer_id": "uuid",
  "check_type": "balance|cooldown|daily_limit",
  "result": 0|1,
  "guild_id": 123456789,
  "initiator_id": 111111111,
  "balance": 500,  // 僅 balance 檢查
  "required": 100,  // 僅 balance 檢查
  "throttled_until": null,  // 僅 cooldown 檢查
  "total_today": 0,  // 僅 daily_limit 檢查
  "attempted_amount": 100,  // 僅 daily_limit 檢查
  "limit": 500  // 僅 daily_limit 檢查
}
```

### transfer_check_approved

```json
{
  "event_type": "transfer_check_approved",
  "transfer_id": "uuid",
  "guild_id": 123456789,
  "initiator_id": 111111111,
  "target_id": 222222222,
  "amount": 100
}
```

### transaction_denied（事件池）

- 發生時機：
  - 重試達上限（10 次）且檢查仍未全部通過 → 標記為 `rejected` 後發送。
  - 待處理請求逾期（`expires_at < now()`）被清理為 `rejected`。
- 來源：`TransferEventPoolCoordinator` 於資料庫交易中呼叫 `pg_notify`。

範例 payload：

```json
{
  "event_type": "transaction_denied",
  "reason": "transfer_checks_failed", // 或 transfer_checks_expired
  "transfer_id": "uuid",
  "guild_id": 123456789,
  "initiator_id": 111111111,
  "target_id": 222222222,
  "amount": 1000
}
```

## 配置

### 環境變數

```bash
# 啟用轉帳事件池模式（預設：false）
TRANSFER_EVENT_POOL_ENABLED=true
```

### 預設設定

- 預設過期時間：24 小時（可透過 `expires_hours` 參數調整）
- 每日轉帳上限：500 點（與同步模式相同）
- 冷卻時間：300 秒（與同步模式相同）

## 使用範例

### 基本使用

```python
from src.bot.services.transfer_service import TransferService

service = TransferService(pool, event_pool_enabled=True)

# 建立待處理轉帳
transfer_id = await service.transfer_currency(
    guild_id=guild_id,
    initiator_id=initiator_id,
    target_id=target_id,
    amount=100,
    reason="payment",
)

# 查詢轉帳狀態
status = await service.get_transfer_status(transfer_id=transfer_id)
print(f"Status: {status.status}")
print(f"Checks: {status.checks}")
```

### 查詢待處理轉帳列表

```python
from src.db.gateway.economy_pending_transfers import PendingTransferGateway

gateway = PendingTransferGateway()
transfers = await gateway.list_pending_transfers(
    connection=conn,
    guild_id=guild_id,
    status="checking",  # 可選：pending, checking, approved, completed, rejected
    limit=100,
    offset=0,
)
```

## 資料庫結構

### pending_transfers 表

| 欄位 | 類型 | 說明 |
|------|------|------|
| transfer_id | uuid | 主鍵 |
| guild_id | bigint | 伺服器 ID |
| initiator_id | bigint | 發起者 ID |
| target_id | bigint | 接收者 ID |
| amount | bigint | 轉帳金額 |
| status | varchar(20) | 狀態：pending, checking, approved, completed, rejected |
| checks | jsonb | 檢查結果：{"balance": 1, "cooldown": 1, "daily_limit": 1} |
| retry_count | integer | 重試次數 |
| expires_at | timestamptz | 過期時間 |
| metadata | jsonb | 元資料 |
| created_at | timestamptz | 建立時間 |
| updated_at | timestamptz | 更新時間 |

### 索引

- `(guild_id, status)`：快速查詢特定伺服器的待處理轉帳
- `(expires_at)`：過期清理查詢
- `(status, updated_at)`：狀態與時間排序

## 與同步模式的比較

| 特性 | 同步模式 | 事件池模式 |
|------|---------|-----------|
| 執行方式 | 立即執行 | 異步執行 |
| 重試 | 需手動重試 | 自動重試 |
| 返回值 | TransferResult | UUID (transfer_id) |
| 適用場景 | 即時轉帳 | 允許延遲的轉帳 |
| 錯誤處理 | 立即拋出異常 | 自動重試或標記為 rejected |

## 注意事項

1. **向後相容**：預設為 `false`，不影響現有同步模式
2. **政府帳戶豁免**：政府帳戶不受冷卻與每日上限限制（與同步模式一致）
3. **事務保證**：轉帳執行仍在事務中，確保一致性
4. **事件順序**：檢查結果事件可能以任意順序到達，協調器會追蹤所有檢查狀態

## 遷移說明

執行資料庫遷移以啟用事件池功能：

```bash
alembic upgrade head
```

遷移腳本：`022_economy_pending_transfers.py`

## 故障排除

### 轉帳一直處於 checking 狀態

- 檢查 `TelemetryListener` 是否正常運行
- 檢查 `TransferEventPoolCoordinator` 是否已啟動
- 檢查 PostgreSQL NOTIFY/LISTEN 連線是否正常

### 轉帳一直重試

- 檢查檢查結果是否正確（`checks` JSONB）
- 檢查重試次數是否超過上限（10 次）
- 檢查餘額、冷卻時間、每日上限是否滿足條件

### 事件未觸發

- 確認環境變數 `TRANSFER_EVENT_POOL_ENABLED=true`
- 檢查 `TelemetryListener` 的 `channel` 設定是否為 `economy_events`
- 檢查資料庫函式是否正確發送 NOTIFY 事件
