## ADDED Requirements

### Requirement: Comprehensive Test Coverage for Supreme Assembly Governance Commands

系統必須（MUST）為最高人民會議治理 slash commands 提供全面的測試覆蓋，確保達到 90%以上的代碼覆蓋率，包括提案管理、投票機制、傳喚功能、帳戶管理和所有 Result<T,E>錯誤處理路徑。

#### Scenario: Supreme Assembly 提案管理測試覆蓋

- **WHEN** 測試套件驗證 supreme_assembly 命令的提案功能
- **THEN** 提案創建、編輯、取消、過期處理等所有操作必須有對應測試案例
- **AND** Result<T,E>成功和失敗路徑必須被完整測試

#### Scenario: Supreme Assembly 投票機制測試覆蓋

- **WHEN** 測試套件測試最高人民會議投票系統
- **THEN** 三選投票（贊成/反對/棄權）、匿名性、披露機制等所有分支必須有測試案例
- **AND** 投票閾值計算和執行邏輯必須被驗證

#### Scenario: Supreme Assembly 傳喚功能測試覆蓋

- **WHEN** 測試套件驗證最高人民會議傳喚機制
- **THEN** 傳喚理事會成員、政府官員、消息發送等所有情況必須有測試案例
- **AND** 權限檢查和 DM 交互必須被完整測試

#### Scenario: Supreme Assembly 帳戶管理測試覆蓋

- **WHEN** 測試套件測試最高人民會議帳戶系統
- **THEN** 帳戶創建、餘額查詢、轉帳功能等所有操作必須有測試案例
- **AND** 確定性 ID 生成和帳戶映射必須被驗證

#### Scenario: Supreme Assembly 權限驗證測試覆蓋

- **WHEN** 測試套件驗證最高人民會議權限檢查
- **THEN** 議長配置、成員權限、管理員權限等所有級別必須有測試案例
- **AND** GovernanceNotConfiguredError 等錯誤處理必須被完整測試

#### Scenario: Supreme Assembly 集成測試覆蓋

- **WHEN** 測試套件執行最高人民會議集成測試
- **THEN** 完整的提案-投票-執行-傳喚流程必須被測試
- **AND** 與其他治理系統的交互必須被驗證
