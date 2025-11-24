## ADDED Requirements
### Requirement: State Council Group Command Description
系統必須（MUST）提供 `/state_council` 群組指令，其描述與所有子指令的描述必須（MUST）以中文顯示。

#### Scenario: 群組描述為中文
- **WHEN** 使用者在 Discord 中查看 `/state_council` 群組指令
- **THEN** 群組的描述文字顯示為中文
- **AND** 所有子指令（`config_leader`、`panel`）的描述文字皆為中文

### Requirement: State Council Config Leader Command Description
系統必須（MUST）提供 `/state_council config_leader` 指令，其描述與所有參數說明必須（MUST）以中文顯示。

#### Scenario: 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/state_council config_leader` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數（leader、leader_role）的描述文字皆為中文

### Requirement: State Council Panel Command Description
系統必須（MUST）提供 `/state_council panel` 指令，其描述必須（MUST）以中文顯示。

#### Scenario: 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/state_council panel` 指令
- **THEN** 指令的描述文字顯示為中文
