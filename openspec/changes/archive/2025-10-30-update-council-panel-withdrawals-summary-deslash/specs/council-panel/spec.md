## ADDED Requirements
### Requirement: Council Summary (Balance and Members)
面板必須（MUST）在開啟時顯示「Council 帳戶餘額」與「理事名單」。餘額數據來自該 guild 的 Council 帳戶；理事名單以目前理事角色的成員為準，至少顯示總人數並列出前 N 名（N 可為 10，避免訊息過長）。

#### Scenario: 面板顯示餘額與理事名單
- **WHEN** 理事在已完成治理設定的 guild 中執行 `/council panel`
- **THEN** 面板上方摘要顯示「餘額：<數值>」與「理事（<人數>）：<前 N 名標記>」

## MODIFIED Requirements
### Requirement: Cancel from Panel (Proposer Only, No Votes)
面板必須（MUST）允許提案人在尚無任何投票前撤案；一旦已有投票則必須（MUST）拒絕並提示原因。

#### Scenario: 撤案成功（尚無投票）
- **GIVEN** 該提案尚未產生任何投票
- **WHEN** 提案人於面板點擊「撤案」
- **THEN** 系統回覆「已撤案」並更新狀態為「已撤案」

#### Scenario: 面板撤案被拒（已有投票）
- **GIVEN** 任一提案已有投票紀錄
- **WHEN** 提案人於面板點擊「撤案」
- **THEN** 系統拒絕並提示「已有投票，無法撤案」

### Requirement: Admin Export from Panel (Optional)
面板必須（MUST）提供匯出入口；且當互動者具管理員或 `manage_guild` 權限時，系統必須（MUST）顯示並允許自面板觸發匯出（JSON/CSV，期間可選），執行時沿用現有匯出邏輯。

#### Scenario: 管理者面板匯出成功
- **WHEN** 管理者自面板選擇期間與格式
- **THEN** 產出檔案並回覆 ephemeral 下載
