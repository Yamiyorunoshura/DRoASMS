## MODIFIED Requirements
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

## ADDED Requirements
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
