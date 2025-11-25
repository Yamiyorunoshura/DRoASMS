# personal-panel Specification

## Purpose

提供一般成員的個人經濟管理介面，整合餘額查詢、交易歷史和轉帳功能於單一面板中。

## ADDED Requirements

### Requirement: Personal Panel Entry Command

系統必須（MUST）提供 `/personal_panel` 斜線指令，允許任何成員開啟個人面板。面板以 ephemeral 訊息承載互動元件。指令描述必須（MUST）以中文顯示。

#### Scenario: 成員開啟個人面板成功

- **WHEN** 任何成員執行 `/personal_panel`
- **THEN** 系統回覆一則 ephemeral 訊息，附上個人面板
- **AND** 面板首頁顯示該成員的用戶名稱和當前餘額

#### Scenario: 餘額顯示使用配置的貨幣名稱和圖示

- **GIVEN** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **WHEN** 成員開啟個人面板
- **THEN** 餘額顯示為「1000 金幣 🪙」而非「1000 點」

#### Scenario: 未設定貨幣配置時使用預設值

- **GIVEN** 該 guild 未設定貨幣配置
- **WHEN** 成員開啟個人面板
- **THEN** 餘額顯示使用預設值「點」作為貨幣名稱

### Requirement: Personal Panel Tab Navigation

個人面板必須（MUST）採用分頁設計，包含「首頁」、「財產」和「轉帳」三個分頁，使用按鈕切換。

#### Scenario: 預設顯示首頁

- **WHEN** 成員開啟個人面板
- **THEN** 預設顯示「首頁」分頁

#### Scenario: 切換到財產分頁

- **WHEN** 成員點擊「財產」按鈕
- **THEN** 面板切換顯示財產分頁內容

#### Scenario: 切換到轉帳分頁

- **WHEN** 成員點擊「轉帳」按鈕
- **THEN** 面板切換顯示轉帳分頁內容

### Requirement: Personal Panel Home Tab

首頁分頁必須（MUST）顯示成員的基本資訊和當前餘額。

#### Scenario: 首頁顯示用戶資訊

- **WHEN** 成員查看首頁分頁
- **THEN** 顯示成員的 Discord 顯示名稱
- **AND** 顯示成員的當前餘額

#### Scenario: 首頁提供快速操作按鈕

- **WHEN** 成員查看首頁分頁
- **THEN** 顯示「快速轉帳」按鈕，點擊後切換到轉帳分頁
- **AND** 顯示「查看歷史」按鈕，點擊後切換到財產分頁

### Requirement: Personal Panel Property Tab

財產分頁必須（MUST）顯示成員的交易歷史記錄，使用分頁顯示。

#### Scenario: 財產分頁顯示交易歷史

- **WHEN** 成員查看財產分頁
- **THEN** 顯示該成員的交易歷史記錄
- **AND** 每頁顯示最多 10 筆記錄
- **AND** 提供上一頁/下一頁導航按鈕

#### Scenario: 交易歷史顯示詳細資訊

- **GIVEN** 財產分頁已載入
- **THEN** 每筆交易記錄顯示：交易類型、金額、對象、時間、備註

#### Scenario: 交易金額使用配置的貨幣名稱和圖示

- **GIVEN** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **WHEN** 成員查看財產分頁
- **THEN** 交易金額顯示為「+100 金幣 🪙」或「-50 金幣 🪙」

#### Scenario: 無交易記錄時的提示

- **GIVEN** 成員沒有任何交易記錄
- **WHEN** 成員查看財產分頁
- **THEN** 顯示「目前沒有交易記錄」提示訊息

### Requirement: Personal Panel Transfer Tab

轉帳分頁必須（MUST）提供轉帳功能，支援轉帳給使用者或政府部門。

#### Scenario: 轉帳分頁顯示兩個轉帳選項

- **WHEN** 成員查看轉帳分頁
- **THEN** 顯示「轉帳給使用者」按鈕
- **AND** 顯示「轉帳給政府部門」按鈕

#### Scenario: 轉帳分頁顯示當前餘額

- **WHEN** 成員查看轉帳分頁
- **THEN** 頁面頂部顯示成員的當前餘額

### Requirement: Transfer To User From Personal Panel

個人面板必須（MUST）提供「轉帳給使用者」功能，使用下拉式選單選擇收款人。

#### Scenario: 點擊轉帳給使用者按鈕

- **WHEN** 成員在轉帳分頁點擊「轉帳給使用者」按鈕
- **THEN** 系統顯示使用者選擇下拉選單（UserSelect）

#### Scenario: 選擇收款使用者後彈出 Modal

- **GIVEN** 成員已點擊「轉帳給使用者」按鈕
- **WHEN** 成員從下拉選單選擇一位使用者
- **THEN** 系統彈出轉帳 Modal
- **AND** Modal 包含金額輸入欄位（必填）
- **AND** Modal 包含備註輸入欄位（選填）

#### Scenario: 轉帳給使用者成功

- **GIVEN** 成員已選擇收款人並填寫金額
- **AND** 成員餘額足夠
- **WHEN** 成員確認轉帳
- **THEN** 系統執行轉帳操作
- **AND** 顯示成功訊息，包含轉帳金額、收款人和新餘額
- **AND** 成功訊息使用配置的貨幣名稱和圖示

#### Scenario: 轉帳給使用者失敗 - 餘額不足

- **GIVEN** 成員已選擇收款人並填寫金額
- **AND** 成員餘額不足
- **WHEN** 成員確認轉帳
- **THEN** 系統拒絕轉帳並顯示「餘額不足」錯誤訊息

#### Scenario: 轉帳給自己被拒

- **GIVEN** 成員嘗試轉帳給自己
- **WHEN** 成員確認轉帳
- **THEN** 系統拒絕並提示「無法轉帳給自己」

### Requirement: Transfer To Government Department From Personal Panel

個人面板必須（MUST）提供「轉帳給政府部門」功能，使用下拉式選單選擇收款部門。

#### Scenario: 點擊轉帳給政府部門按鈕

- **WHEN** 成員在轉帳分頁點擊「轉帳給政府部門」按鈕
- **THEN** 系統顯示政府部門選擇下拉選單（StringSelect）
- **AND** 下拉選單包含所有已設定的政府部門

#### Scenario: 政府部門選項來源

- **GIVEN** 該 guild 已設定國務院，包含內政部、財政部、國土安全部、中央銀行、法務部
- **WHEN** 成員點擊「轉帳給政府部門」按鈕
- **THEN** 下拉選單顯示所有五個部門作為選項

#### Scenario: 未設定國務院時的提示

- **GIVEN** 該 guild 尚未設定國務院
- **WHEN** 成員點擊「轉帳給政府部門」按鈕
- **THEN** 系統顯示提示訊息「該伺服器尚未設定政府部門」

#### Scenario: 選擇政府部門後彈出 Modal

- **GIVEN** 成員已點擊「轉帳給政府部門」按鈕
- **WHEN** 成員從下拉選單選擇一個部門
- **THEN** 系統彈出轉帳 Modal
- **AND** Modal 包含金額輸入欄位（必填）
- **AND** Modal 包含備註輸入欄位（選填）

#### Scenario: 轉帳給政府部門成功

- **GIVEN** 成員已選擇收款部門並填寫金額
- **AND** 成員餘額足夠
- **WHEN** 成員確認轉帳
- **THEN** 系統執行轉帳操作，目標為該部門的政府帳戶
- **AND** 顯示成功訊息，包含轉帳金額、收款部門和新餘額
- **AND** 成功訊息使用配置的貨幣名稱和圖示

#### Scenario: 轉帳給政府部門失敗 - 餘額不足

- **GIVEN** 成員已選擇收款部門並填寫金額
- **AND** 成員餘額不足
- **WHEN** 成員確認轉帳
- **THEN** 系統拒絕轉帳並顯示「餘額不足」錯誤訊息

### Requirement: Personal Panel Transfer Validation

個人面板的轉帳功能必須（MUST）遵循現有的轉帳驗證規則。

#### Scenario: 轉帳金額驗證

- **GIVEN** 成員嘗試轉帳
- **WHEN** 金額為 0 或負數
- **THEN** 系統拒絕並提示「轉帳金額必須為正整數」

#### Scenario: 轉帳冷卻檢查

- **GIVEN** 成員在冷卻期間嘗試轉帳
- **WHEN** 系統檢查冷卻狀態
- **THEN** 系統拒絕並提示剩餘冷卻時間

#### Scenario: 每日轉帳限額檢查

- **GIVEN** 成員已達每日轉帳限額
- **WHEN** 系統檢查限額
- **THEN** 系統拒絕並提示「已達每日轉帳上限」

### Requirement: Personal Panel Real-time Balance Update

個人面板在轉帳操作後必須（MUST）即時更新顯示的餘額。

#### Scenario: 轉帳後餘額即時更新

- **GIVEN** 成員在個人面板執行轉帳
- **WHEN** 轉帳成功完成
- **THEN** 面板上顯示的餘額即時更新為新餘額
- **AND** 無需重新開啟面板

### Requirement: Personal Panel Timeout Handling

個人面板必須（MUST）在閒置超時後正確處理元件狀態。

#### Scenario: 面板超時後禁用元件

- **GIVEN** 個人面板已開啟
- **WHEN** 面板閒置超過 10 分鐘
- **THEN** 所有按鈕和下拉選單變為禁用狀態
- **AND** 顯示「面板已過期，請重新開啟」提示

### Requirement: Personal Panel Command Localization

`/personal_panel` 指令的描述必須（MUST）以中文顯示。

#### Scenario: 指令描述為中文

- **WHEN** 使用者在 Discord 中查看 `/personal_panel` 指令
- **THEN** 指令的描述文字顯示為中文
