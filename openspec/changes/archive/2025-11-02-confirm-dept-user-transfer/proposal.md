# 確認並優化部門轉帳給使用者功能

## Why
用戶請求為每一個政府部門的面板都添加轉帳給使用者的功能，並將來源帳戶自動設置為開啟面板的部門。經過代碼審查，發現此功能已經在系統中實現，但需要確認功能完全符合需求並確保用戶體驗的一致性。

## What Changes
- 確認 `DepartmentUserTransferPanelView` 的實現已符合需求
- 驗證來源部門自動設置邏輯（部門頁面自動設置，總覽頁面手動選擇）
- 確保總覽頁面和部門頁面的行為一致性
- 更新 spec 以明確記錄自動設置來源部門的行為差異

## Impact
- Affected specs: state-council-panel
- Affected code: `src/bot/commands/state_council.py:493-500`
