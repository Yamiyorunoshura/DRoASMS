# Capability: Council Governance — Transfers MVP

## ADDED Requirements

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
MVP 階段所有通知與互動必須（MUST）僅透過理事 DM 完成（包含建案通知、投票、提醒、結案結果）；不得（MUST NOT）在公開頻道發佈摘要或結果。
#### Scenario: 建案與結果皆以 DM 投遞
- Given 有一筆新提案建立
- Then 系統以 DM 發送投票 Embed 給全體理事
- And 結案後以 DM 發送結果（含各理事最終投票）

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

### Requirement: Admin Exports via Slash Commands
系統必須（MUST）提供管理者觸發之匯出指令，支援 CSV 與 JSON，範圍可指定期間；輸出必須（MUST）包含提案資訊、名冊快照、投票紀錄、結案原因與執行結果。
#### Scenario: 匯出 JSON 成功
- Given 管理者具備相應權限
- When 以匯出指令請求 JSON 格式與期間
- Then 產出對應資料並提供下載/傳送

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
