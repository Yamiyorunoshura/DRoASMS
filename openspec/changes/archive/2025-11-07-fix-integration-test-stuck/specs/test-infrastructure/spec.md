## MODIFIED Requirements
### Requirement: 測試環境隔離
系統 SHALL 確保測試執行不影響應用容器的運行，測試資料與應用資料分離。整合測試 SHALL 使用獨立的資源（Docker Compose 專案名稱、資料庫連線）確保測試間隔離，避免資源衝突導致測試卡住。

#### Scenario: 測試資料隔離
- **WHEN** 測試執行完成
- **THEN** 測試建立的資料庫資料不影響應用資料庫
- **AND** 測試使用交易回滾或獨立資料庫確保隔離
- **AND** 測試使用的資料庫連線在測試結束時正確釋放

#### Scenario: 測試容器與應用容器分離
- **WHEN** 測試容器執行測試
- **THEN** 測試容器不影響應用容器的運行
- **AND** 測試容器可以獨立重建而不影響應用容器
- **AND** 整合測試使用獨立的 Docker Compose 專案名稱，避免容器和網路衝突

#### Scenario: 整合測試資源隔離
- **WHEN** 多個整合測試同時執行
- **THEN** 每個測試使用獨立的 Docker Compose 專案名稱（如 `droasms-test-{test_id}`）
- **AND** 每個測試的 Docker Compose 容器和網路在測試結束時正確清理
- **AND** 測試間不會因為資源衝突而卡住或失敗

#### Scenario: 非同步資源清理
- **WHEN** 整合測試使用非同步協調器（如 TransferEventPoolCoordinator）
- **THEN** 協調器在測試結束時（無論成功或失敗）正確停止
- **AND** 所有非同步任務在測試結束前完成或取消
- **AND** 測試不會因為協調器未停止而卡住

#### Scenario: 資料庫連線池管理
- **WHEN** 整合測試使用資料庫連線池
- **THEN** 測試結束時連線池正確關閉，所有連線正確釋放
- **AND** 測試使用的交易在測試結束時正確回滾
- **AND** 連線池不會因為連線未釋放而耗盡

## ADDED Requirements
### Requirement: 測試超時保護
系統 SHALL 為所有整合測試提供超時保護機制，防止測試無限等待導致測試套件卡住。

#### Scenario: Compose 測試超時保護
- **WHEN** 整合測試涉及 Docker Compose 操作（啟動、日誌追蹤）
- **THEN** 測試 MUST 使用 `@pytest.mark.timeout` 裝飾器設定超時（Compose 測試 180-300s）
- **AND** 超時時測試正確清理資源（容器、連線、協調器）
- **AND** 超時錯誤訊息清楚說明測試卡住的原因

#### Scenario: 資料庫測試超時保護
- **WHEN** 整合測試涉及資料庫操作
- **THEN** 測試 MUST 使用 `@pytest.mark.timeout` 裝飾器設定超時（資料庫測試 60s）
- **AND** 超時時資料庫連線正確釋放
- **AND** 超時時交易正確回滾

#### Scenario: 非同步操作超時保護
- **WHEN** 整合測試涉及非同步操作（協調器啟動/停止、事件等待）
- **THEN** 測試 MUST 設定合理的超時值
- **AND** 超時時非同步操作正確取消或停止
- **AND** 超時時資源正確清理

### Requirement: 測試資源清理保證
系統 SHALL 確保所有測試資源（Docker Compose 容器、資料庫連線、非同步協調器、子進程）在測試結束時正確清理，無論測試成功或失敗。

#### Scenario: Fixture 清理保證
- **WHEN** 測試使用 `db_pool` 或 `db_connection` fixture
- **THEN** fixture 的 `finally` 區塊 MUST 確保連線池關閉和連線釋放
- **AND** fixture 的 `finally` 區塊 MUST 確保交易回滾
- **AND** 即使測試失敗或異常，清理邏輯也會執行

#### Scenario: Docker Compose 清理保證
- **WHEN** 測試使用 Docker Compose 啟動容器
- **THEN** 測試的 `finally` 區塊 MUST 執行 `docker compose down` 清理容器
- **AND** 清理操作必須使用測試專用的專案名稱
- **AND** 即使測試失敗或超時，清理邏輯也會執行

#### Scenario: 非同步協調器清理保證
- **WHEN** 測試啟動非同步協調器（如 TransferEventPoolCoordinator）
- **THEN** 測試的 `finally` 區塊 MUST 調用協調器的 `stop()` 方法
- **AND** 協調器停止操作必須設定超時，防止無限等待
- **AND** 即使測試失敗或異常，清理邏輯也會執行

### Requirement: 測試診斷工具
系統 SHALL 提供診斷工具，協助識別和解決測試卡住問題。

#### Scenario: 資源監控輸出
- **WHEN** 整合測試失敗或超時
- **THEN** 測試輸出包含資源使用狀況（活躍的 Docker 容器、資料庫連線數、非同步任務數）
- **AND** 測試輸出包含清理操作的執行狀態
- **AND** 測試輸出包含可能的資源衝突提示

#### Scenario: 測試日誌收集
- **WHEN** 整合測試失敗或超時
- **THEN** 測試收集相關的 Docker Compose 日誌
- **AND** 測試收集資料庫連線池狀態
- **AND** 測試收集非同步協調器狀態
