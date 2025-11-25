## MODIFIED Requirements

### Requirement: Economy Commands Localization

所有經濟類指令（`/transfer`、`/adjust`）的描述與參數說明必須（MUST）以中文顯示。此外，所有經濟相關指令的訊息回應必須（MUST）使用該 guild 配置的貨幣名稱和圖示（若未設定則使用預設值「點」和空字串）。

#### Scenario: Transfer 指令描述為中文

- **WHEN** 使用者在 Discord 中查看 `/transfer` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數（target、amount、reason）的描述文字皆為中文

#### Scenario: Adjust 指令描述為中文

- **WHEN** 使用者在 Discord 中查看 `/adjust` 指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數（target、amount、reason）的描述文字皆為中文

#### Scenario: Transfer 指令使用配置的貨幣名稱和圖示

- **WHEN** 使用者執行 `/transfer` 指令成功
- **AND** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **THEN** 回應訊息顯示「已成功將 X 金幣 🪙 轉給...」而非「已成功將 X 點轉給...」

#### Scenario: Adjust 指令使用配置的貨幣名稱和圖示

- **WHEN** 管理員執行 `/adjust` 指令成功
- **AND** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **THEN** 回應訊息顯示「已調整 X 金幣 🪙」而非「已調整 X 點」

#### Scenario: 未設定配置時使用預設值

- **WHEN** 使用者執行任何經濟相關指令
- **AND** 該 guild 未設定貨幣配置
- **THEN** 系統使用預設值「點」作為貨幣名稱，空字串作為圖示
- **AND** 訊息格式與現有行為一致
