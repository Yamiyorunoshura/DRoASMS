## 1. 檢查與分析
- [x] 1.1 全面檢查所有 Gateway 檔案，找出所有直接操作資料表的程式碼
- [x] 1.2 檢查現有 SQL 函式，確認是否有對應的函式可替代直接查詢
- [x] 1.3 列出需要新增或修正的 SQL 函式清單

## 2. SQL 函式實作
- [x] 2.1 確認 `fn_list_government_accounts` 函式已正確修正 ambiguous column 問題
- [x] 2.2 如有其他缺失的 SQL 函式，撰寫並加入遷移檔案

## 3. Gateway 層重構
- [x] 3.1 修正 `StateCouncilGovernanceGateway.fetch_government_accounts` 改用 SQL 函式
- [x] 3.2 移除所有直接查詢資料表的程式碼
- [x] 3.3 確保所有 Gateway 方法統一使用 SQL 函式

## 4. 測試與驗證
- [x] 4.1 執行現有單元測試確保功能正常
- [x] 4.2 執行整合測試驗證資料庫操作正確性
- [x] 4.3 驗證所有 Gateway 方法不再有直接查詢

## 5. 文檔更新
- [x] 5.1 更新相關註解說明使用 SQL 函式的原因
- [x] 5.2 確保架構原則文件反映此變更
