## ADDED Requirements
### Requirement: Economy Commands Localization
所有經濟類指令（`/transfer`、`/adjust`、`/balance`、`/history`）的描述與參數說明必須（MUST）以中文顯示。

#### Scenario: Transfer 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/transfer` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數（target、amount、reason）的描述文字皆為中文

#### Scenario: Adjust 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/adjust` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數（target、amount、reason）的描述文字皆為中文

#### Scenario: Balance 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/balance` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數的描述文字皆為中文

#### Scenario: History 指令描述為中文
- **WHEN** 使用者在 Discord 中查看 `/history` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數的描述文字皆為中文
