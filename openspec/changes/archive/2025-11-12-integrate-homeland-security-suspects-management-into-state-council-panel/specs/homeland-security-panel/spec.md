# homeland-security-panel Specification Changes

## MODIFIED Requirements

### Requirement: Suspects Management Command Integration
國土安全部面板必須（MUST）整合現有的嫌犯管理功能，取代 `/state_council suspects` 斜線指令。

#### Scenario: 整合嫌疑人管理功能到面板
- **GIVEN** 具備國土安全部權限的使用者
- **WHEN** 在國土安全部面板中操作嫌犯管理
- **THEN** 面板提供與斜線指令相同的完整功能
- **AND** 支援查看、釋放、設定自動釋放時限等操作

#### Scenario: 移除斜線指令依賴
- **GIVEN** 現有的嫌犯管理斜線指令
- **WHEN** 功能整合到面板後
- **THEN** 移除 `/state_council suspects` 斜線指令註冊
- **AND** 移除相關的 `SuspectsManagementView` 類別
- **AND** 保留底層服務邏輯供面板使用

### Requirement: Enhanced Suspect Management UI
面板必須（MUST）提供比斜線指令更豐富的使用者界面和互動體驗。

#### Scenario: 改進的嫌疑人列表顯示
- **GIVEN** 使用者在面板中查看嫌疑人
- **WHEN** 系統顯示嫌疑人資訊
- **THEN** 提供更詳細的資訊顯示（包含逮捕時間、原因、自動釋放狀態）
- **AND** 支援分頁和搜尋功能（如嫌疑人數量較多）

#### Scenario: 批次操作優化
- **GIVEN** 需要操作多個嫌疑人
- **WHEN** 使用者選擇批次操作
- **THEN** 提供批次釋放確認對話框
- **AND** 顯示操作進度和結果摘要

## REMOVED Requirements

### Requirement: Standalone Suspects Slash Command
移除獨立的嫌犯管理斜線指令實現。

#### Scenario: 移除斜線指令註冊
- **GIVEN** 現有的 `/state_council suspects` 指令註冊
- **WHEN** 執行整合變更
- **THEN** 從指令註冊中移除 `suspects` 子指令
- **AND** 移除相關的指令定義和處理邏輯

#### Scenario: 清理相關UI組件
- **GIVEN** 現有的 `SuspectsManagementView` 類別
- **WHEN** 功能整合完成
- **THEN** 移除不再使用的UI視圖類別
- **AND** 清理相關的輔助函數和常數
