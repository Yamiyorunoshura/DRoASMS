# state-council-panel Specification

## Purpose
定義國務院面板的 Discord 互動規格。此面板以 ephemeral 訊息承載，提供國務院領袖和授權人員在單一入口完成所有部門管理操作，包含領袖設定、部門權限配置、福利發放、稅收管理、身分管理和貨幣政策。面板採分頁設計，依部門區分功能，並實現權限控制。

## ADDED Requirements
### Requirement: State Council Panel Entry
系統必須（MUST）提供 `/state_council panel` 指令，允許國務院領袖和授權人員開啟國務院面板，以 ephemeral 訊息承載互動元件。

#### Scenario: 領袖開啟面板成功
- WHEN 國務院領袖在已完成設定的 guild 中執行 `/state_council panel`
- THEN 回覆一則 ephemeral 訊息並附上完整的國務院面板

#### Scenario: 部門授權人員開啟面板
- WHEN 具備部門權限的人員執行 `/state_council panel`
- THEN 回覆面板但僅顯示授權部門的功能頁籤

#### Scenario: 未設定被拒
- WHEN 國務院尚未完成領袖設定
- THEN 系統拒絕並提示執行 `/state_council config_leader`

### Requirement: Multi-Department Tab Interface
面板必須（MUST）採用分頁設計，第一頁為總覽，後續頁面為各部門專用功能。每個頁籤必須（MUST）根據使用者權限動態顯示或隱藏。

#### Scenario: 總覽頁面顯示
- WHEN 使用者開啟面板
- THEN 第一頁顯示國務院摘要、各部門帳戶餘額和快速狀態

#### Scenario: 部門頁籤權限控制
- WHEN 系統檢查使用者權限
- THEN 僅顯示具備權限的部門頁籤

### Requirement: Leader Configuration Modal
面板必須（MUST）提供國務院領袖設定功能，允許管理者指定領袖並初始化相關政府帳戶。

#### Scenario: 設定國務院領袖
- GIVEN 管理員在面板中點擊設定領袖
- AND 選擇有效的使用者作為領袖
- THEN 系統建立領袖配置和所有部門帳戶

### Requirement: Department Role Permission Setting
面板必須（MUST）允許國務院領袖設定各部門所需的身分組，以實現細粒度的權限控制。

#### Scenario: 配置部門權限
- GIVEN 國務院領袖在總覽頁面選擇權限設定
- WHEN 為每個部門選擇對應的身分組
- THEN 系統保存權限配置並更新面板存取控制

### Requirement: Interior Affairs Tab - Welfare Management
內政部頁籤必須（MUST）提供福利發放設定功能，包括金額設定、週期選擇和發放狀態監控。

#### Scenario: 設定定期福利
- GIVEN 具備內政部權限的使用者在內政部頁籤
- WHEN 設定福利金額和發放週期
- THEN 系統更新配置並開始定期發排程

#### Scenario: 查看福利發放記錄
- GIVEN 內政部頁籤開啟
- THEN 顯示最近的福利發放記錄和統計資訊

### Requirement: Finance Ministry Tab - Tax Management
財政部頁籤必須（MUST）提供所得稅設定功能，包括稅率設定、計算週期選擇和稅收統計。

#### Scenario: 設定所得稅參數
- GIVEN 具備財政部權限的使用者在財政部頁籤
- WHEN 設定稅率和計算週期
- THEN 系統更新稅收配置

#### Scenario: 查看稅收統計
- GIVEN 財政部頁籤開啟
- THEN 顯示稅收統計、最近徵收記錄和預計下次徵收時間

### Requirement: Homeland Security Tab - Citizenship Management
國土安全部頁籤必須（MUST）提供身分管理功能，包括公民身分移除、疑犯身分標記和身分記錄查詢。

#### Scenario: 移除公民身分
- GIVEN 具備國土安全部權限的使用者在國土安全部頁籤
- WHEN 選擇目標使用者並執行移除操作
- THEN 系統移除公民身分並掛上疑犯標記

#### Scenario: 查看身分管理記錄
- GIVEN 國土安全部頁籤開啟
- THEN 顯示最近的身分變更記錄和統計

### Requirement: Central Bank Tab - Monetary Policy
中央銀行頁籤必須（MUST）提供貨幣政策功能，包括貨幣增發、貨幣供給量監控和相關統計。

#### Scenario: 執行貨幣增發
- GIVEN 具備中央銀行權限的使用者在中央銀行頁籤
- WHEN 輸入增發金額並確認操作
- THEN 系統增加貨幣供給並更新帳戶餘額

#### Scenario: 查看貨幣統計
- GIVEN 中央銀行頁籤開啟
- THEN 顯示貨幣供給量、增發記錄和經濟指標

### Requirement: Account Transfer Between Departments
面板必須（MUST）提供部門間轉帳功能，允許授權人員在部門政府帳戶間移動資金。

#### Scenario: 部門間轉帳
- GIVEN 具備轉帳權限的使用者
- WHEN 在面板中選擇轉出部門、轉入部門和金額
- THEN 系統驗證權限並執行轉帳交易

### Requirement: Real-time Panel Updates
國務院面板在開啟期間必須（MUST）自動反映與本 guild 相關的國務院事件，包括權限變更、福利發放、稅收徵收、身分變更和帳戶變動。

#### Scenario: 福利發放後面板更新
- WHEN 系統執行定期福利發放
- THEN 內政部頁籤的統計資料在數秒內更新

#### Scenario: 權限變更後頁籤顯示更新
- WHEN 國務院領袖更新部門權限設定
- THEN 相關使用者的面板頁籤顯示即時更新

### Requirement: Export and Audit Functions
面板必須（MUST）提供稽核匯出功能，允許具備權限的人員匯出國務院操作記錄和統計資料。

#### Scenario: 匯出操作記錄
- GIVEN 具備稽核權限的使用者
- WHEN 在面板中選擇匯出期間和格式
- THEN 系統產生並下載對應的記錄檔案

### Requirement: Panel Permission Validation
面板各項操作必須（MUST）嚴格遵守權限控制，非授權人員不得看到或執行相關功能。

#### Scenario: 非授權功能隱藏
- WHEN 使用者不具備某部門權限
- THEN 該部門頁籤完全不顯示

#### Scenario: 操作權限二次驗證
- GIVEN 使用者嘗試執行敏感操作
- WHEN 系統再次驗證使用者權限
- THEN 只有具備權限才能繼續操作
