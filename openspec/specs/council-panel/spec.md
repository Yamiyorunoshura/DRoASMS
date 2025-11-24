# council-panel Specification

## Purpose
定義 Discord 伺服器內「常任理事會面板」之互動規格。此面板以 ephemeral 訊息承載，提供理事在單一入口完成治理相關操作（建立提案、檢視進行中提案與票數、投票／撤案、匯出），並遵守權限與可稽核性要求。面板採「即時更新」與「View 結束即停止更新」的運作模式；互動以面板為主、DM 為輔，不在公開頻道廣播。
## Requirements
### Requirement: Council Panel Entry
系統必須（MUST）提供 `/council panel` 指令，允許常任理事和授權人員開啟常任理事會面板，以 ephemeral 訊息承載互動元件。

#### Scenario: 常任理事開啟面板成功
- **WHEN** 具備常任理事身分組的使用者在已完成設定的 guild 中執行 `/council panel`
- **THEN** 回覆一則 ephemeral 訊息並附上完整的常任理事會面板

#### Scenario: 常任理事身分組權限檢查
- **GIVEN** 系統已完成常任理事會配置
- **WHEN** 使用者執行 `/council panel`
- **THEN** 系統檢查使用者是否具備常任理事身分組
- **AND** 若具備身分組則允許開啟面板，否則拒絕並提示無權限

#### Scenario: 未設定被拒
- **WHEN** 常任理事會尚未完成設定
- **THEN** 系統拒絕並提示執行 `/council config`

### Requirement: Propose from Panel (Modal)
面板必須（MUST）提供「建立提案」操作，以互動式面板流程取得轉帳類型、收款人、金額（正整數）、用途描述與可選附件連結；成功後須建立提案與名冊快照並以 DM/面板投票入口通知理事。

#### Scenario: 面板建案成功（轉帳給使用者）
- GIVEN 理事在面板點擊「建立提案」
- AND 選擇「轉帳給使用者」
- AND 從下拉選單選擇使用者
- AND 輸入金額>0、用途描述與附件（可選）
- THEN 建立提案（target_id 為使用者 ID），鎖定名冊快照與門檻，回覆成功訊息
- AND 對全體理事投遞投票入口（DM，且提供面板內投票按鈕）

#### Scenario: 面板建案成功（轉帳給政府部門）
- GIVEN 理事在面板點擊「建立提案」
- AND 選擇「轉帳給政府部門」
- AND 從下拉選單選擇政府部門
- AND 輸入金額>0、用途描述與附件（可選）
- THEN 建立提案（target_department_id 為部門 ID），鎖定名冊快照與門檻，回覆成功訊息
- AND 對全體理事投遞投票入口（DM，且提供面板內投票按鈕）

#### Scenario: 轉帳類型選擇
- WHEN 理事在面板點擊「建立提案」
- THEN 顯示轉帳類型選擇面板，包含「轉帳給政府部門」與「轉帳給使用者」兩個選項

#### Scenario: 部門選擇下拉選單
- GIVEN 理事選擇「轉帳給政府部門」
- WHEN 系統載入可用部門列表
- THEN 顯示包含所有已配置政府部門的下拉選單，每個選項顯示部門名稱與可選表情符號

#### Scenario: 使用者選擇下拉選單
- GIVEN 理事選擇「轉帳給使用者」
- WHEN 系統載入使用者列表
- THEN 顯示使用者選擇器（使用 Discord User Select 元件或自訂下拉選單，限制顯示數量以符合 Discord 限制）

### Requirement: List Active Proposals
理事會面板 SHALL 使用 dpy-paginator 提供流暢的提案清單分頁功能，取代現有的手動限制 10 筆記錄的實作方式。

#### Scenario: 提案清單分頁導航
- **WHEN** 使用者在理事會面板中查看進行中提案清單時
- **THEN** 系統 SHALL 使用 dpy-paginator 顯示分頁的提案清單
- **AND** 提供上一頁/下一頁按鈕導航
- **AND** 提供頁數下拉選單快速跳轉功能

#### Scenario: 分頁與即時更新整合
- **WHEN** 提案狀態發生變化需要更新面板時
- **THEN** 分頁系統 SHALL 保持當前頁面狀態
- **AND** 自動更新頁面內容以反映最新的提案狀態
- **AND** 重新計算總頁數以反映新增或移除的提案

#### Scenario: 分頁狀態保持
- **WHEN** 使用者在不同頁面間導航後發生即時更新時
- **THEN** 系統 SHALL 盡可能保持使用者當前檢視的頁面
- **AND** 如果當前頁面不再存在，則自動導航到最接近的有效頁面

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

### Requirement: Council Summary (Balance and Members)
面板必須（MUST）在開啟時顯示「Council 帳戶餘額」與「理事名單」。餘額數據來自該 guild 的 Council 帳戶；理事名單以目前理事角色的成員為準，至少顯示總人數並列出前 N 名（N 可為 10，避免訊息過長）。

#### Scenario: 面板顯示餘額與理事名單
- **WHEN** 理事在已完成治理設定的 guild 中執行 `/council panel`
- **THEN** 面板上方摘要顯示「餘額：<數值>」與「理事（<人數>）：<前 N 名標記>」

### Requirement: Realtime Panel Updates
「常任理事會面板」在開啟期間必須（MUST）自動反映與本 guild 治理相關事件（建案、投票、撤案、狀態變更）。面板為 ephemeral，更新僅對開啟者可見，並於 View 結束（timeout/stop）後停止更新。

#### Scenario: 建案後面板自動出現新提案
- WHEN 理事在同一 guild 新建立一筆提案
- THEN 已開啟的面板下拉清單在數秒內出現該提案

#### Scenario: 投票後合計票數更新
- GIVEN 已開啟面板且顯示某進行中提案
- WHEN 任一理事對該提案投票或改票
- THEN 面板中該提案的狀態摘要/合計票數在數秒內更新

#### Scenario: 撤案或逾時/執行後移出清單
- WHEN 提案被撤案、逾時、已通過並執行或執行失敗
- THEN 面板清單移除該提案或更新為結案狀態摘要

#### Scenario: View 結束即停止更新
- WHEN 面板 View 因 timeout 或使用者關閉而結束
- THEN 不再接收或套用任何更新

### Requirement: Usage Guide Button
理事會面板必須（MUST）提供「使用指引」按鈕；點擊後以 ephemeral Embed 顯示操作說明（包含：建案流程、名冊快照與門檻、投票、撤案限制、匯出權限、即時更新與私密性）。

#### Scenario: 顯示使用指引
- **WHEN** 理事於面板點擊「使用指引」
- **THEN** 回覆一則 ephemeral Embed，內容包含面板可執行之主要操作與限制

### Requirement: Transfer Proposal Target Display
面板與提案顯示必須（MUST）正確顯示轉帳目標，當提案為轉帳給政府部門時顯示部門名稱，當為轉帳給使用者時顯示使用者標記或 ID。

#### Scenario: 顯示部門目標提案
- GIVEN 存在一筆轉帳給政府部門的提案
- WHEN 理事在面板中檢視該提案
- THEN 顯示目標為「<部門名稱>」而非使用者標記

#### Scenario: 顯示使用者目標提案
- GIVEN 存在一筆轉帳給使用者的提案
- WHEN 理事在面板中檢視該提案
- THEN 顯示目標為使用者標記或 ID

### Requirement: Transfer Proposal Creation Validation
建立轉帳提案時，系統必須（MUST）驗證轉帳類型與收款人的有效性，確保 `target_id` 與 `target_department_id` 至少有一個為有效值，且兩者不可同時為空。

#### Scenario: 驗證部門目標有效性
- GIVEN 理事選擇「轉帳給政府部門」
- WHEN 選擇的部門 ID 不存在或無效
- THEN 系統拒絕建立提案並提示錯誤

#### Scenario: 驗證使用者目標有效性
- GIVEN 理事選擇「轉帳給使用者」
- WHEN 選擇的使用者不存在或無效
- THEN 系統拒絕建立提案並提示錯誤

#### Scenario: 必須選擇轉帳類型
- GIVEN 理事在面板點擊「建立提案」
- WHEN 未選擇轉帳類型即嘗試提交
- THEN 系統提示必須先選擇轉帳類型

### Requirement: Council Group Command Description
系統必須（MUST）提供 `/council` 群組指令，其描述與所有子指令的描述必須（MUST）以中文顯示。

#### Scenario: 群組描述為中文
- **WHEN** 使用者在 Discord 中查看 `/council` 群組指令
- **THEN** 群組的描述文字顯示為中文
- **AND** 所有子指令（`config_role`、`panel`）的描述文字皆為中文

### Requirement: Council Config Role Command Description
系統必須（MUST）提供 `/council config_role` 指令，其描述與所有參數說明必須（MUST）以中文顯示。

#### Scenario: 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/council config_role` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數的描述文字皆為中文

### Requirement: Council Member Role Configuration
常任理事會系統必須（MUST）提供常任理事身分組設定功能，允許管理者指定哪些Discord身分組被視為常任理事。

#### Scenario: 設定常任理事身分組
- **GIVEN** 系統管理員在常任理事會配置中
- **WHEN** 設定常任理事身分組ID
- **THEN** 系統保存身分組配置並更新權限檢查邏輯

#### Scenario: 多個常任理事身分組支援
- **GIVEN** 系統需要支援多個常任理事身分組
- **WHEN** 管理員設定多個常任理事身分組
- **THEN** 系統允許所有具備任一常任理事身分組的使用者存取面板

### Requirement: Fine-grained Council Operations Permission
常任理事會面板必須（MUST）提供基於常任理事身分組的細粒度權限控制，確保只有具備常任理事身分組的使用者才能執行敏感操作。

#### Scenario: 提案創建權限檢查
- **GIVEN** 使用者試圖在常任理事會面板中創建提案
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能創建提案

#### Scenario: 投票權限檢查
- **GIVEN** 使用者試圖在常任理事會提案中投票
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能投票

#### Scenario: 提案管理權限檢查
- **GIVEN** 使用者試圖管理（取消、修改）常任理事會提案
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能管理提案

#### Scenario: 面板存取權限檢查
- **GIVEN** 使用者試圖開啟常任理事會面板
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能開啟面板並查看內容
