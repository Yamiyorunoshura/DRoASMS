## Why
部門經常需要以政府帳戶直接撥款給普通使用者（例如獎補助、專案經費核銷），但目前國務院面板僅支援「部門之間」轉帳與「內政部」福利發放，缺少通用「部門 → 使用者」的操作。這造成：
- 非內政部場景需繞行 CLI/後端或臨時調整，流程不一致
- 領導層（部門領導或國務院領袖）難以在單一面板完成撥款

## What Changes
- 在所有部門頁籤新增「轉帳給使用者」按鈕
- 點擊後彈出與「部門轉帳」同型的嵌入式面板（Panel View），可：
  - （總覽時）選擇來源部門；（部門頁）預設來源為當前部門
  - 設定受款人（可輸入 @提及 或 使用者ID）
  - 填寫金額與理由
  - 驗證後送出
- 權限：具該來源部門權限者或國務院領袖可執行；受款人可為任意使用者（包含執行者本人）

## Impact
- 規格：`state-council-panel` 新增一條 Requirement
- 程式：
  - UI：`StateCouncilPanelView` 新增按鈕與 `DepartmentUserTransferPanelView`
  - Service：新增 `transfer_department_to_user(...)`
  - Telemetry：沿用既有政府帳戶事件檢測，無需額外事件
- 風險：權限判定需嚴謹；金額/使用者輸入需做基本驗證

## Open Questions
- 受款人輸入是否需改為原生 UserSelect？（先以 Modal 文本輸入 ID/@提及，保留未來升級空間）
