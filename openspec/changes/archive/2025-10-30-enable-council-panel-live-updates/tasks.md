## 1. Implementation
- [x] 建立 `src/infra/events/council_events.py`（事件型別、subscribe/unsubscribe/publish）。
- [x] 修改 `CouncilService`：在 create/cancel/vote/expire/execution 後 publish 事件（含 guild_id、proposal_id、type）。
- [x] 修改 `src/bot/commands/council.py`：
  - [x] `CouncilPanelView` 加入 `bind_message()`、`on_timeout()`、`stop()`、`_apply_live_update()` 與重用的摘要 Embed 產生器。
  - [x] `/council panel` 送出訊息後以 `interaction.original_response()` 綁定訊息並訂閱事件。
- [x] 基礎日誌：訂閱/退訂與錯誤防護。

## 2. Validation
- [x] 本地以假資料流程手動驗證：
  - [x] 開啟面板，建立提案 → 面板下拉出現新提案。
  - [x] 對該提案投票 → 面板內合計票數與狀態文字更新。
  - [x] 撤案或達門檻 → 面板選單移除或狀態更新。
- [x] `openspec validate enable-council-panel-live-updates --strict` 通過。
