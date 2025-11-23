## Why

現有的轉帳機制（`fn_transfer_currency`）採用同步執行模式，所有檢查（餘額、冷卻、每日上限）與轉帳操作在同一交易中完成。此設計雖然能確保一致性，但缺乏彈性的重試機制與異步處理能力。當檢查失敗時，使用者必須手動重試，無法自動處理暫時性失敗（如餘額暫時不足、冷卻期間未結束等）。

為提升使用者體驗並提供更靈活的錯誤處理策略，需要引入事件驅動的轉帳事件池架構，將檢查與執行分離，透過資料庫層的事件機制（NOTIFY/LISTEN）實現異步協調與自動重試。

## What Changes

- **新增 `economy.pending_transfers` 表**：記錄待處理轉帳請求，包含狀態追蹤（`pending` → `checking` → `approved` / `rejected`）、檢查結果（JSONB）、重試計數與過期時間
- **資料庫層觸發器機制**：插入 `pending_transfers` 時自動觸發檢查流程，各項檢查異步執行並透過 `pg_notify` 發送事件
- **擴展 `TelemetryListener`**：監聽轉帳檢查結果事件，追蹤每個轉帳請求的所有檢查狀態
- **Python 層協調邏輯**：當所有檢查通過時，自動呼叫 `fn_transfer_currency` 執行實際轉帳；處理重試與錯誤恢復
- **重試機制**：檢查失敗時使用指數退避策略重試，最多 10 次；超過上限或過期則標記為 `rejected`
- **過期清理機制**：定期清理過期記錄（透過 `pg_cron` 或 Python 層定時任務）

## Impact

- **Affected specs**: `economy-commands`, `database-gateway`
- **Affected code**:
  - 資料庫遷移：新增 `pending_transfers` 表、觸發器與檢查函式
  - `src/db/functions/`：新增檢查函式與觸發器 SQL
  - `src/infra/telemetry/listener.py`：擴展監聽檢查事件
  - `src/bot/services/transfer_service.py`：新增事件池協調邏輯
  - `src/db/gateway/`：新增 `pending_transfers` 相關 Gateway 方法
