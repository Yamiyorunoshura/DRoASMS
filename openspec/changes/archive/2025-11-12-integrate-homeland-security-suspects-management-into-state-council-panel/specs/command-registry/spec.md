# command-registry Specification Changes

## REMOVED Requirements

### Requirement: State Council Suspects Command Registration
移除國務院嫌犯管理斜線指令的註冊和相關定義。

#### Scenario: 移除指令定義
- **GIVEN** `state_council.py` 中的 `suspects` 指令定義
- **WHEN** 執行功能整合
- **THEN** 移除 `"state_council suspects"` 指令定義物件
- **AND** 移除相關的描述、標籤和範例

#### Scenario: 移除指令處理函數
- **GIVEN** `suspects` 異步指令處理函數
- **WHEN** 功能整合到面板
- **THEN** 移除 `suspects` 函數及其裝飾器
- **AND** 移除相關的權限檢查邏輯（保留供面板使用）

#### Scenario: 清理指令導出
- **GIVEN** `register_state_council_commands` 函數
- **WHEN** 移除嫌疑人指令
- **THEN** 確保指令註冊函數不再包含 `suspects` 子指令
- **AND** 更新相關的命令樹註冊邏輯

### Requirement: Suspects Management UI Components
移除專為斜線指令設計的嫌疑人管理UI組件。

#### Scenario: 移除 SuspectsManagementView 類別
- **GIVEN** 現有的 `SuspectsManagementView` 類別
- **WHEN** 功能整合完成
- **THEN** 完全移除該類別及其方法
- **AND** 移除相關的輔助類別和函數

#### Scenario: 清理相關常數和輔助函數
- **GIVEN** 專門支援嫌犯管理指令的常數和函數
- **WHEN** 指令移除後
- **THEN** 移除不再使用的常數定義
- **AND** 重構可重用的邏輯到服務層
