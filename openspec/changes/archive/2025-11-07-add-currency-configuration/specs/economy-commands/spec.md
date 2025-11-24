## ADDED Requirements
### Requirement: Currency Configuration Command
系統必須（MUST）提供 `/currency_config` 斜線指令，允許具有管理權限的使用者設定該 guild 的貨幣名稱和圖示。

#### Scenario: 管理員設定貨幣名稱和圖示成功
- **WHEN** 具有 administrator 或 manage_guild 權限的使用者執行 `/currency_config`，提供 `name` 和 `icon` 參數
- **AND** `name` 為非空字串且長度不超過 20 字元
- **AND** `icon` 為單一 emoji 或 Unicode 字元（可選，預設為空字串）
- **THEN** 系統將配置儲存至 `economy.economy_configurations` 表
- **AND** 回傳成功訊息，顯示已設定的貨幣名稱和圖示

#### Scenario: 非管理員無法設定配置
- **WHEN** 不具有 administrator 或 manage_guild 權限的使用者執行 `/currency_config`
- **THEN** 系統拒絕請求並提示「僅限管理員可設定貨幣配置」

#### Scenario: 貨幣名稱驗證失敗
- **WHEN** 使用者提供的 `name` 參數為空字串或長度超過 20 字元
- **THEN** 系統拒絕請求並提示「貨幣名稱必須為 1-20 字元的非空字串」

#### Scenario: 僅設定貨幣名稱
- **WHEN** 管理員執行 `/currency_config`，僅提供 `name` 參數（不提供 `icon`）
- **THEN** 系統更新貨幣名稱，圖示保持不變（若已設定）或設為空字串（若未設定）

#### Scenario: 僅設定貨幣圖示
- **WHEN** 管理員執行 `/currency_config`，僅提供 `icon` 參數（不提供 `name`）
- **THEN** 系統更新貨幣圖示，名稱保持不變（若已設定）或使用預設值「點」（若未設定）

## MODIFIED Requirements
### Requirement: Economy Commands Localization
所有經濟類指令（`/transfer`、`/adjust`、`/balance`、`/history`）的描述與參數說明必須（MUST）以中文顯示。此外，所有經濟相關指令的訊息回應必須（MUST）使用該 guild 配置的貨幣名稱和圖示（若未設定則使用預設值「點」和空字串）。

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

#### Scenario: Balance 指令使用配置的貨幣名稱和圖示
- **WHEN** 使用者執行 `/balance` 指令
- **AND** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **THEN** 回應訊息顯示「目前餘額為 X 金幣 🪙」而非「目前餘額為 X 點」

#### Scenario: Transfer 指令使用配置的貨幣名稱和圖示
- **WHEN** 使用者執行 `/transfer` 指令成功
- **AND** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **THEN** 回應訊息顯示「已成功將 X 金幣 🪙 轉給...」而非「已成功將 X 點轉給...」

#### Scenario: Adjust 指令使用配置的貨幣名稱和圖示
- **WHEN** 管理員執行 `/adjust` 指令成功
- **AND** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **THEN** 回應訊息顯示「已調整 X 金幣 🪙」而非「已調整 X 點」

#### Scenario: History 指令使用配置的貨幣名稱和圖示
- **WHEN** 使用者執行 `/history` 指令
- **AND** 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- **THEN** 交易記錄顯示「收入 +X 金幣 🪙」或「支出 -X 金幣 🪙」而非「收入 +X 點」或「支出 -X 點」

#### Scenario: 未設定配置時使用預設值
- **WHEN** 使用者執行任何經濟相關指令
- **AND** 該 guild 未設定貨幣配置
- **THEN** 系統使用預設值「點」作為貨幣名稱，空字串作為圖示
- **AND** 訊息格式與現有行為一致
