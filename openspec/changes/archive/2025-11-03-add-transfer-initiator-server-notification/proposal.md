## Why

目前轉帳成功時，系統會透過 DM 通知收款人，但轉帳人（發起人）僅在執行 `/transfer` 指令時看到 ephemeral 回應。在同步模式下，這已經足夠；但在事件池（event pool）模式下，轉帳可能是異步完成的，轉帳人無法即時得知轉帳是否成功執行。

為提升使用者體驗並確保轉帳人在轉帳成功時能收到明確的伺服器內通知，需要擴展現有通知機制，在轉帳成功時除了 DM 通知收款人外，也向轉帳人發送 ephemeral notification。

## What Changes

- **擴展轉帳成功通知機制**：當收到 `transaction_success` 事件時，除了 DM 通知收款人外，還需向轉帳人發送 ephemeral followup notification
- **TelemetryListener 增強**：新增邏輯以發送轉帳成功通知給轉帳人，使用 interaction followup 機制
- **Interaction Token 管理**：需要在轉帳請求中保存 interaction token，以便在異步完成時發送 followup

## Impact

- **Affected specs**: `economy-commands`
- **Affected code**:
  - `src/infra/telemetry/listener.py`：新增轉帳成功通知轉帳人的邏輯
  - `src/bot/commands/transfer.py`：可能需要保存 interaction token 以供後續使用
  - `src/bot/services/transfer_service.py`：可能需要傳遞 interaction 相關資訊
