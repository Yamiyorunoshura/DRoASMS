# Proposal: 升級常任理事會面板（Council Panel）

## Summary
將「常任理事會」除設定指令（config）外的相關能力整合進 Discord 面板，提供理事以單一面板即可：建立/瀏覽提案、就地投票、（限提案人）撤案、（限管理者）匯出。維持既有 DM 通知流程，但互動改以面板為第一入口。

## Why
- 目前僅有 DM 投票按鈕（VotingView）與 Slash 指令分散操作，對理事不夠直覺。
- 需求：理事「在面板完成所有操作」，僅排除「/council config_role」設定指令。
- 風險控制：不動資料庫與核心商業規則，僅擴充互動層（Discord UI）。

## What Changes
- 新增 Slash：`/council panel`（僅理事可用），回覆 ephemeral 面板。
- 面板功能：
  - 建立提案（Modal 輸入：受款人、金額、用途、附件連結）
  - 檢視進行中提案清單與狀態、選擇後顯示投票按鈕
  - 提案人可從面板撤案（僅無任何投票前）
  - 管理者可從面板觸發匯出（保留原 slash，面板僅作入口）
- 治理規格調整：將「DM-Only」修改為「Panel + DM（通知/補救）」
- 啟動時持續註冊持久化投票按鈕（沿用現有 VotingView 機制）；面板本身為 ephemeral，不持久化。

## Impact
- 非破壞性：不更動 DB schema 與狀態字典。
- 權限與風險：
  - 面板僅理事可開啟；匯出需管理員或 `manage_guild`。
  - 保持既有門檻/逾時/提前否決邏輯不變。
- 可觀測性：新增面板互動事件日誌鍵（`event: council.panel.*`）。

## Non-Goals
- 不新增網頁後台/控制台。
- 不變更門檻計算、名冊快照、匿名→揭露規則。
- 不調整 `/council config_role` 行為與權限。

## Acceptance (High-level)
- 理事可在伺服器中執行 `/council panel`，看見面板，並能：
  - 以 Modal 建案成功，理事收到投票入口（DM 或面板內投票）。
  - 於面板選擇任一進行中提案並完成投票。
  - 提案人可於無票前從面板撤案；有票後系統拒絕並提示原因。
  - 管理員可自面板匯出指定期間資料（JSON/CSV）。

## Risks / Notes
- Ephemeral 面板不可標記 persistent；必須確保投票按鈕仍以 persistent VotingView 存活。
- 受款人輸入 UX：優先提供使用者選擇元件（或以 Mention/User picker）；若受限則接受 ID/mention。
- 大量提案列舉需分頁或 Select 分流；MVP 先限制顯示最近 N 筆進行中提案。
