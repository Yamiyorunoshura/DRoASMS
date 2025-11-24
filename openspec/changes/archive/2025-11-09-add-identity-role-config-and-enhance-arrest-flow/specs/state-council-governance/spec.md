## ADDED Requirements
### Requirement: Citizen and Suspect Role Configuration
系統必須（MUST）提供指令以設定公民身分組和嫌犯身分組。這些身分組必須（MUST）由管理員或管理伺服器權限的使用者設定，並儲存在國務院配置中。

#### Scenario: 設定公民身分組成功
- **GIVEN** 管理員執行 `/state_council config_citizen_role` 指令
- **AND** 指定有效的 Discord 身分組
- **WHEN** 系統處理設定請求
- **THEN** 系統保存公民身分組 ID 至配置中
- **AND** 回覆成功訊息

#### Scenario: 設定嫌犯身分組成功
- **GIVEN** 管理員執行 `/state_council config_suspect_role` 指令
- **AND** 指定有效的 Discord 身分組
- **WHEN** 系統處理設定請求
- **THEN** 系統保存嫌犯身分組 ID 至配置中
- **AND** 回覆成功訊息

#### Scenario: 未設定身分組時拒絕操作
- **GIVEN** 公民身分組或嫌犯身分組未設定
- **WHEN** 嘗試執行需要身分組的操作（如逮捕）
- **THEN** 系統拒絕操作並提示需要先設定對應的身分組

## MODIFIED Requirements
### Requirement: Homeland Security - Citizenship Management
國土安全部必須（MUST）提供身分管理功能，可以移除被選中使用者的公民身分組並掛上疑犯身分。疑犯身分組必須（MUST）由管理員透過指令預先配置。公民身分組必須（MUST）由管理員透過指令預先配置。

#### Scenario: 移除公民身分
- **GIVEN** 具備國土安全部權限的人員
- **AND** 公民身分組和嫌犯身分組已設定
- **WHEN** 在面板中選擇目標使用者並執行逮捕操作
- **THEN** 系統自動移除使用者的公民身分組並掛上嫌犯身分組
- **AND** 記錄身分變更操作

#### Scenario: 疑犯身分設定驗證
- **GIVEN** 管理員未設定疑犯身分組或公民身分組
- **WHEN** 嘗試執行逮捕操作
- **THEN** 系統拒絕操作並提示需要先設定對應的身分組
