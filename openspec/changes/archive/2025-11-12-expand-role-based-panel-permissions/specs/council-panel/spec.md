## MODIFIED Requirements
### Requirement: Council Panel Entry
系統必須（MUST）提供 `/council panel` 指令，允許常任理事和授權人員開啟常任理事會面板，以 ephemeral 訊息承載互動元件。

#### Scenario: 常任理事開啟面板成功
- **WHEN** 具備常任理事身分組的使用者在已完成設定的 guild 中執行 `/council panel`
- **THEN** 回覆一則 ephemeral 訊息並附上完整的常任理事會面板

#### Scenario: 常任理事身分組權限檢查
- **GIVEN** 系統已完成常任理事會配置
- **WHEN** 使用者執行 `/council panel`
- **THEN** 系統檢查使用者是否具備常任理事身分組
- **AND** 若具備身分組則允許開啟面板，否則拒絕並提示無權限

#### Scenario: 未設定被拒
- **WHEN** 常任理事會尚未完成設定
- **THEN** 系統拒絕並提示執行 `/council config`

## ADDED Requirements
### Requirement: Council Member Role Configuration
常任理事會系統必須（MUST）提供常任理事身分組設定功能，允許管理者指定哪些Discord身分組被視為常任理事。

#### Scenario: 設定常任理事身分組
- **GIVEN** 系統管理員在常任理事會配置中
- **WHEN** 設定常任理事身分組ID
- **THEN** 系統保存身分組配置並更新權限檢查邏輯

#### Scenario: 多個常任理事身分組支援
- **GIVEN** 系統需要支援多個常任理事身分組
- **WHEN** 管理員設定多個常任理事身分組
- **THEN** 系統允許所有具備任一常任理事身分組的使用者存取面板

### Requirement: Fine-grained Council Operations Permission
常任理事會面板必須（MUST）提供基於常任理事身分組的細粒度權限控制，確保只有具備常任理事身分組的使用者才能執行敏感操作。

#### Scenario: 提案創建權限檢查
- **GIVEN** 使用者試圖在常任理事會面板中創建提案
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能創建提案

#### Scenario: 投票權限檢查
- **GIVEN** 使用者試圖在常任理事會提案中投票
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能投票

#### Scenario: 提案管理權限檢查
- **GIVEN** 使用者試圖管理（取消、修改）常任理事會提案
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能管理提案

#### Scenario: 面板存取權限檢查
- **GIVEN** 使用者試圖開啟常任理事會面板
- **WHEN** 系統檢查權限
- **THEN** 只有具備常任理事身分組的使用者才能開啟面板並查看內容
