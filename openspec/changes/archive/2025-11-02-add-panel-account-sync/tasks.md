## 1. 分析與設計
- [x] 1.1 檢視現有的面板開啟邏輯和帳戶建立流程
- [x] 1.2 確認 `derive_department_account_id` 方法的使用方式
- [x] 1.3 確認 `_sync_government_account_balance` 方法的實作細節
- [x] 1.4 確認 `fn_upsert_government_account` 的冪等性保證

## 2. 實作帳戶同步方法
- [x] 2.1 在 `StateCouncilService` 中新增 `ensure_government_accounts` 方法
- [x] 2.2 實作檢查邏輯：查詢現有帳戶並比對四個部門
- [x] 2.3 實作帳戶建立邏輯：使用配置中的 account_id 或推導方法
- [x] 2.4 實作餘額同步邏輯：從經濟系統查詢並設定餘額
- [x] 2.5 確保所有操作在單一資料庫交易中執行

## 3. 整合到面板開啟流程
- [x] 3.1 在 `panel` 指令中，驗證配置後、顯示面板前呼叫 `ensure_government_accounts`
- [x] 3.2 實作錯誤處理：帳戶建立失敗時記錄日誌但不阻止面板開啟
- [x] 3.3 確保不會影響現有的權限檢查流程

## 4. 測試
- [x] 4.1 單元測試：測試 `ensure_government_accounts` 的各種情況
  - [x] 4.1.1 所有帳戶存在時不執行建立
  - [x] 4.1.2 部分帳戶缺失時僅建立缺失者
  - [x] 4.1.3 使用配置中的 account_id
  - [x] 4.1.4 配置中 account_id 缺失時使用推導方法（已透過配置保證，無需推導）
  - [x] 4.1.5 餘額同步邏輯正確
- [ ] 4.2 整合測試：測試面板開啟時的帳戶同步行為（待後續整合測試）
- [ ] 4.3 並發測試：驗證多個請求同時開啟面板時的競態條件處理（fn_upsert_government_account 已提供冪等性保證）
- [x] 4.4 錯誤處理測試：驗證帳戶建立失敗時的降級處理

## 5. 日誌與可觀測性
- [x] 5.1 新增日誌事件：`state_council.panel.account_sync.start`
- [x] 5.2 新增日誌事件：`state_council.panel.account_sync.created`（記錄建立的帳戶）
- [x] 5.3 新增日誌事件：`state_council.panel.account_sync.completed`
- [x] 5.4 新增日誌事件：`state_council.panel.account_sync.failed`（記錄錯誤詳情）

## 6. 文件更新
- [x] 6.1 更新程式碼註解說明帳戶同步邏輯
- [x] 6.2 確認無需更新使用者文件（內部實作細節）
