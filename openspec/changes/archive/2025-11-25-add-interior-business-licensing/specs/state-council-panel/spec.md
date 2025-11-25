## ADDED Requirements

### Requirement: Interior Affairs Tab - Business License Management

內政部頁籤必須（MUST）提供商業許可管理功能，包括發放許可、查看許可列表和撤銷許可。

#### Scenario: 顯示商業許可管理區塊

- **GIVEN** 具備內政部權限的使用者在內政部頁籤
- **WHEN** 頁面載入時
- **THEN** 顯示「商業許可管理」區塊，包含「發放許可」和「查看許可」按鈕

#### Scenario: 發放許可按鈕觸發 Modal

- **GIVEN** 使用者在內政部頁籤的商業許可管理區塊
- **WHEN** 點擊「發放許可」按鈕
- **THEN** 系統顯示許可發放 Modal，包含目標用戶選擇、許可類型下拉選單和有效期設定

#### Scenario: 許可發放 Modal 提交成功

- **GIVEN** 使用者已填寫許可發放 Modal 的所有必填欄位
- **WHEN** 點擊確認按鈕
- **THEN** 系統驗證輸入資料並發放許可
- **AND** 顯示成功訊息並關閉 Modal

#### Scenario: 許可發放驗證失敗

- **GIVEN** 使用者提交許可發放 Modal
- **AND** 輸入資料不完整或無效
- **WHEN** 系統驗證輸入
- **THEN** 顯示錯誤訊息並保持 Modal 開啟

### Requirement: Business License List View

內政部頁籤必須（MUST）提供商業許可列表檢視功能，支援分頁顯示和狀態篩選。

#### Scenario: 查看許可列表

- **GIVEN** 具備內政部權限或國務院領袖身分的使用者
- **WHEN** 點擊「查看許可」按鈕
- **THEN** 系統顯示商業許可列表嵌入訊息
- **AND** 每頁顯示最多 10 筆記錄
- **AND** 提供上一頁/下一頁導航按鈕

#### Scenario: 許可列表顯示資訊

- **GIVEN** 許可列表已載入
- **THEN** 每筆記錄顯示：用戶名稱、許可類型、核發日期、到期日期、狀態徽章

#### Scenario: 空列表提示

- **GIVEN** 該 guild 尚無任何商業許可記錄
- **WHEN** 使用者查看許可列表
- **THEN** 顯示「目前沒有商業許可記錄」提示訊息

#### Scenario: 篩選許可狀態

- **GIVEN** 許可列表顯示中
- **WHEN** 使用者從狀態篩選下拉選單選擇「有效」「已過期」或「已撤銷」
- **THEN** 列表僅顯示符合該狀態的記錄

### Requirement: Business License Revocation UI

內政部頁籤必須（MUST）提供從許可列表撤銷許可的功能。

#### Scenario: 撤銷按鈕顯示

- **GIVEN** 許可列表中有狀態為「有效」的許可記錄
- **THEN** 該記錄旁顯示「撤銷」按鈕

#### Scenario: 撤銷確認 Modal

- **GIVEN** 使用者點擊許可記錄旁的「撤銷」按鈕
- **WHEN** 系統處理點擊事件
- **THEN** 顯示撤銷確認 Modal，包含撤銷原因輸入欄位

#### Scenario: 確認撤銷許可

- **GIVEN** 使用者已在撤銷確認 Modal 填寫撤銷原因
- **WHEN** 點擊確認按鈕
- **THEN** 系統執行撤銷操作
- **AND** 顯示成功訊息
- **AND** 更新列表顯示

#### Scenario: 取消撤銷操作

- **GIVEN** 撤銷確認 Modal 已開啟
- **WHEN** 使用者點擊取消按鈕
- **THEN** Modal 關閉且不執行任何操作

### Requirement: Business License Permission Validation

商業許可相關操作必須（MUST）嚴格驗證使用者權限，確保只有內政部領導人或國務院領袖能執行操作。

#### Scenario: 非授權人員無法看到商業許可管理

- **GIVEN** 使用者不具備內政部首長身分組且非國務院領袖
- **WHEN** 開啟國務院面板
- **THEN** 內政部頁籤不顯示，或頁籤中不顯示商業許可管理功能

#### Scenario: 發放操作權限二次驗證

- **GIVEN** 使用者嘗試提交許可發放請求
- **WHEN** 系統處理請求
- **THEN** 再次驗證使用者具備內政部權限後才執行發放

#### Scenario: 撤銷操作權限二次驗證

- **GIVEN** 使用者嘗試撤銷商業許可
- **WHEN** 系統處理請求
- **THEN** 再次驗證使用者具備內政部權限後才執行撤銷
