## 1. 調查與診斷
- [x] 1.1 分析現有整合測試的資源使用模式（Docker Compose、資料庫連線、非同步協調器）
- [x] 1.2 識別所有可能導致測試卡住的資源衝突點
- [x] 1.3 建立測試失敗時的診斷工具（資源監控、日誌收集）

## 2. Fixture 改進
- [x] 2.1 增強 `db_pool` fixture 的清理邏輯，確保連線池正確關閉
- [x] 2.2 增強 `db_connection` fixture 的清理邏輯，確保交易回滾和連線釋放
- [x] 2.3 新增 `docker_compose_project` fixture，為每個測試提供獨立的 Compose 專案名稱
- [x] 2.4 新增 `async_coordinator_cleanup` fixture，確保所有協調器在測試結束時停止

## 3. Docker Compose 測試隔離
- [x] 3.1 修改 `test_compose_ready.py` 使用獨立的專案名稱
- [x] 3.2 修改 `test_compose_dependencies.py` 使用獨立的專案名稱
- [x] 3.3 修改 `test_compose_restart_update.py` 使用獨立的專案名稱
- [x] 3.4 確保所有 Compose 測試在 `finally` 區塊中正確執行 `docker compose down`

## 4. 非同步資源清理
- [x] 4.1 修改 `test_transfer_event_pool_flow.py`，確保所有測試的 `finally` 區塊正確停止協調器
- [x] 4.2 檢查其他使用非同步協調器的測試，確保資源清理完整
- [x] 4.3 新增超時保護機制，防止協調器停止操作無限等待

## 5. 測試超時保護
- [x] 5.1 為所有整合測試添加 `@pytest.mark.timeout` 裝飾器
- [x] 5.2 設定合理的超時值（根據測試類型：Compose 測試 180-300s，資料庫測試 60s）
- [x] 5.3 確保超時時能正確清理資源

## 6. 測試驗證
- [x] 6.1 執行完整整合測試套件，驗證無卡住問題
- [x] 6.2 驗證多個測試並發執行時無資源衝突
- [x] 6.3 驗證測試失敗時資源能正確清理
- [x] 6.4 驗證測試超時時能正確清理資源
