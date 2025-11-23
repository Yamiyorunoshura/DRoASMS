1) 規格：為 `state-council-panel` 新增「Department → User Transfer」Requirement；含成功/權限/自轉自帳戶案例
2) Service：在 `StateCouncilService` 實作 `transfer_department_to_user`（含權限檢查、經濟轉帳、治理餘額更新）
3) UI：在 `StateCouncilPanelView`
   - 部門頁籤 `_add_department_actions` 加入 `轉帳給使用者` 按鈕與 callback
   - 新增 `DepartmentUserTransferPanelView`（來源部門選擇、受款人設定、金額/理由 Modal、送出）
4) 文件：使用指引在部門頁新增一行說明
5) 驗證：本地跑測試；手動用假資料驗證面板流程
