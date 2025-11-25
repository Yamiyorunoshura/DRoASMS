## ADDED Requirements

### Requirement: Comprehensive Test Coverage for Council Governance Commands

系統必須（MUST）為理事會治理 slash commands 提供全面的測試覆蓋，確保達到 90%以上的代碼覆蓋率，包括提案創建、投票執行、權限管理和所有 Result<T,E>錯誤處理路徑。

#### Scenario: Council 提案創建測試覆蓋

- **WHEN** 測試套件驗證 council 命令的提案創建功能
- **THEN** 所有提案類型、金額驗證、目標驗證分支必須有對應測試案例
- **AND** Result<T,E>成功和失敗路徑必須被完整測試

#### Scenario: Council 投票功能測試覆蓋

- **WHEN** 測試套件測試理事會投票機制
- **THEN** 贊成、反對、棄權、超時、重複投票等所有情況必須有測試案例
- **AND** 投票閾值計算和執行邏輯必須被驗證

#### Scenario: Council 權限驗證測試覆蓋

- **WHEN** 測試套件驗證理事會權限檢查
- **THEN** 理事會成員、非成員、管理員等所有權限級別必須有測試案例
- **AND** 身分組快照和權限驗證邏輯必須被完整覆蓋

#### Scenario: Council 錯誤處理測試覆蓋

- **WHEN** 測試套件測試理事會命令的錯誤處理
- **THEN** GovernanceNotConfiguredError、ValidationError、BusinessLogicError 等所有錯誤類型必須有對應測試
- **AND** 錯誤消息和用戶反饋必須被驗證

#### Scenario: Council 集成測試覆蓋

- **WHEN** 測試套件執行理事會集成測試
- **THEN** 完整的提案-投票-執行流程必須被測試
- **AND** 與經濟系統的交互和數據庫事務必須被驗證
