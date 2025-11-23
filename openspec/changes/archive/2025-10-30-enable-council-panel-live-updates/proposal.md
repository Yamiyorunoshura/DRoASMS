# Proposal: 啟用常任理事會面板即時更新

## Why
目前 `/council panel` 為一次性渲染的 ephemeral 面板；當提案建立、投票、撤案、或狀態變更時，需使用者手動重開面板才會看到最新內容，造成使用體驗中斷。

## What Changes
- 在 Bot 行程內新增極簡的 in-process 事件匯流排（council events）。
- CouncilService 在關鍵治理事件（建案、投票、撤案、狀態變更/逾時/執行）發佈事件。
- 面板 `CouncilPanelView` 在開啟當下訂閱同 guild 的事件；收到事件後自動刷新選單與摘要 Embed，直接 `message.edit` 更新（維持 ephemeral）。
- View timeout 或停止時自動退訂，避免洩漏與資源佔用。

## Impact
- 使用者在 5 秒內（實作為即時、最佳努力）看到更新，不需重開面板。
- 僅限單行程內即時性（MVP）—如需跨行程/多實例，再評估以 Postgres NOTIFY 或外部總線擴充。

## Non-Goals
- 不改變現有 DM 提醒/結果投遞策略。
- 不在公開頻道廣播更新。

## Acceptance (High-level)
- 在同一 guild 中建立/投票/撤案後，開啟中的面板能自動反映最新提案與合計票數狀態；View 結束後不再更新。
