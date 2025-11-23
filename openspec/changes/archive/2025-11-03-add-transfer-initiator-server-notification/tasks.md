## 1. 實作準備
- [x] 1.1 研究 Discord interaction followup API，確認如何在異步情況下發送 ephemeral notification
- [x] 1.2 評估是否需要保存 interaction token，或可使用其他機制（如 webhook）
- [x] 1.3 確認在 event pool 模式下如何追蹤原始 interaction

## 2. 實作通知機制
- [x] 2.1 在 `TelemetryListener` 中新增 `_notify_initiator_server()` 方法
- [x] 2.2 實作使用 interaction followup 發送 ephemeral notification 的邏輯
- [x] 2.3 處理無法取得 interaction 的情況（例如 token 過期、guild 不存在等）

## 3. 整合與測試
- [x] 3.1 更新 `TelemetryListener._default_handler()` 以在 `transaction_success` 時呼叫新方法
- [x] 3.2 撰寫單元測試驗證通知邏輯（tests/unit/test_telemetry_listener_notify_initiator.py）
- [x] 3.3 撰寫整合測試驗證轉帳成功時的通知流程（tests/integration/test_transfer_initiator_notification.py）
- [x] 3.4 測試同步模式與 event pool 模式下的通知行為（測試涵蓋兩種模式）

## 4. 文件與驗證
- [x] 4.1 更新相關文件說明新的通知機制（實作中包含註解說明）
- [x] 4.2 執行 `openspec validate add-transfer-initiator-server-notification --strict` 確認提案格式正確
