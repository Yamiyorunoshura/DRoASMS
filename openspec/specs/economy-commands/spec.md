# economy-commands Specification

## Purpose
定義本專案的經濟類斜線指令與理事會治理的整合行為。重點為在 `/adjust` 與 `/transfer` 支援提及已綁定之「常任理事會」身分組並映射到該 guild 的理事會帳戶，同時維持既有權限與餘額檢查、錯誤處理與防呆限制。此規格不改變一般使用者的基本轉帳與加減值行為，只增加身分組→帳戶的安全映射能力。
## Requirements
### Requirement: Mention Council Role in /adjust
系統必須（MUST）允許管理者在 `/adjust` 以「常任理事會」綁定之身分組作為目標，並將其映射至該 guild 的理事會帳戶 ID（由程式以 deterministic 方式生成）。系統必須（MUST）同時支援以「議長」綁定之身分組作為目標，並將其映射至該 guild 的最高人民會議帳戶 ID（由程式以 deterministic 方式生成：`9_200_000_000_000_000 + guild_id`）。

#### Scenario: 以理事會身分組加值成功
- WHEN 管理者在已設定理事會的 guild 中執行 `/adjust`，target 提及為已綁定的理事會身分組
- AND amount 為正整數，reason 填寫
- THEN 系統將目標映射為「理事會帳戶」並成功完成加值

#### Scenario: 以理事會身分組扣點成功
- WHEN 管理者在已設定理事會的 guild 中執行 `/adjust`，target 提及為已綁定的理事會身分組
- AND amount 為負整數，reason 填寫
- THEN 系統將目標映射為「理事會帳戶」並成功完成扣點，且不得使餘額為負

#### Scenario: 以議長身分組加值成功
- WHEN 管理者在已設定最高人民會議的 guild 中執行 `/adjust`，target 提及為已綁定的議長身分組
- AND amount 為正整數，reason 填寫
- THEN 系統將目標映射為「最高人民會議帳戶」並成功完成加值

#### Scenario: 以議長身分組扣點成功
- WHEN 管理者在已設定最高人民會議的 guild 中執行 `/adjust`，target 提及為已綁定的議長身分組
- AND amount 為負整數，reason 填寫
- THEN 系統將目標映射為「最高人民會議帳戶」並成功完成扣點，且不得使餘額為負

#### Scenario: 未設定治理被拒
- WHEN guild 尚未完成理事會或最高人民會議綁定
- AND target 提及為理事會或議長身分組
- THEN 系統拒絕並提示應先執行 `/council config_role` 或 `/supreme_assembly config_speaker_role`

#### Scenario: 提及非綁定身分組被拒
- WHEN target 為任意身分組但非理事會、議長或部門領導人綁定者
- THEN 系統拒絕請求並提示「僅支援提及已綁定的常任理事會、議長或部門領導人身分組」

### Requirement: Mention Council Role in /transfer
系統必須（MUST）允許一般成員在 `/transfer` 以「常任理事會」綁定之身分組作為受款人，並將其映射至該 guild 的理事會帳戶 ID 後執行轉帳。系統必須（MUST）同時支援以「國務院領袖」綁定之身分組作為受款人，並將其映射至該 guild 的國務院主帳戶 ID 後執行轉帳。系統必須（MUST）同時支援以「部門領導人」綁定之身分組作為受款人，並將其映射至對應的部門政府帳戶 ID 後執行轉帳。系統必須（MUST）同時支援以「議長」綁定之身分組作為受款人，並將其映射至該 guild 的最高人民會議帳戶 ID（由程式以 deterministic 方式生成：`9_200_000_000_000_000 + guild_id`）後執行轉帳。系統必須（MUST）在同步模式和事件池模式下都正確支援上述所有身分組轉帳功能。

#### Scenario: 轉入理事會帳戶成功
- WHEN 成員在已設定理事會的 guild 中執行 `/transfer`，target 提及為已綁定的理事會身分組
- AND amount 為正整數
- THEN 系統將目標映射為「理事會帳戶」並成功完成轉帳

#### Scenario: 轉入國務院主帳戶成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的國務院領袖身分組
- AND amount 為正整數
- THEN 系統將目標映射為「國務院主帳戶」並成功完成轉帳

#### Scenario: 轉入部門政府帳戶成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的部門領導人身分組
- AND amount 為正整數
- THEN 系統將目標映射為對應的「部門政府帳戶」並成功完成轉帳

#### Scenario: 轉入最高人民會議帳戶成功
- WHEN 成員在已設定最高人民會議的 guild 中執行 `/transfer`，target 提及為已綁定的議長身分組
- AND amount 為正整數
- THEN 系統將目標映射為「最高人民會議帳戶」並成功完成轉帳

#### Scenario: 未設定治理被拒
- WHEN guild 尚未完成理事會、國務院或最高人民會議綁定
- AND target 提及為理事會身分組、國務院領袖身分組或議長身分組
- THEN 系統拒絕並提示應先執行 `/council config_role`、`/state_council config_leader` 或 `/supreme_assembly config_speaker_role`

#### Scenario: 提及非綁定身分組被拒
- WHEN target 為任意身分組但非已綁定的理事會、國務院領袖、部門領導人或議長身分組
- THEN 系統拒絕請求並提示「僅支援提及常任理事會、國務院領袖、已綁定之部門領導人或議長身分組，或直接指定個別成員」

#### Scenario: 事件池模式下理事會身分組轉帳成功
- WHEN 成員在已設定理事會的 guild 中執行 `/transfer`，target 提及為已綁定的理事會身分組
- AND 系統啟用事件池模式（`TRANSFER_EVENT_POOL_ENABLED=true`）
- AND amount 為正整數
- THEN 轉帳請求被記錄到 `economy.pending_transfers` 表
- AND 系統將目標映射為「理事會帳戶」並在檢查通過後自動執行轉帳

#### Scenario: 事件池模式下國務院領袖身分組轉帳成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的國務院領袖身分組
- AND 系統啟用事件池模式（`TRANSFER_EVENT_POOL_ENABLED=true`）
- AND amount 為正整數
- THEN 轉帳請求被記錄到 `economy.pending_transfers` 表
- AND 系統將目標映射為「國務院主帳戶」並在檢查通過後自動執行轉帳

#### Scenario: 事件池模式下部門領導人身分組轉帳成功
- WHEN 成員在已設定國務院的 guild 中執行 `/transfer`，target 提及為已綁定的部門領導人身分組
- AND 系統啟用事件池模式（`TRANSFER_EVENT_POOL_ENABLED=true`）
- AND amount 為正整數
- THEN 轉帳請求被記錄到 `economy.pending_transfers` 表
- AND 系統將目標映射為對應的「部門政府帳戶」並在檢查通過後自動執行轉帳

#### Scenario: 事件池模式下議長身分組轉帳成功
- WHEN 成員在已設定最高人民會議的 guild 中執行 `/transfer`，target 提及為已綁定的議長身分組
- AND 系統啟用事件池模式（`TRANSFER_EVENT_POOL_ENABLED=true`）
- AND amount 為正整數
- THEN 轉帳請求被記錄到 `economy.pending_transfers` 表
- AND 系統將目標映射為「最高人民會議帳戶」並在檢查通過後自動執行轉帳

### Requirement: Asynchronous Transfer Event Pool
系統必須（MUST）提供異步轉帳事件池機制，允許轉帳請求在檢查失敗時自動重試，無需使用者手動操作。

#### Scenario: 轉帳請求進入事件池
- **WHEN** 使用者執行 `/transfer` 指令，且系統啟用事件池模式
- **THEN** 轉帳請求被記錄到 `economy.pending_transfers` 表，狀態為 `pending`
- **AND** 觸發器自動啟動檢查流程，狀態變更為 `checking`

#### Scenario: 所有檢查通過後自動執行轉帳
- **WHEN** `pending_transfers` 記錄的所有檢查（餘額、冷卻、限額）都標記為通過（值為 1）
- **THEN** Python 層自動呼叫 `fn_transfer_currency` 執行實際轉帳
- **AND** 狀態更新為 `approved`，轉帳結果返回給使用者

#### Scenario: 檢查失敗時自動重試
- **WHEN** 轉帳檢查失敗（餘額不足、冷卻中、超過每日上限）
- **THEN** 系統使用指數退避策略自動重試（間隔為 `2^retry_count` 秒，上限 300 秒）
- **AND** 重試計數增加，最多重試 10 次
- **AND** 若超過重試上限或記錄過期，狀態標記為 `rejected`

#### Scenario: 檢查結果記錄在 JSONB 欄位
- **WHEN** 每項檢查（餘額、冷卻、限額）執行完成
- **THEN** 檢查結果（1=通過，0=失敗）記錄到 `pending_transfers.checks` JSONB 欄位
- **AND** 透過 `pg_notify` 發送檢查結果事件，Python 層可即時追蹤狀態

#### Scenario: 過期記錄自動清理
- **WHEN** `pending_transfers` 記錄超過過期時間（預設 24 小時）
- **THEN** 系統定期清理過期記錄（透過 `pg_cron` 或 Python 層定時任務）
- **AND** 清理前將狀態標記為 `rejected`（若仍為 `pending` 或 `checking`）

### Requirement: Transfer Event Pool Configuration
系統必須（MUST）允許透過配置啟用或停用事件池架構，預設行為應保持向後相容。

#### Scenario: 事件池模式可配置
- **WHEN** 環境變數 `TRANSFER_EVENT_POOL_ENABLED=true` 或配置檔案啟用事件池
- **THEN** `/transfer` 指令使用事件池架構處理轉帳請求
- **WHEN** 事件池未啟用
- **THEN** `/transfer` 指令使用現有同步轉帳路徑（直接呼叫 `fn_transfer_currency`）

### Requirement: Transfer Success Notification to Initiator
系統必須（MUST）在轉帳成功時，除了 DM 通知收款人外，也向轉帳人（發起人）發送 ephemeral notification，告知轉帳已成功執行。

#### Scenario: 同步模式轉帳成功通知
- **WHEN** 轉帳在同步模式下成功執行
- **THEN** 轉帳人在執行 `/transfer` 指令時收到 ephemeral 回應，顯示轉帳成功訊息
- **AND** 收款人收到 DM 通知

#### Scenario: 事件池模式轉帳成功通知
- **WHEN** 轉帳在事件池模式下異步完成
- **THEN** 系統向轉帳人發送 ephemeral followup notification，顯示轉帳成功訊息
- **AND** 收款人收到 DM 通知

#### Scenario: 通知內容包含轉帳詳情
- **WHEN** 轉帳成功執行
- **THEN** 轉帳人收到的 ephemeral notification 包含以下資訊：
  - 轉帳金額
  - 收款人資訊（mention 或顯示名稱）
  - 轉帳後的餘額
  - 備註（如有）

#### Scenario: 通知失敗不影響轉帳流程
- **WHEN** 轉帳成功但發送 ephemeral notification 失敗（例如 interaction token 過期、guild 不存在等）
- **THEN** 轉帳交易仍視為成功完成
- **AND** 系統記錄通知失敗事件，但不中斷後續流程

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

### Requirement: State Council Main Account ID Derivation
系統必須（MUST）提供 deterministic 方法來生成國務院主帳戶 ID，使用 9.1e15 區段作為基底，避免與理事會帳戶（9e15）和部門帳戶（9.5e15）碰撞。

#### Scenario: 國務院主帳戶 ID 生成
- WHEN 系統需要為特定 guild 生成國務院主帳戶 ID
- THEN 使用公式 `9_100_000_000_000_000 + guild_id` 生成帳戶 ID
- AND 生成的帳戶 ID 不會與現有的理事會帳戶或部門帳戶 ID 碰撞

#### Scenario: 帳戶 ID 唯一性保證
- WHEN 不同 guild 使用相同的國務院主帳戶 ID 生成方法
- THEN 每個 guild 生成的帳戶 ID 都是唯一的
- AND 帳戶 ID 在 int64 範圍內（不會溢位）

### Requirement: Comprehensive Test Coverage for Economy Commands

系統必須（MUST）為所有經濟類 slash commands 提供全面的測試覆蓋，確保達到 90%以上的代碼覆蓋率，包括所有成功路徑、錯誤處理路徑、權限檢查和邊界條件。

#### Scenario: Adjust 命令權限檢查測試覆蓋

- **WHEN** 測試套件執行 adjust 命令的權限驗證邏輯
- **THEN** 所有權限分支（管理員、法務部、非權限用戶）都必須有對應測試案例
- **AND** Result<T,E>錯誤路徑必須被完整測試

#### Scenario: Transfer 命令驗證邏輯測試覆蓋

- **WHEN** 測試套件驗證 transfer 命令的業務邏輯
- **THEN** 冷卻時間、餘額檢查、目標驗證等所有分支必須有測試案例
- **AND** 同步模式和事件池模式都必須被測試

#### Scenario: Balance 命令分頁功能測試覆蓋

- **WHEN** 測試套件測試 balance 命令的歷史查詢功能
- **THEN** 分頁邏輯、空結果、大數據集等所有情況必須有測試案例
- **AND** Result<T,E>處理路徑必須被完整覆蓋

#### Scenario: Result<T,E>錯誤處理測試覆蓋

- **WHEN** 測試套件測試所有經濟命令的錯誤處理
- **THEN** 每個可能的錯誤類型（ValidationError、BusinessLogicError、DatabaseError）都必須有對應測試
- **AND** 錯誤消息格式和用戶體驗必須被驗證

#### Scenario: 邊界條件和異常情況測試覆蓋

- **WHEN** 測試套件執行邊界條件測試
- **THEN** 極大金額、負數處理、特殊字符、網絡超時等情況必須有測試案例
- **AND** 系統必須在所有異常情況下保持穩定性

#### Scenario: 集成測試覆蓋率要求

- **WHEN** 測試套件執行集成測試
- **THEN** 跨命令交互、數據庫事務、Discord API 集成等必須有完整測試覆蓋
- **AND** 所有主要使用場景必須被驗證
