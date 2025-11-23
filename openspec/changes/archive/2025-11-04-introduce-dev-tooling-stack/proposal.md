## Why

目前的專案在多個領域使用手動實作，增加開發難度與維護成本：
- 設定載入與驗證：使用 `os.getenv()` 搭配手動檢查，缺乏型別安全與自動驗證
- 重試邏輯：在 `entrypoint.sh` 與 `transfer_event_pool.py` 中手寫指數退避，程式碼重複且難以維護
- 測試資料生成：測試中手動建立假資料，耗時且容易產生重複程式碼
- 測試覆蓋率：缺乏自動化報告，無法評估測試品質
- 測試執行：測試套件較多時執行時間過長，影響開發效率
- 程式碼品質：缺乏提交前自動檢查，容易引入格式或型別錯誤

引入業界標準工具可降低開發難度、提升程式碼品質，並減少重複實作。

## What Changes

- **Pydantic**：重構設定載入（`BotSettings`、`PoolConfig`）為 Pydantic 模型，自動驗證環境變數與型別
- **pytest-cov**：新增測試覆蓋率報告，整合至 CI 與開發流程
- **Faker**：在測試中引入 Faker 自動生成假資料（中文/英文），減少手寫測試資料
- **Tenacity**：重構重試邏輯（資料庫連線、轉帳重試）使用 Tenacity 裝飾器
- **pytest-xdist**：支援並行執行測試，縮短測試時間
- **pre-commit**：新增 Git hooks 自動執行格式化、lint、型別檢查
- **Hypothesis**：在複雜邏輯測試中引入屬性測試，自動生成邊界案例
- **Typer + Rich**：為 CLI 工具預留架構（目前為選用）
- **watchfiles**：開發時自動重載支援（目前為選用）

## Impact

- **Affected specs**:
  - `database-gateway`：重試邏輯與設定管理
  - 新增 `development-tooling` spec：涵蓋測試工具與開發工具
- **Affected code**:
  - `src/bot/main.py`：`BotSettings` 重構為 Pydantic
  - `src/db/pool.py`：`PoolConfig` 重構為 Pydantic
  - `docker/bin/entrypoint.sh`：重試邏輯遷移至 Python（使用 Tenacity）
  - `src/bot/services/transfer_event_pool.py`：重試邏輯使用 Tenacity
  - `tests/conftest.py`：新增 Faker fixtures
  - `pyproject.toml`：新增依賴與設定
  - `.pre-commit-config.yaml`：新增 pre-commit 設定
  - CI 工作流程：整合覆蓋率報告與並行測試

## Breaking Changes

無。此變更為向後相容，僅改善內部實作與開發體驗。
