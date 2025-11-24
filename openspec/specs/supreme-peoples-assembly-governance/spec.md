# supreme-peoples-assembly-governance Specification

## Purpose
TBD - created by archiving change add-supreme-peoples-assembly. Update Purpose after archive.
## Requirements
### Requirement: Supreme Assembly Account per Guild
每個 guild 必須（MUST）且僅能（MUST）存在一個「最高人民會議帳戶」作為轉帳之付款方或收款方；該帳戶屬於該 guild 的經濟體系，且系統必須（MUST）允許查詢其餘額。帳戶 ID 必須（MUST）使用 deterministic 方法生成：`9_200_000_000_000_000 + guild_id`。

#### Scenario: 初始化成功
- **GIVEN** 已以 config 指令完成最高人民會議帳戶初始化
- **WHEN** 查詢 guild 的最高人民會議帳戶
- **THEN** 系統回傳存在且唯一的帳戶識別

#### Scenario: 帳戶 ID 唯一性
- **GIVEN** 不同 guild 使用相同的帳戶 ID 生成方法
- **WHEN** 系統為各 guild 生成帳戶 ID
- **THEN** 每個 guild 生成的帳戶 ID 都是唯一的，且不會與理事會帳戶（9e15）、國務院主帳戶（9.1e15）或部門帳戶（9.5e15）碰撞

### Requirement: Role Configuration
系統必須（MUST）允許管理者透過斜線指令配置議長身分組和議員身分組。議長身分組和議員身分組必須（MUST）可以分別設定，且系統必須（MUST）驗證身分組的有效性。

#### Scenario: 配置議長身分組成功
- **GIVEN** 管理者在 guild 中執行 `/supreme_assembly config_speaker_role`
- **AND** 選擇有效的身分組
- **WHEN** 系統驗證身分組有效性
- **THEN** 系統保存議長身分組配置並初始化最高人民會議帳戶

#### Scenario: 配置議員身分組成功
- **GIVEN** 管理者在 guild 中執行 `/supreme_assembly config_member_role`
- **AND** 選擇有效的身分組
- **WHEN** 系統驗證身分組有效性
- **THEN** 系統保存議員身分組配置

#### Scenario: 未設定被拒
- **GIVEN** guild 尚未完成議長或議員身分組設定
- **WHEN** 嘗試執行治理相關操作
- **THEN** 系統拒絕並提示先完成設定

### Requirement: Transfer Capabilities
最高人民會議帳戶必須（MUST）能夠與以下對象進行轉帳：
- 一般使用者
- 理事會帳戶
- 政府部門帳戶（透過統一的 JSON 政府架構識別）
- 常任理事會（透過統一的 JSON 政府架構識別）

#### Scenario: 轉帳給使用者成功
- **GIVEN** 最高人民會議帳戶餘額充足
- **WHEN** 授權人員發起轉帳給使用者
- **THEN** 系統完成轉帳，更新雙方餘額

#### Scenario: 轉帳給理事會帳戶成功
- **GIVEN** 最高人民會議帳戶餘額充足
- **WHEN** 授權人員發起轉帳給理事會帳戶
- **THEN** 系統正確識別理事會帳戶並完成轉帳

#### Scenario: 轉帳給政府部門成功
- **GIVEN** 最高人民會議帳戶餘額充足
- **AND** 目標政府部門存在於 JSON 政府架構中
- **WHEN** 授權人員發起轉帳給政府部門
- **THEN** 系統正確識別部門帳戶並完成轉帳

#### Scenario: 轉帳給常任理事會成功
- **GIVEN** 最高人民會議帳戶餘額充足
- **AND** 常任理事會存在於 JSON 政府架構中
- **WHEN** 授權人員發起轉帳給常任理事會
- **THEN** 系統正確識別常任理事會帳戶並完成轉帳

### Requirement: Proposal Creation & Snapshot
系統必須（MUST）允許議長建立「表決提案」，包含提案內容、金額（如適用）、用途描述；提案建立瞬間必須（MUST）鎖定議員名冊快照與人數 N，並設定截止時間 = 建立時間 + 72 小時（可配置）。

#### Scenario: 建案成功並產生快照
- **GIVEN** 議長身份有效且 guild 已完成設定
- **WHEN** 議長建立表決提案
- **THEN** 立即保存議員名冊快照與 N，狀態為「進行中」

#### Scenario: 快照不變性
- **GIVEN** 提案已建立且 N=10
- **WHEN** 提案建立後新增或移除議員
- **THEN** 該提案的名冊快照 N 不變，新增者不得對本案投票，被移除者仍保有本案投票權

### Requirement: Voting Rules
投票選項必須（MUST）為「同意／反對／棄權」；議員一旦投票後必須（MUST）不可改選；「棄權」必須（MUST）不計入贊成或反對。

#### Scenario: 投票後不可改選
- **GIVEN** 議員甲已投「反對」
- **WHEN** 議員甲嘗試改投「同意」
- **THEN** 系統拒絕並提示「已投票，無法改選」

#### Scenario: 棄權不計入票數
- **GIVEN** 議員投「棄權」
- **WHEN** 系統計算票數
- **THEN** 「棄權」不計入同意或反對票數

### Requirement: Anonymity then Disclosure
進行中階段必須（MUST）僅顯示合計票數（同意、反對、棄權分別統計）；表決結束時必須（MUST）揭露各投票者之最終投票。

#### Scenario: 匿名投票階段
- **GIVEN** 表決進行中
- **WHEN** 查看表決狀態
- **THEN** 僅顯示合計票數（同意 X 票、反對 Y 票、棄權 Z 票），不顯示個別投票者

#### Scenario: 結案後揭露
- **GIVEN** 表決已結束（通過、否決或逾時）
- **WHEN** 查看表決結果
- **THEN** 顯示各投票者的最終投票（同意/反對/棄權）

### Requirement: Proposal Status Transitions
表決提案狀態必須（MUST）支援以下轉移：
- `進行中` → `已通過`（同意票數達到門檻）
- `進行中` → `已否決`（反對票數達到門檻或提前否決）
- `進行中` → `已逾時`（達到截止時間仍未通過）
- `進行中` → `已撤案`（議長撤銷，僅在無投票前可撤銷）

#### Scenario: 表決通過
- **GIVEN** N=10，門檻 T=6（floor(N/2) + 1）
- **WHEN** 在截止前同意票到達 6 票
- **THEN** 狀態轉為「已通過」並通知所有議員

#### Scenario: 表決否決
- **GIVEN** N=10，門檻 T=6
- **WHEN** 在截止前反對票達到門檻或提前判定無法通過
- **THEN** 狀態轉為「已否決」並通知所有議員

#### Scenario: 表決逾時
- **GIVEN** 表決距截止已到
- **AND** 同意票未達門檻
- **THEN** 狀態為「已逾時」並通知所有議員

#### Scenario: 撤案限制
- **GIVEN** 表決已有任一投票紀錄
- **WHEN** 議長嘗試撤案
- **THEN** 系統拒絕並提示「已有投票，無法撤案」

### Requirement: Passing Threshold
通過條件必須（MUST）為「同意票數 ≥ floor(N/2) + 1」，其中 N 為提案建立時的議員人數。

#### Scenario: 門檻計算正確
- **GIVEN** N=10
- **WHEN** 計算通過門檻
- **THEN** T = floor(10/2) + 1 = 6

### Requirement: Summons Functionality
系統必須（MUST）提供傳召功能，允許議長傳召議員或政府官員。傳召必須（MUST）通過私訊通知被傳召人，並記錄傳召歷史。

#### Scenario: 傳召議員成功
- **GIVEN** 議長在面板中點擊「傳召」
- **AND** 選擇「傳召議員」
- **AND** 從下拉選單選擇議員
- **WHEN** 系統執行傳召
- **THEN** 被傳召的議員收到私訊通知，面板記錄傳召歷史

#### Scenario: 傳召政府官員成功
- **GIVEN** 議長在面板中點擊「傳召」
- **AND** 選擇「傳召政府官員」
- **AND** 從下拉選單選擇政府部門領導人或國務院領袖或常任理事會成員
- **WHEN** 系統執行傳召
- **THEN** 被傳召的政府官員收到私訊通知，面板記錄傳召歷史

#### Scenario: 傳召面板流程
- **GIVEN** 議長在面板中點擊「傳召」
- **WHEN** 系統顯示傳召選項
- **THEN** 顯示第二個嵌入訊息面板，詢問「傳召議員」或「傳召政府官員」

#### Scenario: 傳召通知內容
- **GIVEN** 議長發起傳召
- **WHEN** 被傳召人收到私訊通知
- **THEN** 通知包含傳召人資訊、傳召原因（如有）和相關連結

### Requirement: Permissions and Configuration
未完成治理設定（議長角色、議員角色、帳戶等）前，任何治理相關指令必須（MUST）被拒絕並回覆指引；系統必須（MUST）僅允許議長建立表決提案；系統必須（MUST）僅允許議員（含議長）投票。

#### Scenario: 非議長無法建案
- **GIVEN** 使用者不具議長身分
- **WHEN** 嘗試建立表決提案
- **THEN** 系統拒絕並提示僅限議長

#### Scenario: 非議員無法投票
- **GIVEN** 使用者不具議員身分
- **WHEN** 嘗試投票
- **THEN** 系統拒絕並提示僅限議員

### Requirement: Audit & Logging
系統必須（MUST）記錄表決提案建立者、時間戳、議員名冊快照（含名單與 N）、每次投票、結案原因，並且必須（MUST）支援匯出。

#### Scenario: 稽核可追溯
- **GIVEN** 任一期間匯出請求
- **WHEN** 系統產生匯出檔案
- **THEN** 可重建每一表決提案的完整生命週期事件，包含所有投票記錄

### Requirement: Concurrency Limit per Guild
同一 guild 的「進行中」表決提案數量上限必須（MUST）為 5；超過時系統必須（MUST）拒絕新建案並提示。

#### Scenario: 超過上限拒絕建案
- **GIVEN** 該 guild 已有 5 筆進行中表決提案
- **WHEN** 議長嘗試再建立新表決提案
- **THEN** 建案被拒，提示已達上限

### Requirement: Notifications
系統必須（MUST）於建案時通知全體議員；並且在截止前 24 小時再次 DM 提醒尚未投票之議員；表決結束時必須（MUST）通知全體議員結果。

#### Scenario: 建案通知
- **GIVEN** 議長建立新表決提案
- **WHEN** 系統處理建案
- **THEN** 向全體議員發送 DM 通知，包含投票入口

#### Scenario: T-24h 提醒未投者
- **GIVEN** 距離截止時間剩餘 24 小時
- **WHEN** 尚有未投議員
- **THEN** 只向未投議員發送提醒 DM

#### Scenario: 結案通知
- **GIVEN** 表決已結束（通過/否決/逾時）
- **WHEN** 系統處理結案
- **THEN** 向全體議員發送 DM 通知，包含結果和各投票者的投票
