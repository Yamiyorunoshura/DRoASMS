## MODIFIED Requirements
### Requirement: Council Panel Entry
系統必須（MUST）提供 `/council panel` 指令，於伺服器中由具理事身分之成員開啟「常任理事會面板」，以 ephemeral 訊息承載互動元件。`/council` 群組及其所有子指令的描述與參數說明必須（MUST）以中文顯示。

#### Scenario: 理事開啟面板成功
- WHEN 理事在已完成治理設定的 guild 中執行 `/council panel`
- THEN 回覆一則 ephemeral 訊息並附上面板操作區
- AND `/council` 群組與 `/council panel` 指令的描述文字為中文

#### Scenario: 非理事被拒
- WHEN 非理事嘗試執行 `/council panel`
- THEN 系統拒絕並提示僅限理事（中文）

#### Scenario: 未設定治理被拒
- WHEN 治理尚未完成（未設定理事角色）
- THEN 系統拒絕並提示執行 `/council config_role`（中文）

## ADDED Requirements
### Requirement: Council Group Command Description
系統必須（MUST）提供 `/council` 群組指令，其描述與所有子指令的描述必須（MUST）以中文顯示。

#### Scenario: 群組描述為中文
- **WHEN** 使用者在 Discord 中查看 `/council` 群組指令
- **THEN** 群組的描述文字顯示為中文
- **AND** 所有子指令（`config_role`、`panel`）的描述文字皆為中文

### Requirement: Council Config Role Command Description
系統必須（MUST）提供 `/council config_role` 指令，其描述與所有參數說明必須（MUST）以中文顯示。

#### Scenario: 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/council config_role` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數的描述文字皆為中文
