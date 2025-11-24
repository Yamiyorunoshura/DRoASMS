# supreme-assembly-panel Specification

## Purpose
TBD - created by archiving change add-supreme-peoples-assembly. Update Purpose after archive.
## Requirements
### Requirement: Supreme Assembly Panel Entry
最高議會面板必須（MUST）提供基於議會成員身分組的權限控制，允許具備相應身分組的人員使用議會立法和審議功能。

#### Scenario: 議會成員開啟面板
- **GIVEN** 使用者具備最高議會成員身分組
- **WHEN** 該使用者執行最高議會面板指令
- **THEN** 系統允許開啟面板並顯示完整議會功能

#### Scenario: 非議會成員被拒
- **GIVEN** 使用者不具備最高議會成員身分組
- **WHEN** 該使用者嘗試開啟最高議會面板
- **THEN** 系統拒絕並提示無權限

### Requirement: Panel Summary (Balance and Members)
面板必須（MUST）在開啟時顯示「最高人民會議帳戶餘額」與「議員名單」。餘額數據來自該 guild 的最高人民會議帳戶；議員名單以目前議員角色的成員為準，至少顯示總人數並列出前 N 名（N 可為 10，避免訊息過長）。

#### Scenario: 面板顯示餘額與議員名單
- **WHEN** 議長或議員在已完成治理設定的 guild 中執行 `/supreme_assembly panel`
- **THEN** 面板上方摘要顯示「餘額：<數值>」與「議員（<人數>）：<前 N 名標記>」

### Requirement: Transfer from Panel
面板必須（MUST）提供轉帳功能，允許授權人員發起轉帳。轉帳目標必須（MUST）能夠正確識別：
- 一般使用者
- 理事會帳戶（透過統一的 JSON 政府架構）
- 政府部門帳戶（透過統一的 JSON 政府架構）
- 常任理事會（透過統一的 JSON 政府架構）

#### Scenario: 轉帳給使用者成功
- **GIVEN** 授權人員在面板點擊「轉帳」
- **AND** 選擇「轉帳給使用者」
- **AND** 從下拉選單選擇使用者
- **AND** 輸入金額>0、用途描述
- **THEN** 系統完成轉帳，更新雙方餘額，回覆成功訊息

#### Scenario: 轉帳給理事會成功
- **GIVEN** 授權人員在面板點擊「轉帳」
- **AND** 選擇「轉帳給理事會」
- **AND** 輸入金額>0、用途描述
- **THEN** 系統正確識別理事會帳戶並完成轉帳

#### Scenario: 轉帳給政府部門成功
- **GIVEN** 授權人員在面板點擊「轉帳」
- **AND** 選擇「轉帳給政府部門」
- **AND** 從下拉選單選擇政府部門（基於 JSON 政府架構）
- **AND** 輸入金額>0、用途描述
- **THEN** 系統正確識別部門帳戶並完成轉帳

#### Scenario: 轉帳給常任理事會成功
- **GIVEN** 授權人員在面板點擊「轉帳」
- **AND** 選擇「轉帳給常任理事會」
- **AND** 輸入金額>0、用途描述
- **THEN** 系統正確識別常任理事會帳戶並完成轉帳

#### Scenario: 轉帳類型選擇
- **WHEN** 授權人員在面板點擊「轉帳」
- **THEN** 顯示轉帳類型選擇面板，包含「轉帳給使用者」、「轉帳給理事會」、「轉帳給政府部門」、「轉帳給常任理事會」等選項

#### Scenario: 部門選擇下拉選單
- **GIVEN** 授權人員選擇「轉帳給政府部門」
- **WHEN** 系統載入可用部門列表
- **THEN** 顯示包含所有已配置政府部門的下拉選單（基於 JSON 政府架構），每個選項顯示部門名稱

### Requirement: Create Proposal from Panel (Speaker Only)
面板必須（MUST）提供「發起表決」操作，僅限議長使用。表決提案必須（MUST）包含提案內容、金額（如適用）、用途描述；成功後須建立提案與名冊快照並以 DM/面板投票入口通知議員。

#### Scenario: 議長發起表決成功
- **GIVEN** 議長在面板點擊「發起表決」
- **AND** 填寫提案內容、金額（如適用）、用途描述
- **THEN** 建立表決提案，鎖定名冊快照與門檻，回覆成功訊息
- **AND** 對全體議員投遞投票入口（DM，且提供面板內投票按鈕）

#### Scenario: 非議長無法發起表決
- **GIVEN** 議員（非議長）在面板中
- **WHEN** 嘗試發起表決
- **THEN** 系統不顯示「發起表決」按鈕或拒絕操作並提示僅限議長

### Requirement: List Active Proposals
最高人民會議面板 SHALL 使用 dpy-paginator 提供流暢的表決提案清單分頁功能，取代現有的手動限制 10 筆記錄的實作方式。

#### Scenario: 表決提案清單分頁導航
- **WHEN** 使用者在最高人民會議面板中查看進行中表決提案時
- **THEN** 系統 SHALL 使用 dpy-paginator 顯示分頁的提案清單
- **AND** 提供上一頁/下一頁按鈕導航
- **AND** 提供頁數下拉選單快速跳轉功能

#### Scenario: 分頁與表決狀態整合
- **WHEN** 表決提案狀態發生變化需要更新面板時
- **THEN** 分頁系統 SHALL 保持當前頁面狀態
- **AND** 自動更新頁面內容以反映最新的提案狀態
- **AND** 重新計算總頁數以反映新增或移除的提案

#### Scenario: 分頁與投票功能整合
- **WHEN** 使用者在分頁中選擇提案並進行投票時
- **THEN** 投票後系統 SHALL 保持使用者當前檢視的頁面
- **AND** 更新該頁面中對應提案的狀態顯示
- **AND** 提供即時的投票結果反饋

### Requirement: Voting from Panel
面板必須（MUST）提供投票功能，允許議員（含議長）對進行中的表決提案投票。投票後必須（MUST）不可改選。

#### Scenario: 投票成功
- **GIVEN** 議員在面板中選擇進行中的表決提案
- **WHEN** 點擊「同意」、「反對」或「棄權」按鈕
- **THEN** 系統記錄投票，更新合計票數，並提示「已投票，無法改選」

#### Scenario: 已投票後無法改選
- **GIVEN** 議員已對某表決提案投票
- **WHEN** 嘗試再次點擊投票按鈕
- **THEN** 系統拒絕並提示「已投票，無法改選」

#### Scenario: 投票按鈕狀態更新
- **GIVEN** 議員已投票
- **WHEN** 查看該表決提案的投票按鈕
- **THEN** 按鈕顯示為已選狀態或禁用狀態，無法再次點擊

### Requirement: Summons from Panel
面板必須（MUST）提供「傳召」功能，僅限議長使用。按下後必須（MUST）出現第二個嵌入訊息面板，詢問使用者是傳召議員還是傳召政府官員。當選擇傳召常任理事時，必須（MUST）發送新面板讓用戶選擇要傳召哪一個或哪些常任理事（可多選）。

#### Scenario: 傳召面板顯示
- **GIVEN** 議長在面板點擊「傳召」
- **WHEN** 系統顯示傳召選項
- **THEN** 出現第二個嵌入訊息面板，包含「傳召議員」和「傳召政府官員」選項

#### Scenario: 傳召議員流程
- **GIVEN** 議長選擇「傳召議員」
- **WHEN** 從下拉選單選擇議員
- **THEN** 系統發送私訊通知被傳召議員，面板記錄傳召歷史

#### Scenario: 傳召常任理事會成員（多選）
- **GIVEN** 議長選擇「傳召政府官員」
- **AND** 選擇「常任理事會成員」選項
- **WHEN** 系統顯示常任理事選擇面板
- **THEN** 顯示包含所有常任理事會成員的下拉選單，支援多選
- **AND** 使用者可以選擇一個或多個常任理事
- **AND** 選擇完成後，系統發送私訊通知所有被選中的常任理事會成員
- **AND** 面板記錄傳召歷史（包含所有被傳召的成員）

#### Scenario: 傳召多個常任理事時通知所有人
- **GIVEN** 議長選擇傳召常任理事
- **AND** 從下拉選單選擇了多個常任理事會成員
- **WHEN** 送出選擇
- **THEN** 系統為每個被選中的成員發送私訊通知
- **AND** 傳召記錄包含所有被傳召成員的資訊

#### Scenario: 傳召其他政府官員流程
- **GIVEN** 議長選擇「傳召政府官員」
- **WHEN** 從下拉選單選擇政府部門領導人或國務院領袖（非常任理事會）
- **THEN** 系統發送私訊通知被傳召官員，面板記錄傳召歷史

#### Scenario: 非議長無法傳召
- **GIVEN** 議員（非議長）在面板中
- **WHEN** 嘗試使用傳召功能
- **THEN** 系統不顯示「傳召」按鈕或拒絕操作並提示僅限議長

### Requirement: Real-time Panel Updates
「最高人民會議面板」在開啟期間必須（MUST）自動反映與本 guild 治理相關事件（建案、投票、結案、狀態變更）。面板為 ephemeral，更新僅對開啟者可見，並於 View 結束（timeout/stop）後停止更新。

#### Scenario: 建案後面板自動出現新提案
- **WHEN** 議長在同一 guild 新建立一筆表決提案
- **THEN** 已開啟的面板下拉清單在數秒內出現該提案

#### Scenario: 投票後合計票數更新
- **GIVEN** 已開啟面板且顯示某進行中表決提案
- **WHEN** 任一議員對該提案投票
- **THEN** 面板中該提案的狀態摘要/合計票數在數秒內更新（仍保持匿名）

#### Scenario: 結案後移出清單或更新狀態
- **WHEN** 表決提案被結案（通過/否決/逾時/撤案）
- **THEN** 面板清單移除該提案或更新為結案狀態摘要

#### Scenario: View 結束即停止更新
- **WHEN** 面板 View 因 timeout 或使用者關閉而結束
- **THEN** 不再接收或套用任何更新

### Requirement: Usage Guide Button
最高人民會議面板必須（MUST）提供「使用指引」按鈕；點擊後以 ephemeral Embed 顯示操作說明（包含：轉帳流程、發起表決、投票規則、傳召功能、即時更新與私密性）。

#### Scenario: 顯示使用指引
- **WHEN** 議長或議員於面板點擊「使用指引」
- **THEN** 回覆一則 ephemeral Embed，內容包含面板可執行之主要操作與限制

### Requirement: Panel Permission Validation
面板各項操作必須（MUST）嚴格遵守權限控制，非授權人員不得看到或執行相關功能。

#### Scenario: 議長專屬功能隱藏
- **WHEN** 議員（非議長）開啟面板
- **THEN** 「發起表決」和「傳召」按鈕不顯示

#### Scenario: 操作權限二次驗證
- **GIVEN** 使用者嘗試執行敏感操作（如發起表決）
- **WHEN** 系統再次驗證使用者權限
- **THEN** 只有具備權限才能繼續操作

### Requirement: Persistent Voting Buttons
面板提供之投票按鈕必須（MUST）以 persistent view 形式註冊，使機器人重啟後仍可對進行中表決提案投票；面板容器為 ephemeral 不持久化。

#### Scenario: 重啟後仍可投票
- **GIVEN** 機器人已重啟
- **WHEN** 議員於 DM 或面板票區點擊投票
- **THEN** 投票按鈕仍可用且記錄結果

### Requirement: Supreme Assembly Group Command Description
系統必須（MUST）提供 `/supreme_assembly` 群組指令，其描述與所有子指令的描述必須（MUST）以中文顯示。

#### Scenario: 群組描述為中文
- **WHEN** 使用者在 Discord 中查看 `/supreme_assembly` 群組指令
- **THEN** 群組的描述文字顯示為中文
- **AND** 所有子指令（`config_speaker_role`、`config_member_role`、`panel`）的描述文字皆為中文

### Requirement: Supreme Assembly Config Commands Description
系統必須（MUST）提供 `/supreme_assembly config_speaker_role` 和 `/supreme_assembly config_member_role` 指令，其描述與所有參數說明必須（MUST）以中文顯示。

#### Scenario: 配置指令描述為中文
- **WHEN** 使用者在 Discord 中查看配置指令
- **THEN** 指令的描述文字顯示為中文
- **AND** 所有參數的描述文字皆為中文

### Requirement: Supreme Assembly Member Role Configuration
最高議會系統必須（MUST）提供議會成員身分組設定功能，允許配置議會成員的權限等級。

#### Scenario: 設定議會成員身分組
- **GIVEN** 系統管理員在最高議會配置中
- **WHEN** 設定議會成員身分組ID
- **THEN** 系統保存身分組配置並更新權限檢查邏輯

#### Scenario: 議會主席身分組權限
- **GIVEN** 系統設定議會主席身分組
- **WHEN** 使用者具備此身分組
- **THEN** 該使用者擁有議會管理的額外權限

### Requirement: Legislative Operations Permission
最高議會面板必須（MUST）提供基於議會成員身分組的立法操作權限控制。

#### Scenario: 立法提案權限檢查
- **GIVEN** 使用者嘗試創建立法提案
- **WHEN** 系統檢查權限
- **THEN** 只有具備最高議會成員身分組的使用者才能創建提案

#### Scenario: 法案審議權限檢查
- **GIVEN** 使用者嘗試參與法案審議
- **WHEN** 系統檢查權限
- **THEN** 只有具備最高議會成員身分組的使用者才能參與審議

#### Scenario: 議會管理權限檢查
- **GIVEN** 使用者嘗試執行議會管理操作
- **WHEN** 系統檢查權限
- **THEN** 只有具備議會主席身分組的使用者才能執行管理操作
