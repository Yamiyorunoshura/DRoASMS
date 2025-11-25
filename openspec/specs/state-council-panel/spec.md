# state-council-panel Specification

## Purpose
TBD - created by archiving change add-dept-to-user-transfer-button. Update Purpose after archive.
## Requirements
### Requirement: Department To User Transfer From Panel
面板必須（MUST）提供「部門 → 使用者」轉帳功能。授權對象為：具有來源部門權限之人員或國務院領袖；受款人可為任意使用者（包含執行者本人）。所有轉帳相關的顯示文字必須（MUST）使用該 guild 配置的貨幣名稱和圖示（若未設定則使用預設值「點」和空字串）。

#### Scenario: 部門頁面自動設置來源部門
- GIVEN 使用者具有該部門權限
- WHEN 在該部門頁面點擊「轉帳給使用者」
- THEN 系統自動將來源部門設置為當前面板部門，無需手動選擇

#### Scenario: 總覽頁面選擇來源部門
- GIVEN 使用者為國務院領袖或具備部門權限
- WHEN 在總覽頁面點擊「轉帳給使用者」
- THEN 系統顯示部門選擇下拉選單供選擇來源部門

#### Scenario: 部門領導轉帳給一般使用者成功
- GIVEN 使用者擁有「來源部門」權限
- WHEN 在該部門頁點擊「轉帳給使用者」，選擇受款人並填寫金額與理由（>0）
- THEN 系統完成轉帳，來源為該部門政府帳戶、目標為受款人個人帳戶，並於面板回覆成功訊息
- AND 成功訊息使用配置的貨幣名稱和圖示

#### Scenario: 國務院領袖跨部門撥款成功
- GIVEN 使用者為國務院領袖
- WHEN 在面板（總覽或任一部門頁）發起「部門 → 使用者」轉帳
- THEN 系統允許選擇任一部門作為來源並完成轉帳

#### Scenario: 無權限被拒
- GIVEN 使用者不具來源部門權限且非國務院領袖
- WHEN 嘗試送出轉帳
- THEN 系統拒絕並提示無權限

#### Scenario: 可轉帳至本人
- GIVEN 授權使用者
- WHEN 將受款人指定為自身
- THEN 不因 initiator==target 檢核被擋（來源為部門帳戶，目標為個人帳戶）

#### Scenario: 部門轉帳給使用者訊息使用配置的貨幣名稱和圖示
- GIVEN 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- WHEN 執行部門轉帳給使用者
- THEN 成功訊息顯示「已轉帳 X 金幣 🪙 給...」而非「已轉帳 X 幣 給...」

### Requirement: Usage Guide Button
國務院面板必須（MUST）提供「使用指引」按鈕；點擊後以 ephemeral Embed 顯示依目前頁面（總覽或各部門）而異之操作說明。

#### Scenario: 總覽顯示指引
- **GIVEN** 使用者位於「總覽」頁
- **WHEN** 點擊「使用指引」
- **THEN** 回覆 ephemeral Embed，說明導航、部門轉帳、匯出資料（限領袖）、設定部門領導等

#### Scenario: 部門頁顯示指引
- **GIVEN** 使用者位於任一部門頁（內政/財政/國土安全/中央銀行/法務部）
- **WHEN** 點擊「使用指引」
- **THEN** 回覆 ephemeral Embed，說明該部門之主要操作（如福利發放、稅款徵收、身分管理、貨幣發行、嫌犯管理）與限制

### Requirement: State Council Panel Entry
系統必須（MUST）提供 `/state_council panel` 指令，允許國務院領袖和授權人員開啟國務院面板，以 ephemeral 訊息承載互動元件。

#### Scenario: 領袖開啟面板成功
- WHEN 國務院領袖在已完成設定的 guild 中執行 `/state_council panel`
- THEN 回覆一則 ephemeral 訊息並附上完整的國務院面板

#### Scenario: 部門授權人員開啟面板
- WHEN 具備部門權限的人員執行 `/state_council panel`
- THEN 回覆面板但僅顯示授權部門的功能頁籤

#### Scenario: 未設定被拒
- WHEN 國務院尚未完成領袖設定
- THEN 系統拒絕並提示執行 `/state_council config_leader`

### Requirement: Multi-Department Tab Interface
面板必須（MUST）採用分頁設計，第一頁為總覽，後續頁面為各部門專用功能。每個頁籤必須（MUST）根據使用者權限動態顯示或隱藏。

#### Scenario: 總覽頁面顯示
- WHEN 使用者開啟面板
- THEN 第一頁顯示國務院摘要、各部門帳戶餘額和快速狀態

#### Scenario: 部門頁籤權限控制
- WHEN 系統檢查使用者權限
- THEN 僅顯示具備權限的部門頁籤

### Requirement: Leader Configuration Modal
面板必須（MUST）提供國務院領袖設定功能，允許管理者指定領袖並初始化相關政府帳戶。

#### Scenario: 設定國務院領袖
- GIVEN 管理員在面板中點擊設定領袖
- AND 選擇有效的使用者作為領袖
- THEN 系統建立領袖配置和所有部門帳戶（包含法務部）

### Requirement: Department Role Permission Setting
面板必須（MUST）允許國務院領袖設定各部門所需的身分組，以實現細粒度的權限控制。

#### Scenario: 配置部門權限
- GIVEN 國務院領袖在總覽頁面選擇權限設定
- WHEN 為每個部門選擇對應的身分組
- THEN 系統保存權限配置並更新面板存取控制

### Requirement: Interior Affairs Tab - Welfare Management
內政部頁籤必須（MUST）提供福利發放設定功能，包括金額設定、週期選擇和發放狀態監控。

#### Scenario: 設定定期福利
- GIVEN 具備內政部權限的使用者在內政部頁籤
- WHEN 設定福利金額和發放週期
- THEN 系統更新配置並開始定期發排程

#### Scenario: 查看福利發放記錄
- GIVEN 內政部頁籤開啟
- THEN 顯示最近的福利發放記錄和統計資訊

### Requirement: Finance Ministry Tab - Tax Management
財政部頁籤必須（MUST）提供所得稅設定功能，包括稅率設定、計算週期選擇和稅收統計。

#### Scenario: 設定所得稅參數
- GIVEN 具備財政部權限的使用者在財政部頁籤
- WHEN 設定稅率和計算週期
- THEN 系統更新稅收配置

#### Scenario: 查看稅收統計
- GIVEN 財政部頁籤開啟
- THEN 顯示稅收統計、最近徵收記錄和預計下次徵收時間

### Requirement: Homeland Security Tab - Citizenship Management
國土安全部頁籤必須（MUST）提供逮捕功能，包括使用下拉選單選擇要逮捕的人、填寫逮捕原因，以及自動移除公民身分組並掛上嫌犯身分組。

#### Scenario: 逮捕流程啟動
- **GIVEN** 具備國土安全部權限的使用者在國土安全部頁籤
- **WHEN** 點擊「逮捕人員」按鈕
- **THEN** 系統發送新的嵌入訊息，包含使用者下拉選單和逮捕原因輸入欄位

#### Scenario: 選擇要逮捕的人並填寫原因
- **GIVEN** 使用者已點擊「逮捕人員」按鈕
- **AND** 系統顯示逮捕選擇介面
- **WHEN** 從下拉選單選擇目標使用者
- **AND** 填寫逮捕原因
- **AND** 送出表單
- **THEN** 系統驗證必填欄位（目標使用者和逮捕原因）
- **AND** 執行逮捕操作

#### Scenario: 逮捕操作自動處理身分組
- **GIVEN** 使用者已選擇目標並填寫原因
- **AND** 公民身分組和嫌犯身分組已設定
- **WHEN** 送出逮捕表單
- **THEN** 系統自動移除目標使用者的公民身分組
- **AND** 系統自動為目標使用者掛上嫌犯身分組
- **AND** 記錄身分變更操作（包含逮捕原因）

#### Scenario: 逮捕原因為必填
- **GIVEN** 使用者已選擇目標使用者
- **WHEN** 未填寫逮捕原因即嘗試送出
- **THEN** 系統拒絕操作並提示必須填寫逮捕原因

#### Scenario: 查看身分管理記錄
- **GIVEN** 國土安全部頁籤開啟
- **THEN** 顯示最近的身分變更記錄和統計

### Requirement: Central Bank Tab - Monetary Policy
中央銀行頁籤必須（MUST）提供貨幣政策功能，包括貨幣增發、貨幣供給量監控和相關統計。所有與貨幣相關的顯示文字必須（MUST）使用該 guild 配置的貨幣名稱和圖示（若未設定則使用預設值「點」和空字串）。

#### Scenario: 執行貨幣增發
- GIVEN 具備中央銀行權限的使用者在中央銀行頁籤
- WHEN 輸入增發金額並確認操作
- THEN 系統增加貨幣供給並更新帳戶餘額
- AND 成功訊息使用配置的貨幣名稱和圖示

#### Scenario: 查看貨幣統計
- GIVEN 中央銀行頁籤開啟
- THEN 顯示貨幣供給量、增發記錄和經濟指標
- AND 所有金額顯示使用配置的貨幣名稱和圖示

#### Scenario: 貨幣增發訊息使用配置的貨幣名稱和圖示
- GIVEN 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- WHEN 中央銀行執行貨幣增發
- THEN 成功訊息顯示「貨幣發行成功！增發 X 金幣 🪙」而非「貨幣發行成功！增發 X 幣」

#### Scenario: 面板統計使用配置的貨幣名稱和圖示
- GIVEN 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- WHEN 使用者查看中央銀行頁籤的統計資料
- THEN 顯示「本月貨幣發行：X 金幣 🪙」而非「本月貨幣發行：X 幣」

### Requirement: Justice Department Tab - Suspect Management
法務部頁籤必須（MUST）提供嫌犯管理功能，包括嫌犯列表顯示、詳情檢視、起訴和撤銷起訴操作，並確保只有法務部領導人能夠執行相關操作。

#### Scenario: 嫌犯列表載入
- **GIVEN** 具備法務部權限的使用者在法務部頁籤
- **WHEN** 頁面載入時
- **THEN** SHALL顯示所有被逮捕且未被釋放的嫌犯列表
- **AND** 每個嫌犯SHALL顯示：成員名稱、逮捕時間、逮捕人、當前狀態
- **AND** 列表SHALL支援分頁，每頁10條記錄

#### Scenario: 查看嫌犯詳情
- **GIVEN** 具備法務部權限的使用者在法務部頁籤的嫌犯列表
- **WHEN** 點擊特定嫌犯的"查看詳情"按鈕
- **THEN** SHALL顯示該嫌犯的完整資訊
- **AND** SHALL包含：逮捕原因、逮捕時間、逮捕人、起訴狀態、起訴時間、起訴人

#### Scenario: 法務部起訴嫌犯
- **GIVEN** 具備法務部權限的使用者
- **AND** 嫌犯狀態為 "detained"
- **WHEN** 點擊"起訴"按鈕並輸入起訴原因
- **Then:** 系統SHALL將嫌犯狀態更新為 "charged"
- **And:** SHALL記錄起訴人ID和起訴時間
- **And:** SHALL記錄起訴原因到審計日誌
- **And:** SHALL顯示成功訊息

#### Scenario: 法務部撤銷起訴
- **GIVEN** 具備法務部權限的使用者
- **AND** 嫌犯狀態為 "charged"
- **WHEN** 點擊"撤銷起訴"按鈕
- **Then:** 系統SHALL將嫌犯狀態更新為 "detained"
- **And:** SHALL清空起訴相關欄位
- **And:** SHALL記錄操作到審計日誌
- **And:** SHALL顯示成功訊息

#### Scenario: 非法務部人員嘗試訪問
- **GIVEN** 使用者沒有法務部領導人身份組
- **WHEN** 嘗試訪問法務部分頁功能
- **Then:** 系統SHALL拒絕訪問
- **And:** SHALL顯示錯誤訊息："您沒有權限訪問法務部功能"

#### Scenario: 嘗試起訴已起訴的嫌犯
- **GIVEN** 嫌犯狀態已為 "charged"
- **WHEN** 嘗試再次起訴
- **Then:** 系統SHALL拒絕操作
- **And:** SHALL顯示錯誤訊息："該嫌犯已被起訴"

### Requirement: Account Transfer Between Departments
面板必須（MUST）提供部門間轉帳功能，允許授權人員在部門政府帳戶間移動資金。所有轉帳相關的顯示文字必須（MUST）使用該 guild 配置的貨幣名稱和圖示（若未設定則使用預設值「點」和空字串）。

#### Scenario: 部門間轉帳
- GIVEN 具備轉帳權限的使用者
- WHEN 在面板中選擇轉出部門、轉入部門和金額
- THEN 系統驗證權限並執行轉帳交易
- AND 成功訊息使用配置的貨幣名稱和圖示

#### Scenario: 部門轉帳訊息使用配置的貨幣名稱和圖示
- GIVEN 該 guild 已設定貨幣名稱為「金幣」、圖示為「🪙」
- WHEN 執行部門間轉帳
- THEN 成功訊息顯示「已轉帳 X 金幣 🪙」而非「已轉帳 X 幣」

### Requirement: Real-time Panel Updates
國務院面板在開啟期間必須（MUST）自動反映與本 guild 相關的國務院事件，包括權限變更、福利發放、稅收徵收、身分變更和帳戶變動。

#### Scenario: 福利發放後面板更新
- WHEN 系統執行定期福利發放
- THEN 內政部頁籤的統計資料在數秒內更新

#### Scenario: 權限變更後頁籤顯示更新
- WHEN 國務院領袖更新部門權限設定
- THEN 相關使用者的面板頁籤顯示即時更新

### Requirement: Export and Audit Functions
面板必須（MUST）提供稽核匯出功能，允許具備權限的人員匯出國務院操作記錄和統計資料。

#### Scenario: 匯出操作記錄
- GIVEN 具備稽核權限的使用者
- WHEN 在面板中選擇匯出期間和格式
- THEN 系統產生並下載對應的記錄檔案

### Requirement: Panel Permission Validation
面板各項操作必須（MUST）嚴格遵守權限控制，非授權人員不得看到或執行相關功能。

#### Scenario: 非授權功能隱藏
- WHEN 使用者不具備某部門權限
- THEN 該部門頁籤完全不顯示

#### Scenario: 操作權限二次驗證
- GIVEN 使用者嘗試執行敏感操作
- WHEN 系統再次驗證使用者權限
- THEN 只有具備權限才能繼續操作

### Requirement: UI Consistency Verification
轉帳給使用者功能必須（MUST）在所有部門頁面和總覽頁面保持一致的用戶體驗。

#### Scenario: 按鈕位置一致性
- GIVEN 使用者在任何面板頁面
- THEN 「轉帳給使用者」按鈕應顯示在相似位置

#### Scenario: 操作流程一致性
- GIVEN 使用者在任何頁面發起轉帳
- THEN 操作步驟和介面應保持一致，僅來源部門設置邏輯不同

### Requirement: Government Account Synchronization on Panel Open
當國務院面板開啟時，系統必須（MUST）檢查所有必需的政府帳戶是否存在。若配置存在但帳戶缺失，系統必須（MUST）自動建立缺失的政府帳戶，確保面板功能正常運作。

#### Scenario: 配置存在但帳戶缺失時自動建立
- **GIVEN** 國務院領袖配置已存在
- **AND** 部分或全部政府帳戶缺失
- **WHEN** 使用者開啟國務院面板
- **THEN** 系統自動建立缺失的政府帳戶，使用配置中記錄的 account_id（如存在）或推導方法產生一致的 account_id
- **AND** 建立的帳戶餘額應從經濟系統同步（如經濟帳戶存在）或設為 0（如不存在）

#### Scenario: 所有帳戶存在時無需建立
- **GIVEN** 國務院領袖配置已存在
- **AND** 所有四個部門的政府帳戶都已存在
- **WHEN** 使用者開啟國務院面板
- **THEN** 系統不執行帳戶建立操作，直接顯示面板

#### Scenario: 使用配置中的 account_id 建立帳戶
- **GIVEN** 國務院領袖配置已存在且記錄了各部門的 account_id
- **AND** 內政部帳戶缺失
- **WHEN** 系統自動建立內政部帳戶
- **THEN** 使用配置中記錄的 `internal_affairs_account_id` 作為新帳戶的 account_id

#### Scenario: 配置中 account_id 缺失時使用推導方法
- **GIVEN** 國務院領袖配置已存在但未記錄部門 account_id
- **AND** 財政部帳戶缺失
- **WHEN** 系統自動建立財政部帳戶
- **THEN** 使用 `derive_department_account_id` 方法產生一致的 account_id

#### Scenario: 同步經濟系統餘額
- **GIVEN** 政府帳戶缺失但經濟系統中存在對應的帳戶餘額
- **WHEN** 系統自動建立政府帳戶
- **THEN** 建立的帳戶餘額應與經濟系統中的餘額一致

#### Scenario: 經濟帳戶不存在時設為零餘額
- **GIVEN** 政府帳戶缺失且經濟系統中不存在對應帳戶
- **WHEN** 系統自動建立政府帳戶
- **THEN** 建立的帳戶餘額設為 0

#### Scenario: 並發開啟面板時避免重複建立
- **GIVEN** 多個使用者同時開啟國務院面板
- **AND** 內政部帳戶缺失
- **WHEN** 系統同時處理多個面板開啟請求
- **THEN** 使用資料庫的 ON CONFLICT 機制確保帳戶僅建立一次，所有請求最終看到一致的帳戶狀態

#### Scenario: 部分帳戶缺失時建立所有缺失帳戶
- **GIVEN** 國務院領袖配置已存在
- **AND** 內政部和財政部帳戶存在，但國土安全部和中央銀行帳戶缺失
- **WHEN** 使用者開啟國務院面板
- **THEN** 系統僅建立國土安全部和中央銀行帳戶，保留現有帳戶不變

#### Scenario: 帳戶建立失敗時的降級處理
- **GIVEN** 國務院領袖配置已存在
- **AND** 帳戶建立過程中發生錯誤（如資料庫連線失敗）
- **WHEN** 使用者開啟國務院面板
- **THEN** 系統記錄錯誤日誌但不阻止面板開啟
- **AND** 面板顯示錯誤訊息提示帳戶同步失敗，建議使用者重試或聯繫管理員

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

### Requirement: Department Head Role Definition
國務院系統必須（MUST）為每個部門定義部門首長身分組，並基於這些身分組提供對應的權限控制。

#### Scenario: 內政部首長身分組權限
- **GIVEN** 系統設定內政部首長身分組
- **WHEN** 使用者具備此身分組
- **THEN** 該使用者能夠使用內政部的福利發放、公民管理等所有功能
- **AND** 無法使用財政部、國土安全部、中央銀行的功能

#### Scenario: 財政部首長身分組權限
- **GIVEN** 系統設定財政部首長身分組
- **WHEN** 使用者具備此身分組
- **THEN** 該使用者能夠使用財政部的稅務管理、會計核算等所有功能
- **AND** 無法使用其他部門的功能

#### Scenario: 國土安全部首長身分組權限
- **GIVEN** 系統設定國土安全部首長身分組
- **WHEN** 使用者具備此身分組
- **THEN** 該使用者能夠使用國土安全部的身分管理、安全監控等所有功能
- **AND** 無法使用其他部門的功能

#### Scenario: 中央銀行首長身分組權限
- **GIVEN** 系統設定中央銀行首長身分組
- **WHEN** 使用者具備此身分組
- **THEN** 該使用者能夠使用中央銀行的貨幣政策、金融監管等所有功能
- **AND** 無法使用其他部門的功能

#### Scenario: 法務部首長身分組權限
- **GIVEN** 系統設定法務部首長身分組
- **WHEN** 使用者具備此身分組
- **THEN** 該使用者能夠使用法務部的嫌犯管理、起訴操作等所有功能
- **AND** 無法使用其他部門的功能

### Requirement: Enhanced Department Permission Validation
國務院面板必須（MUST）在每次操作時都嚴格驗證使用者的部門首長身分組權限，確保只有授權人員能夠執行對應操作。

#### Scenario: 福利發放權限檢查
- **GIVEN** 使用者嘗試執行福利發放操作
- **WHEN** 系統檢查權限
- **THEN** 只有具備內政部首長身分組的使用者才能執行此操作

#### Scenario: 稅務管理權限檢查
- **GIVEN** 使用者嘗試執行稅務管理操作
- **WHEN** 系統檢查權限
- **THEN** 只有具備財政部首長身分組的使用者才能執行此操作

#### Scenario: 身分管理權限檢查
- **GIVEN** 使用者嘗試執行身分管理操作
- **WHEN** 系統檢查權限
- **THEN** 只有具備國土安全部首長身分組的使用者才能執行此操作

#### Scenario: 貨幣政策權限檢查
- **GIVEN** 使用者嘗試執行貨幣政策操作
- **WHEN** 系統檢查權限
- **THEN** 只有具備中央銀行首長身分組的使用者才能執行此操作

#### Scenario: 法務部嫌犯管理權限檢查
- **GIVEN** 使用者嘗試執行嫌犯管理操作
- **WHEN** 系統檢查權限
- **THEN** 只有具備法務部首長身分組的使用者才能執行此操作

### Requirement: Interior Affairs Tab - Business License Management

內政部頁籤必須（MUST）提供商業許可管理功能，包括發放許可、查看許可列表和撤銷許可。

#### Scenario: 顯示商業許可管理區塊

- **GIVEN** 具備內政部權限的使用者在內政部頁籤
- **WHEN** 頁面載入時
- **THEN** 顯示「商業許可管理」區塊，包含「發放許可」和「查看許可」按鈕

#### Scenario: 發放許可按鈕觸發 Modal

- **GIVEN** 使用者在內政部頁籤的商業許可管理區塊
- **WHEN** 點擊「發放許可」按鈕
- **THEN** 系統顯示許可發放 Modal，包含目標用戶選擇、許可類型下拉選單和有效期設定

#### Scenario: 許可發放 Modal 提交成功

- **GIVEN** 使用者已填寫許可發放 Modal 的所有必填欄位
- **WHEN** 點擊確認按鈕
- **THEN** 系統驗證輸入資料並發放許可
- **AND** 顯示成功訊息並關閉 Modal

#### Scenario: 許可發放驗證失敗

- **GIVEN** 使用者提交許可發放 Modal
- **AND** 輸入資料不完整或無效
- **WHEN** 系統驗證輸入
- **THEN** 顯示錯誤訊息並保持 Modal 開啟

### Requirement: Business License List View

內政部頁籤必須（MUST）提供商業許可列表檢視功能，支援分頁顯示和狀態篩選。

#### Scenario: 查看許可列表

- **GIVEN** 具備內政部權限或國務院領袖身分的使用者
- **WHEN** 點擊「查看許可」按鈕
- **THEN** 系統顯示商業許可列表嵌入訊息
- **AND** 每頁顯示最多 10 筆記錄
- **AND** 提供上一頁/下一頁導航按鈕

#### Scenario: 許可列表顯示資訊

- **GIVEN** 許可列表已載入
- **THEN** 每筆記錄顯示：用戶名稱、許可類型、核發日期、到期日期、狀態徽章

#### Scenario: 空列表提示

- **GIVEN** 該 guild 尚無任何商業許可記錄
- **WHEN** 使用者查看許可列表
- **THEN** 顯示「目前沒有商業許可記錄」提示訊息

#### Scenario: 篩選許可狀態

- **GIVEN** 許可列表顯示中
- **WHEN** 使用者從狀態篩選下拉選單選擇「有效」「已過期」或「已撤銷」
- **THEN** 列表僅顯示符合該狀態的記錄

### Requirement: Business License Revocation UI

內政部頁籤必須（MUST）提供從許可列表撤銷許可的功能。

#### Scenario: 撤銷按鈕顯示

- **GIVEN** 許可列表中有狀態為「有效」的許可記錄
- **THEN** 該記錄旁顯示「撤銷」按鈕

#### Scenario: 撤銷確認 Modal

- **GIVEN** 使用者點擊許可記錄旁的「撤銷」按鈕
- **WHEN** 系統處理點擊事件
- **THEN** 顯示撤銷確認 Modal，包含撤銷原因輸入欄位

#### Scenario: 確認撤銷許可

- **GIVEN** 使用者已在撤銷確認 Modal 填寫撤銷原因
- **WHEN** 點擊確認按鈕
- **THEN** 系統執行撤銷操作
- **AND** 顯示成功訊息
- **AND** 更新列表顯示

#### Scenario: 取消撤銷操作

- **GIVEN** 撤銷確認 Modal 已開啟
- **WHEN** 使用者點擊取消按鈕
- **THEN** Modal 關閉且不執行任何操作

### Requirement: Business License Permission Validation

商業許可相關操作必須（MUST）嚴格驗證使用者權限，確保只有內政部領導人或國務院領袖能執行操作。

#### Scenario: 非授權人員無法看到商業許可管理

- **GIVEN** 使用者不具備內政部首長身分組且非國務院領袖
- **WHEN** 開啟國務院面板
- **THEN** 內政部頁籤不顯示，或頁籤中不顯示商業許可管理功能

#### Scenario: 發放操作權限二次驗證

- **GIVEN** 使用者嘗試提交許可發放請求
- **WHEN** 系統處理請求
- **THEN** 再次驗證使用者具備內政部權限後才執行發放

#### Scenario: 撤銷操作權限二次驗證

- **GIVEN** 使用者嘗試撤銷商業許可
- **WHEN** 系統處理請求
- **THEN** 再次驗證使用者具備內政部權限後才執行撤銷

### Requirement: Administrative Management Panel

國務院面板必須（MUST）提供「行政管理」按鈕，點擊後發送新的 ephemeral 嵌入訊息面板，用於管理各部門領導人的身分組設定。此功能僅限國務院領袖使用。

#### Scenario: 行政管理按鈕僅限領袖可見

- **GIVEN** 使用者開啟國務院面板
- **AND** 使用者為國務院領袖
- **WHEN** 總覽頁面載入時
- **THEN** 顯示「行政管理」按鈕

#### Scenario: 非領袖無法看到行政管理按鈕

- **GIVEN** 使用者開啟國務院面板
- **AND** 使用者不是國務院領袖（僅為部門授權人員）
- **WHEN** 總覽頁面載入時
- **THEN** 不顯示「行政管理」按鈕

#### Scenario: 點擊行政管理按鈕發送新嵌入訊息

- **GIVEN** 國務院領袖在總覽頁面
- **WHEN** 點擊「行政管理」按鈕
- **THEN** 系統發送新的 ephemeral 嵌入訊息
- **AND** 嵌入訊息包含所有部門的當前領導人設定狀態
- **AND** 嵌入訊息附帶行政管理互動元件（下拉選單）

#### Scenario: 行政管理面板顯示當前部門領導人狀態

- **GIVEN** 行政管理面板已開啟
- **AND** 內政部領導人身分組已設定為「內政部長」
- **AND** 財政部領導人身分組未設定
- **WHEN** 面板載入時
- **THEN** 嵌入訊息顯示「內政部：@內政部長」
- **AND** 嵌入訊息顯示「財政部：未設定」

#### Scenario: 行政管理面板提供部門選擇下拉選單

- **GIVEN** 行政管理面板已開啟
- **WHEN** 查看互動元件
- **THEN** 顯示部門選擇下拉選單
- **AND** 選項包含：內政部、財政部、國土安全部、中央銀行、法務部

#### Scenario: 選擇部門後可選擇領導人身分組

- **GIVEN** 行政管理面板已開啟
- **AND** 使用者從部門下拉選單選擇「內政部」
- **WHEN** 系統處理選擇
- **THEN** 顯示領導人身分組選擇下拉選單（RoleSelect）

#### Scenario: 設定部門領導人成功

- **GIVEN** 使用者已選擇部門「內政部」
- **AND** 使用者從身分組選擇器選擇「@內政部長」身分組
- **WHEN** 系統處理設定
- **THEN** 系統儲存部門領導人設定
- **AND** 顯示成功訊息「已更新 內政部 領導人身分組為 @內政部長」
- **AND** 嵌入訊息內容刷新以反映新設定

#### Scenario: 清除部門領導人設定

- **GIVEN** 使用者已選擇部門「財政部」
- **AND** 使用者在身分組選擇器中不選擇任何身分組（min_values=0）
- **WHEN** 系統處理設定
- **THEN** 系統清除該部門的領導人設定
- **AND** 顯示成功訊息「已更新 財政部 領導人身分組為 未設定」
- **AND** 嵌入訊息內容刷新顯示「財政部：未設定」

### Requirement: Administrative Management Panel Real-time Updates

行政管理面板必須（MUST）支援實時更新，當部門領導人設定變更時自動刷新顯示內容。

#### Scenario: 設定變更後面板自動刷新

- **GIVEN** 行政管理面板已開啟
- **AND** 面板已訂閱 State Council 事件
- **WHEN** 部門領導人設定變更事件發生
- **THEN** 嵌入訊息內容自動刷新以顯示最新的部門領導人狀態

#### Scenario: 面板超時後取消事件訂閱

- **GIVEN** 行政管理面板已開啟
- **AND** 面板已訂閱 State Council 事件
- **WHEN** 面板因超時被停止
- **THEN** 系統取消事件訂閱
- **AND** 釋放相關資源
