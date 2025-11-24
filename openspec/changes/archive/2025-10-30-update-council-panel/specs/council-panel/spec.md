## ADDED Requirements

### Requirement: Council Panel Entry
系統必須（MUST）提供 `/council panel` 指令，於伺服器中由具理事身分之成員開啟「常任理事會面板」，以 ephemeral 訊息承載互動元件。

#### Scenario: 理事開啟面板成功
- WHEN 理事在已完成治理設定的 guild 中執行 `/council panel`
- THEN 回覆一則 ephemeral 訊息並附上面板操作區

#### Scenario: 非理事被拒
- WHEN 非理事嘗試執行 `/council panel`
- THEN 系統拒絕並提示僅限理事

#### Scenario: 未設定治理被拒
- WHEN 治理尚未完成（未設定理事角色）
- THEN 系統拒絕並提示執行 `/council config_role`

### Requirement: Propose from Panel (Modal)
面板必須（MUST）提供「建立提案」操作，以 Modal 取得受款人、金額（正整數）、用途描述與可選附件連結；成功後須建立提案與名冊快照並以 DM/面板投票入口通知理事。

#### Scenario: 面板建案成功
- GIVEN 理事在面板點擊「建立提案」
- AND 輸入有效受款人與金額>0
- THEN 建立提案，鎖定名冊快照與門檻，回覆成功訊息
- AND 對全體理事投遞投票入口（DM，且提供面板內投票按鈕）

### Requirement: List Active Proposals
面板必須（MUST）讓理事瀏覽該 guild 進行中提案清單（可限制最多 N=10 筆），每筆顯示目標、金額、截止時間與狀態摘要；選擇任一提案後應顯示投票按鈕與當前合計票數。

#### Scenario: 顯示清單與投票操作
- WHEN 理事於面板展開「進行中提案」
- THEN 顯示最近 N 筆進行中提案供選擇
- AND 選擇後出現「同意/反對/棄權」投票按鈕與合計票數

### Requirement: Cancel from Panel (Proposer Only, No Votes)
面板必須（MUST）允許提案人在尚無任何投票前撤案；一旦已有投票則必須（MUST）拒絕並提示原因。

#### Scenario: 面板撤案被拒（已有投票）
- GIVEN 任一提案已有投票紀錄
- WHEN 提案人於面板點擊「撤案」
- THEN 系統拒絕並提示「已有投票，無法撤案」

### Requirement: Admin Export from Panel (Optional)
面板應（SHOULD）提供匯出入口；且當互動者具管理員或 `manage_guild` 權限時，系統必須（MUST）顯示並允許自面板觸發匯出（JSON/CSV，期間可選），執行時沿用現有匯出邏輯。

#### Scenario: 管理者面板匯出成功
- WHEN 管理者自面板選擇期間與格式
- THEN 產出檔案並回覆 ephemeral 下載

### Requirement: Permissions & Visibility in Panel
面板各操作必須（MUST）遵守現有權限規則：非理事不可建案/投票；匯出僅管理者可用；config 指令不得（MUST NOT）出現在面板。

#### Scenario: 面板不包含設定
- WHEN 開啟面板
- THEN 不得出現任何治理設定（config）相關操作

### Requirement: Persistent Voting Buttons
面板提供之投票按鈕必須（MUST）以 persistent view 形式註冊，使機器人重啟後仍可對進行中提案投票；面板容器為 ephemeral 不持久化。

#### Scenario: 重啟後仍可投票
- GIVEN 機器人已重啟
- WHEN 理事於 DM 或面板票區點擊投票
- THEN 投票按鈕仍可用且記錄結果
