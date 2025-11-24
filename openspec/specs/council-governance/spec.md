# council-governance Specification

## Purpose
定義 guild 級治理流程與資料模型：理事會帳戶、轉帳提案生命週期、名冊快照與門檻計算、投票與改票規則、通過／否決／逾時／撤案／執行失敗／已執行等狀態轉移，以及通知、提醒與稽核匯出。目標是以可驗證、可追溯且預期一致的方式決策資金移轉。此規格不涵蓋 UI；互動入口與面板行為由 `council-panel` 規格定義。
## Requirements
### Requirement: Council Account per Guild
每個 guild 必須（MUST）且僅能（MUST）存在一個「理事會帳戶」作為轉帳之付款方；該帳戶屬於該 guild 的經濟體系，且系統必須（MUST）允許查詢其餘額。
#### Scenario: 初始化成功
- Given 已以 config 指令完成理事會帳戶初始化
- When 查詢 guild 的 Council 帳戶
- Then 系統回傳存在且唯一的帳戶識別

### Requirement: Proposal Creation & Snapshot
系統必須（MUST）允許理事建立「轉帳提案」，包含受款人、金額（整數且 >0）、用途描述、（可選）附件連結；提案建立瞬間必須（MUST）鎖定理事名冊快照與人數 N，計算門檻 T = floor(N/2) + 1，並設定截止時間 = 建立時間 + 72 小時。
#### Scenario: 建案成功並產生快照
- Given 理事身份有效且 guild 已完成設定
- When 建立金額 100、受款人 U、用途描述 D 的轉帳提案
- Then 立即保存名冊快照與 N、T 與截止時間，狀態為「進行中」

### Requirement: Snapshot Invariance
名冊快照於提案生命週期內必須（MUST）保持不變；提案後新增理事必須（MUST）無本案投票權；提案後被移除的理事必須（MUST）保有本案投票權。
#### Scenario: 新增理事不具本案投票權
- Given 提案已建立且 N=5
- When 提案建立後新增 1 名理事
- Then 該新增者不得對本案投票，且 T 與 N 不變

### Requirement: Voting Options and Changes
投票選項必須（MUST）為「同意／反對／棄權」；理事必須（MUST）可在截止前重複投票，且以最後一次投票作為最終意向；「棄權」必須（MUST）不計入贊成或反對。
#### Scenario: 改票覆蓋
- Given 甲理事先投「反對」
- When 甲理事在截止前改投「同意」
- Then 計票以「同意」計入

### Requirement: Passing Threshold
通過條件必須（MUST）為「同意票數 ≥ T」。
#### Scenario: 正常通過
- Given N=5，T=3
- When 在截止前同意票到達 3 票
- Then 狀態轉為「已通過」，並立即嘗試執行轉帳

### Requirement: Early Rejection
若在進行中任一時刻判定「剩餘未投票者即使全數同意也無法達標」，系統必須（MUST）立即將提案結案為「已否決」並通知。
#### Scenario: 提前否決
- Given N=5，T=3
- And 當前反對票已達 3 票
- When 系統重新評估可達成性
- Then 立即結案為「已否決」並通知

### Requirement: Timeout Auto-Reject
達到截止時間仍未通過時，系統必須（MUST）自動結案為「已逾時」並通知。
#### Scenario: 逾時否決
- Given 提案距截止已到
- And 同意票 < T
- Then 狀態為「已逾時」並通知

### Requirement: Withdrawal Rule
提案人僅能在「尚無任何投票」前撤案；一旦出現第一張票則必須（MUST）不可撤，系統必須（MUST）回覆原因。
#### Scenario: 撤案被拒
- Given 已有任一投票紀錄
- When 提案人嘗試撤案
- Then 系統拒絕並提示「已有投票，無法撤案」

### Requirement: Execution and Failures
提案達門檻後系統必須（MUST）立即嘗試執行轉帳；成功則最終狀態必須（MUST）為「已執行」。若餘額不足或受款人無效等原因導致失敗，則必須（MUST）標記為「執行失敗」並通知。
#### Scenario: 餘額不足導致執行失敗
- Given 提案已通過並進入執行
- When 理事會帳戶餘額不足
- Then 狀態為「執行失敗」並通知提案人與理事

### Requirement: DM-Only Communications (MVP)
MVP 既有「僅 DM」互動調整為「面板優先 + DM 輔助」：互動入口以 `/council panel` 面板為主；系統仍須（MUST）以 DM 進行建案通知、截止前提醒與結案結果投遞（含個別票揭露）；不得（MUST NOT）在公開頻道發佈摘要或結果（本修改不變更此限制）。

#### Scenario: 面板為主、DM 投遞結果
- GIVEN 有一筆新提案建立
- THEN 系統於理事 DM 投遞投票入口（並/或於面板提供投票區）
- AND 結案後以 DM 投遞結果（含各理事最終投票）

### Requirement: Anonymity then Disclosure
進行中階段必須（MUST）僅顯示合計票數；結案時必須（MUST）揭露各投票者之最終投票。
#### Scenario: 匿名→揭露
- Given 提案進行中
- Then DM/Embed 僅顯示合計票
- And 結案結果 DM 顯示各理事最終投票名單

### Requirement: Concurrency Limit per Guild
同一 guild 的「進行中」提案數量上限必須（MUST）為 5；超過時系統必須（MUST）拒絕新建案並提示。
#### Scenario: 超過上限拒絕建案
- Given 該 guild 已有 5 筆進行中提案
- When 嘗試再建立新提案
- Then 建案被拒，提示已達上限

### Requirement: Reminders
系統必須（MUST）於建案時通知全體理事；並且在截止前 24 小時再次 DM 提醒尚未投票之理事。
#### Scenario: T-24h 提醒未投者
- Given 距離截止時間剩餘 24 小時
- When 尚有未投理事
- Then 只向未投理事發送提醒 DM

### Requirement: Permissions and Configuration
未完成治理設定（理事角色／Council 帳戶等）前，任何治理相關指令必須（MUST）被拒絕並回覆指引；系統必須（MUST）僅允許理事建案與投票。
#### Scenario: 未設定拒絕
- Given 該 guild 尚未完成必要設定
- When 理事嘗試建立提案
- Then 系統拒絕並提示先完成設定

### Requirement: Status Dictionary (Frozen)
系統狀態集合必須（MUST）固定為：`進行中`、`已通過`、`已否決`、`已逾時`、`已撤案`、`執行失敗`、`已執行`；相關日誌與輸出必須（MUST）使用一致字串。
#### Scenario: 狀態轉移一致
- Given 提案達門檻 → 執行成功
- Then 按序呈現「已通過」→「已執行」

### Requirement: Audit & Logging
系統必須（MUST）記錄提案建立者、時間戳、名冊快照（含名單與 N）、門檻 T、每次投票/改票、結案原因、執行結果（含餘額檢查），並且必須（MUST）支援匯出。
#### Scenario: 稽核可追溯
- Given 任一期間匯出請求
- Then 可重建每一提案的完整生命週期事件

### Requirement: Slash Commands 去重（面板優先）
系統必須（MUST）避免提供與「理事會面板」重複之斜線指令；當某功能已可自面板操作時，不得（MUST NOT）再提供對等的斜線指令。允許的治理相關斜線指令限：`/council panel` 與設定類（例如 `/council config_role`）。

#### Scenario: 僅保留面板與設定指令
- **WHEN** 查閱可用的 `/council` 指令
- **THEN** 僅看見 `/council panel` 與設定相關指令，且無撤案/建案/匯出等重複指令

### Requirement: Result Pattern Integration

The system SHALL provide seamless integration between Result<T,E> pattern and traditional exception handling for council operations.

#### Scenario: Dual service registration

- **WHEN** dependency injection container is initialized
- **THEN** both CouncilService and CouncilServiceResult SHALL be registered
- **AND** callers SHALL choose which implementation to use

#### Scenario: Migration path support

- **WHEN** developers want to migrate to Result pattern
- **THEN** CouncilServiceResult SHALL be available as direct replacement
- **AND** migration documentation SHALL be provided

#### Scenario: Error context preservation

- **WHEN** Result errors are converted to exceptions
- **THEN** error context information SHALL be preserved in exception messages
- **AND** structured logging SHALL capture full error details
