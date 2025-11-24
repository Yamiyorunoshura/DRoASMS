## ADDED Requirements
### Requirement: Database Gateway Layer Architecture
Gateway 層必須（MUST）統一使用 SQL 函式進行所有資料庫操作，不得（MUST NOT）直接查詢或操作資料表。所有業務邏輯必須（MUST）在資料庫層以 SQL 函式實作，Gateway 層僅負責呼叫 SQL 函式並將結果映射為型別安全物件。

#### Scenario: Gateway 使用 SQL 函式查詢資料
- **WHEN** Gateway 需要查詢政府帳戶列表
- **THEN** 必須呼叫 `fn_list_government_accounts` SQL 函式，而非直接查詢 `governance.government_accounts` 資料表

#### Scenario: Gateway 不直接操作資料表
- **WHEN** 檢查 Gateway 程式碼
- **THEN** 不得出現直接 `SELECT FROM`、`INSERT INTO`、`UPDATE` 或 `DELETE FROM` 資料表的 SQL 語句
- **AND** 所有資料庫操作必須透過 SQL 函式進行

#### Scenario: SQL 函式處理 ambiguous column
- **WHEN** SQL 函式使用 `RETURNS TABLE` 定義輸出欄位
- **THEN** 函式內的查詢必須使用表別名限定欄位名稱，避免與輸出參數名稱衝突
