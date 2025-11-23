## Why
目前理事會轉帳提案功能使用 Modal 文字輸入來指定受款人，操作體驗不夠直觀。同時，政府部門的識別方式在代碼中散落且硬編碼，不利於未來擴展。我們需要：
1. 改善理事會轉帳提案的使用者體驗，提供類似國務院面板的互動式選擇介面
2. 建立統一的政府部門識別格式，支援未來新增部門而無需大幅修改代碼

## What Changes
- **理事會面板轉帳提案 UI 擴充**：將現有的 Modal 文字輸入改為互動式面板，包含：
  - 轉帳類型選擇（轉帳給政府部門 vs 轉帳給使用者）
  - 收款人下拉選單（根據類型動態載入政府部門或使用者列表）
  - 保留金額、用途描述與附件連結輸入（透過 Modal 或面板元件）
- **政府部門統一識別格式**：建立 JSON 格式的部門定義系統，包含：
  - 部門識別碼（ID）、顯示名稱、帳戶代碼等元資料
  - 支援從配置載入部門列表，無需硬編碼
  - 相容現有資料庫約束與帳戶 ID 推導邏輯

## Impact
- **Affected specs**: `council-panel`, `state-council-governance`
- **Affected code**:
  - `src/bot/commands/council.py` - 面板 UI 元件
  - `src/bot/services/council_service.py` - 提案建立邏輯
  - `src/bot/services/state_council_service.py` - 部門識別邏輯
  - `src/db/functions/governance/fn_council.sql` - 提案建立函式（可能需支援部門 ID）
  - 資料庫遷移 - 可能需要擴充 `proposals` 表以支援部門目標
