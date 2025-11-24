## MODIFIED Requirements

### Requirement: Result<T,E> 錯誤處理核心類型
系統 SHALL 實現單一、權威的 Rust 風格 `Result<T,E>` 類型，提供類型安全的錯誤處理機制，支援 `Ok(T)` 和 `Err(E)` 兩種變體。所有新程式碼 MUST 僅使用這一套 Result 型別與其伴隨的 `AsyncResult<T,E>`。

#### Scenario: 成功結果處理
- **WHEN** 操作成功完成時
- **THEN** 系統必須返回 `Result.Ok(value)` 包含成功的值
- **AND** `result.is_ok()` 必須返回 `True`
- **AND** `result.is_err()` 必須返回 `False`
- **AND** `result.unwrap()` 必須返回包裝的值

#### Scenario: 錯誤結果處理
- **WHEN** 操作失敗時
- **THEN** 系統必須返回 `Result.Err(error)` 包含錯誤資訊
- **AND** `result.is_err()` 必須返回 `True`
- **AND** `result.is_ok()` 必須返回 `False`
- **AND** `result.unwrap_err()` 必須返回包裝的錯誤

#### Scenario: 鏈式操作支援
- **WHEN** 對 Result 物件進行鏈式調用時
- **THEN** `result.map(function)` 必須在成功時應用函數並返回新 Result
- **AND** `result.and_then(function)` 必須支援單子式鏈式操作
- **AND** 錯誤情況下鏈式調用必須直接傳播錯誤

#### Scenario: 唯一實作來源
- **WHEN** 專案中的任一模組需要使用 `Result<T,E>` 或 `AsyncResult<T,E>` 型別
- **THEN** 該模組 MUST 從單一權威模組匯入這些型別（目前為 `src.infra.result` 命名空間）
- **AND** 專案內不得再定義額外的 `Ok` / `Err` / `Result` 類別作為平行實作
- **AND** 任何相容層（例如 legacy wrapper）只允許包裝此權威實作，不得引入新的語意或型別行為

### Requirement: 錯誤類型層次結構
系統 SHALL 建立單一、分層的錯誤類型系統，提供具體的錯誤分類和上下文資訊。所有新的 domain 錯誤型別 MUST 直接或間接繼承自權威的 `Error` 根型別。

#### Scenario: 資料庫錯誤處理
- **WHEN** 資料庫操作失敗時
- **THEN** 必須返回 `DatabaseError` 類型的錯誤（繼承自 `Error`）
- **AND** 錯誤必須包含查詢參數、資料表名稱與 SQLSTATE 等上下文
- **AND** 必須區分連線錯誤、約束違規、查詢錯誤等子類型
- **AND** 錯誤必須由統一的 mapping 函式產生（例如從 asyncpg 例外轉換），不可在不同模組各自實作不相容的 mapping

#### Scenario: Discord API 錯誤處理
- **WHEN** Discord API 調用失敗時
- **THEN** 必須返回 `DiscordError` 類型的錯誤（繼承自 `Error`）
- **AND** 錯誤必須包含 HTTP 狀態碼與 Discord API 錯誤碼
- **AND** 必須區分限流、認證、權限等錯誤類型
- **AND** 新增 Discord 相關錯誤型別時，不得再定義獨立的錯誤根類別

#### Scenario: 業務邏輯驗證錯誤
- **WHEN** 業務規則驗證失敗時
- **THEN** 必須返回 `ValidationError` 或特化的業務邏輯錯誤型別（皆繼承自 `Error`）
- **AND** 錯誤必須包含具體的驗證失敗欄位和值
- **AND** 必須支援多欄位驗證錯誤聚合
- **AND** 不得建立第二套平行的錯誤階層（例如另一個 `BaseError` 根型別）與權威階層並存

#### Scenario: 相容層邊界
- **WHEN** legacy 模組仍需與舊的 exception 型式 API 整合時
- **THEN** 可以透過明確標註的「相容層」將 exception 轉換為權威 `Error` 階層下的型別，再包裝為 `Result`
- **AND** 相容層 MUST 僅存在於少數標註檔案內，且不得被新的業務邏輯直接依賴
- **AND** 新增程式碼不得直接從相容層匯入錯誤型別或 Result 型別
