# Tasks: 升級常任理事會面板（Council Panel）

## 1. 指令與面板骨架
- [x] 1.1 新增 Slash 指令 `council panel`（`src/bot/commands/council.py`）
- [x] 1.2 權限檢查：僅理事可開啟；未設定治理時回覆指引
- [x] 1.3 回覆 ephemeral 面板容器訊息（`CouncilPanelView`）

## 2. 面板互動元件
- [x] 2.1 `ProposeTransferModal`：受款人、金額、描述、附件連結（驗證 >0 金額）
- [x] 2.2 建案後：沿用既有 `_dm_council_for_voting` 推送投票入口
- [x] 2.3 `ActiveProposalsSelect`：列出進行中提案（最多 N=10 筆；含簡述與截止）
- [x] 2.4 選擇提案後顯示投票按鈕（沿用/包裝 `VotingView`）
- [x] 2.5 `CancelProposalButton`：僅提案人可見；呼叫 `service.cancel_proposal`，失敗顯示原因
- [x] 2.6 `ExportButton`（可選）：需管理員/`manage_guild`；引導至現有 `/council export`

## 3. Service 與 Gateway 介面支援
- [x] 3.1 在 `CouncilService` 暴露 `list_active_proposals()`（呼叫 gateway 現有查詢）
- [x] 3.2 新增輔助 formatter：將提案摘要化（目標、金額、截止、ID 短碼）

## 4. 持久化與啟動註冊
- [x] 4.1 保持 `VotingView` 為 persistent；啟動時註冊（既有邏輯維持）
- [x] 4.2 面板（`CouncilPanelView`）使用 ephemeral，不註冊 persistent

## 5. 日誌與可觀測
- [x] 5.1 新增 `event: council.panel.open|propose|vote|cancel|export` 等結構化日誌

## 6. 測試與驗證
- [x] 6.1 單元測試：`CouncilService.list_active_proposals` 合約
- [x] 6.2 合約測試：建案→面板列出→投票→（條件）撤案流程（以 service 層模擬）
- [x] 6.3 文件：`README.md` 補充 `/council panel` 使用說明

## 7. 完成定義（DoD）
- [x] 面板可正常開啟；理事能從面板完成建案、投票、撤案
- [x] 管理者可從面板進入匯出（或收到引導）
- [x] `ruff`, `mypy`, `pytest` 通過；日誌鍵齊全
