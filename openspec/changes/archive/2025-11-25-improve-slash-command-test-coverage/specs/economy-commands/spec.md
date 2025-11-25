## ADDED Requirements

### Requirement: Comprehensive Test Coverage for Economy Commands

系統必須（MUST）為所有經濟類 slash commands 提供全面的測試覆蓋，確保達到 90%以上的代碼覆蓋率，包括所有成功路徑、錯誤處理路徑、權限檢查和邊界條件。

#### Scenario: Adjust 命令權限檢查測試覆蓋

- **WHEN** 測試套件執行 adjust 命令的權限驗證邏輯
- **THEN** 所有權限分支（管理員、法務部、非權限用戶）都必須有對應測試案例
- **AND** Result<T,E>錯誤路徑必須被完整測試

#### Scenario: Transfer 命令驗證邏輯測試覆蓋

- **WHEN** 測試套件驗證 transfer 命令的業務邏輯
- **THEN** 冷卻時間、餘額檢查、目標驗證等所有分支必須有測試案例
- **AND** 同步模式和事件池模式都必須被測試

#### Scenario: Balance 命令分頁功能測試覆蓋

- **WHEN** 測試套件測試 balance 命令的歷史查詢功能
- **THEN** 分頁邏輯、空結果、大數據集等所有情況必須有測試案例
- **AND** Result<T,E>處理路徑必須被完整覆蓋

#### Scenario: Result<T,E>錯誤處理測試覆蓋

- **WHEN** 測試套件測試所有經濟命令的錯誤處理
- **THEN** 每個可能的錯誤類型（ValidationError、BusinessLogicError、DatabaseError）都必須有對應測試
- **AND** 錯誤消息格式和用戶體驗必須被驗證

#### Scenario: 邊界條件和異常情況測試覆蓋

- **WHEN** 測試套件執行邊界條件測試
- **THEN** 極大金額、負數處理、特殊字符、網絡超時等情況必須有測試案例
- **AND** 系統必須在所有異常情況下保持穩定性

#### Scenario: 集成測試覆蓋率要求

- **WHEN** 測試套件執行集成測試
- **THEN** 跨命令交互、數據庫事務、Discord API 集成等必須有完整測試覆蓋
- **AND** 所有主要使用場景必須被驗證
