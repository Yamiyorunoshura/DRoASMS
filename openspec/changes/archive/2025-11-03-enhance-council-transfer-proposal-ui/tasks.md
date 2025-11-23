## 1. 建立部門定義格式
- [x] 1.1 建立 `src/config/departments.json`，定義所有政府部門的 JSON 格式
- [x] 1.2 實作 `src/bot/services/department_registry.py`，提供部門載入、查詢與快取功能
- [x] 1.3 更新 `StateCouncilService` 使用部門註冊表，保留字串名稱映射以保持相容
- [ ] 1.4 單元測試：驗證部門載入、查詢與 ID/名稱轉換

## 2. 擴充資料庫結構
- [x] 2.1 建立 Alembic 遷移，在 `governance.proposals` 表新增 `target_department_id` 欄位（TEXT, NULL）
- [x] 2.2 更新 `fn_create_proposal` SQL 函式，支援 `p_target_department_id` 參數
- [x] 2.3 更新 `CouncilGovernanceGateway.create_proposal` 以支援部門目標
- [x] 2.4 更新提案查詢與匯出邏輯，同時處理 `target_id` 與 `target_department_id`
- [x] 2.5 資料庫測試：驗證部門提案建立、查詢與匯出

## 3. 實作理事會面板轉帳 UI
- [x] 3.1 建立 `TransferTypeSelectionView`，提供「轉帳給政府部門」與「轉帳給使用者」按鈕
- [x] 3.2 建立 `DepartmentSelectView`，從部門註冊表載入可用部門並顯示下拉選單
- [x] 3.3 建立 `UserSelectView` 或使用 Discord User Select 元件（視 Discord.py 版本而定）
- [x] 3.4 建立 `TransferProposalModal`，整合金額、用途描述與附件連結輸入
- [x] 3.5 更新 `CouncilPanelView`，將「建立提案」按鈕改為觸發轉帳類型選擇面板
- [x] 3.6 更新 `CouncilService.create_transfer_proposal`，支援 `target_department_id` 參數
- [x] 3.7 單元測試：驗證面板互動流程與提案建立邏輯

## 4. 更新相關功能與顯示
- [x] 4.1 更新提案顯示邏輯，當 `target_department_id` 存在時顯示部門名稱而非使用者
- [x] 4.2 更新 DM 通知與投票入口，正確顯示部門目標提案
- [x] 4.3 更新匯出功能，支援部門目標提案的 CSV/JSON 輸出
- [x] 4.4 更新使用指引，說明新的轉帳提案流程

## 5. 整合測試與驗證
- [x] 5.1 整合測試：完整流程（選擇類型 → 選擇收款人 → 填寫資訊 → 建立提案 → 投票）
- [x] 5.2 契約測試：確保向後相容（舊提案仍可正常顯示與操作）
- [x] 5.3 性能測試：驗證部門載入與面板載入延遲
- [x] 5.4 文件更新：更新 README 與 CHANGELOG
