## Why
整合測試經常因為資源衝突、測試隔離不足、非同步資源清理不完整等問題而卡住（stuck），導致測試套件無法完成執行。這些問題包括：
- Docker Compose 容器在多個測試間共享，導致資源衝突
- 資料庫連線池耗盡，測試未正確清理連線
- 非同步協調器（如 TransferEventPoolCoordinator）未正確停止
- 測試間缺乏隔離，共享狀態導致不可預測行為
- Fixture 清理不完整，資源洩漏影響後續測試

## What Changes
- **新增測試隔離機制**：確保每個整合測試使用獨立的 Docker Compose 專案名稱或命名空間
- **強化資源清理**：確保所有非同步資源（連線池、協調器、子進程）在測試結束時正確清理
- **改進 Fixture 管理**：增強 `db_pool` 和 `db_connection` fixture 的清理邏輯，確保交易回滾和連線釋放
- **新增超時保護**：為所有整合測試添加合理的超時設定，防止無限等待
- **改進 Docker Compose 測試**：使用獨立的專案名稱或臨時目錄，避免多個測試同時執行時的衝突
- **新增資源監控**：在測試失敗時輸出資源使用狀況，協助診斷問題

## Impact
- Affected specs: `test-infrastructure`
- Affected code:
  - `tests/conftest.py` - Fixture 清理邏輯
  - `tests/integration/*.py` - 所有整合測試檔案
  - `tests/integration/test_compose_*.py` - Docker Compose 相關測試
  - `tests/integration/test_transfer_event_pool_flow.py` - 協調器清理
  - `tests/integration/test_state_council_flow.py` - Mock 資源清理
