## 1. Implementation
- [x] 1.1 面板顯示 Summary：查詢並顯示「Council 帳戶餘額」與「理事名單（人數＋列出前 N 名）」
- [x] 1.2 面板撤案：確認提案人在無投票時可於面板成功撤案（既有 service 規則覆用）
- [x] 1.3 面板匯出：於面板提供日期區間與 JSON/CSV 的匯出操作（取代指引跳轉），含權限檢查
- [x] 1.4 移除重複斜線指令：刪除 `/council cancel`、`/council propose_transfer`、`/council export` 的註冊與對應 handler
- [x] 1.5 僅保留 `/council panel` 與 `/council config_role`（與專案其他設定指令），更新說明文字
- [x] 1.6 日誌與稽核：確保撤案與匯出行為均記錄於現有日誌

## 2. Validation
- [x] 2.1 `openspec validate update-council-panel-withdrawals-summary-deslash --strict` 通過
- [x] 2.2 啟動機器人後，理事可開啟面板並看到餘額與理事名單
- [x] 2.3 在無票情況，提案人於面板成功撤案；有票則明確被拒
- [x] 2.4 面板匯出可於具管理權限時成功產出 JSON/CSV；無權限則被拒
- [x] 2.5 指令清單中不存在 `/council cancel`、`/council propose_transfer`、`/council export`
- [x] 2.6 回歸測試：既有投票 persistent view 於重啟後仍可投票
