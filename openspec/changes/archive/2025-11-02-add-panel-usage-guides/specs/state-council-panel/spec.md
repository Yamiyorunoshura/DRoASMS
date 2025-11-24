## ADDED Requirements
### Requirement: Usage Guide Button
國務院面板必須（MUST）提供「使用指引」按鈕；點擊後以 ephemeral Embed 顯示依目前頁面（總覽或各部門）而異之操作說明。

#### Scenario: 總覽顯示指引
- **GIVEN** 使用者位於「總覽」頁
- **WHEN** 點擊「使用指引」
- **THEN** 回覆 ephemeral Embed，說明導航、部門轉帳、匯出資料（限領袖）、設定部門領導等

#### Scenario: 部門頁顯示指引
- **GIVEN** 使用者位於任一部門頁（內政/財政/國土安全/中央銀行）
- **WHEN** 點擊「使用指引」
- **THEN** 回覆 ephemeral Embed，說明該部門之主要操作（如福利發放、稅款徵收、身分管理、貨幣發行）與限制
