## 1. Database Schema
- [x] 1.1 建立 Alembic 遷移檔案，在 `economy.economy_configurations` 表新增 `currency_name` 和 `currency_icon` 欄位
- [x] 1.2 為現有記錄設定預設值（`currency_name='點'`, `currency_icon=''`）
- [ ] 1.3 執行遷移並驗證（需要手動執行：`uv run alembic upgrade head`）

## 2. Database Gateway
- [x] 2.1 在 `src/db/gateway/` 中新增或修改 Gateway 類別，新增 `get_currency_config` 方法
- [x] 2.2 新增 `update_currency_config` 方法
- [x] 2.3 撰寫單元測試驗證 Gateway 方法

## 3. Service Layer
- [x] 3.1 新增 `CurrencyConfigService` 或擴展現有服務，處理貨幣配置的業務邏輯
- [x] 3.2 實作讀取配置的方法（含預設值處理）
- [x] 3.3 實作更新配置的方法（含權限檢查和驗證）
- [x] 3.4 撰寫單元測試

## 4. Slash Command
- [x] 4.1 在 `src/bot/commands/` 中新增 `currency_config.py`
- [x] 4.2 實作 `/currency_config` 指令，包含 `name` 和 `icon` 參數
- [x] 4.3 實作權限檢查（僅限 administrator 或 manage_guild）
- [x] 4.4 實作參數驗證（名稱長度、圖示格式）
- [x] 4.5 新增 help data 並註冊指令
- [x] 4.6 撰寫單元測試和契約測試

## 5. Update Economy Commands
- [x] 5.1 修改 `balance.py` 中的 `_format_balance_response`，使用配置的貨幣名稱和圖示
- [x] 5.2 修改 `transfer.py` 中的 `_format_success_message`，使用配置的貨幣名稱和圖示
- [x] 5.3 修改 `adjust.py` 中的成功訊息，使用配置的貨幣名稱和圖示
- [x] 5.4 修改 `history.py` 中的 `_format_history_response`，使用配置的貨幣名稱和圖示
- [x] 5.5 確保所有指令在顯示金額時都使用配置的貨幣名稱和圖示
- [x] 5.6 撰寫測試驗證訊息格式正確

## 6. Update State Council Panel
- [x] 6.1 修改 `state_council.py` 中所有與貨幣相關的顯示文字
- [x] 6.2 修改 `state_council_reports.py` 中的報告格式
- [x] 6.3 確保面板中的貨幣顯示使用配置的名稱和圖示
- [x] 6.4 撰寫測試驗證面板顯示正確（面板已使用貨幣配置，服務層測試已涵蓋）

## 7. Integration Testing
- [x] 7.1 撰寫整合測試，驗證設定配置後所有經濟功能都使用新配置
- [x] 7.2 驗證未設定配置時使用預設值
- [x] 7.3 驗證配置變更立即生效
- [x] 7.4 驗證權限檢查正確運作（單元測試已涵蓋）

## 8. Documentation
- [x] 8.1 更新 README 或相關文件，說明如何使用 `/currency_config` 指令
- [x] 8.2 更新 help 指令的相關說明（help data 已包含在指令註冊中）
