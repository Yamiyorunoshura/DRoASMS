## Why
為了將治理互動集中於「理事會面板」，需：
- 在面板中直接支援撤案（符合「無票前可撤」規則），避免提案人需再透過斜線指令操作。
- 顯示理事會帳戶餘額與理事名冊，讓理事一進面板即可掌握決策背景資訊。
- 移除與面板重複的斜線指令（撤案、建案、匯出），降低學習成本與維護負擔。

## What Changes
- council-panel：新增「Council Summary（餘額＋理事名單）」區塊（MUST）。
- council-panel：補齊「撤案」成功情境並以面板為唯一入口（MUST）。
- council-panel：將「Admin Export from Panel」由 SHOULD 調整為 MUST，提供日期區間與 JSON/CSV（MUST）。
- council-governance：移除「Admin Exports via Slash Commands」（REMOVED），以面板匯出取代。
- council-governance：新增「Slash Commands 去重」規範，禁止對面板已涵蓋之功能提供重複斜線指令（MUST）。

## Impact
- Affected specs: council-panel, council-governance
- Affected code:
  - `src/bot/commands/council.py`：移除 `/council cancel`、`/council propose_transfer`、`/council export`；擴充 `/council panel` 內嵌顯示餘額與理事名單，並保留 `/council panel`、`/council config_role`。
  - `src/bot/services/council_service.py`：補齊查詢 Council 帳戶餘額與名冊的便捷方法（可重用既有經濟查詢 gateway）。
  - 如需：前端面板 View 內新增 Summary 區塊與更新匯出流程。

---
依 OpenSpec 流程，先審批本提案，待批准後再行實作與測試。
