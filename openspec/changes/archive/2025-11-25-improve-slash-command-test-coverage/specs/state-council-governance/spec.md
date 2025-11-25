## ADDED Requirements

### Requirement: Comprehensive Test Coverage for State Council Governance Commands

系統必須（MUST）為國務院治理 slash commands 提供全面的測試覆蓋，確保達到 90%以上的代碼覆蓋率，包括部門管理、貨幣發行、稅收收集、福利發放和所有 Result<T,E>錯誤處理路徑。

#### Scenario: State Council 部門管理測試覆蓋

- **WHEN** 測試套件驗證 state_council 命令的部門管理功能
- **THEN** 部門創建、編輯、刪除、領導人配置等所有操作必須有對應測試案例
- **AND** Result<T,E>成功和失敗路徑必須被完整測試

#### Scenario: State Council 貨幣發行測試覆蓋

- **WHEN** 測試套件測試國務院貨幣發行機制
- **THEN** 發行限制驗證、部門分配、餘額檢查等所有分支必須有測試案例
- **AND** 權限檢查和審計記錄必須被驗證

#### Scenario: State Council 稅收收集測試覆蓋

- **WHEN** 測試套件驗證國務院稅收收集功能
- **THEN** 稅率配置、征收計算、部門分配等所有邏輯必須有測試案例
- **AND** Result<T,E>錯誤處理和邊界條件必須被完整覆蓋

#### Scenario: State Council 福利發放測試覆蓋

- **WHEN** 測試套件測試國務院福利發放系統
- **THEN** 發放資格驗證、金額計算、目標分配等所有情況必須有測試案例
- **AND** 權限驗證和資金來源檢查必須被驗證

#### Scenario: State Council 權限管理測試覆蓋

- **WHEN** 測試套件驗證國務院權限檢查
- **THEN** 部門領導人、國務院領袖、法務部等所有權限級別必須有測試案例
- **AND** StateCouncilNotConfiguredError 等錯誤處理必須被完整測試

#### Scenario: State Council 集成測試覆蓋

- **WHEN** 測試套件執行國務院集成測試
- **THEN** 完整的部門-發行-稅收-福利流程必須被測試
- **AND** 與經濟系統和理事會系統的交互必須被驗證
