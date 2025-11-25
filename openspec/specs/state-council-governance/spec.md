# state-council-governance Specification

## Purpose
TBD - created by archiving change add-state-council. Update Purpose after archive.
## Requirements
### Requirement: State Council Leader Configuration
每個 guild 必須（MUST）可以設定一位國務院領袖，領袖具備所有部門的完整管理權限。系統必須（MUST）提供指令進行領袖設定，並領袖必須（MUST）可以配置各部門所需的身分組權限。

#### Scenario: 設定國務院領袖成功
- Given 管理員執行設定指令
- And 指定有效的使用者作為國務院領袖
- Then 系統建立領袖配置並建立相關政府帳戶

#### Scenario: 領袖配置部門權限
- Given 國務院領袖開啟面板設定介面
- When 為各部門設定所需身分組
- Then 系統保存權限配置並限制非授權人員存取

### Requirement: Independent Government Accounts per Department
每個部門必須（MUST）擁有獨立的政府帳戶，包括國務院領袖帳戶、內政部帳戶、財政部帳戶、國土安全部帳戶和中央銀行帳戶。所有帳戶必須（MUST）與普通使用者帳戶互通，支援轉帳功能。

#### Scenario: 部門帳戶初始化
- Given 國務院領袖完成設定
- When 系統初始化國務院系統
- Then 自動建立五個獨立政府帳戶並記錄帳戶ID

#### Scenario: 部門間轉帳功能
- Given 具備轉帳權限的人員
- When 在面板中執行部門間轉帳
- Then 系統驗證權限並執行轉帳交易

### Requirement: Department Role-based Access Control
每個部門的功能必須（MUST）根據設定的身分組進行權限控制。只有具備相關身分組的使用者才能在面板中看到並使用對應的部門功能。國務院領袖必須（MUST）可以存取所有部門功能。

#### Scenario: 身分組權限驗證
- Given 使用者開啟國務院面板
- When 系統檢查使用者身分組
- Then 僅顯示具備權限的部門功能頁籤

#### Scenario: 領袖全權限存取
- Given 國務院領袖開啟面板
- Then 顯示所有部門功能頁籤

### Requirement: Interior Affairs - Welfare Distribution System
內政部必須（MUST）提供福利發放功能，支援設定定期（每月/每週/每日）發放金額，系統必須（MUST）自動根據設定執行發放作業。

#### Scenario: 設定定期福利發放
- Given 具備內政部權限的人員
- When 在面板中設定福利金額和發放週期
- Then 系統保存配置並開始定期發放

#### Scenario: 自動福利發放執行
- Given 到達設定的發放時間
- When 系統執行定期發放任務
- Then 從內政部帳戶向符合資格的使用者發放福利

### Requirement: Finance Ministry - Income Tax System
財政部必須（MUST）提供所得稅功能，支援計算每人在設定期間（每月/每週/每日）的所得並按設定稅率徵收。系統必須（MUST）自動執行稅收計算和扣繳。

#### Scenario: 設定所得稅參數
- Given 具備財政部權限的人員
- When 在面板中設定稅率和計算週期
- Then 系統保存稅收配置

#### Scenario: 自動所得稅徵收
- Given 到達稅收計算時間
- When 系統計算使用者所得並徵收稅款
- Then 從使用者帳戶扣除稅款並存入財政部帳戶

### Requirement: Homeland Security - Citizenship Management
國土安全部必須（MUST）提供身分管理功能，可以移除被選中使用者的公民身分組並掛上疑犯身分。疑犯身分組必須（MUST）由管理員透過指令預先配置。公民身分組必須（MUST）由管理員透過指令預先配置。

#### Scenario: 移除公民身分
- **GIVEN** 具備國土安全部權限的人員
- **AND** 公民身分組和嫌犯身分組已設定
- **WHEN** 在面板中選擇目標使用者並執行逮捕操作
- **THEN** 系統自動移除使用者的公民身分組並掛上嫌犯身分組
- **AND** 記錄身分變更操作

#### Scenario: 疑犯身分設定驗證
- **GIVEN** 管理員未設定疑犯身分組或公民身分組
- **WHEN** 嘗試執行逮捕操作
- **THEN** 系統拒絕操作並提示需要先設定對應的身分組

### Requirement: Central Bank - Money Issuance
中央銀行必須（MUST）提供貨幣增發功能，允許授權人員增加貨幣供給量並存入中央銀行帳戶。

#### Scenario: 執行貨幣增發
- Given 具備中央銀行權限的人員
- When 在面板中輸入增發金額並確認
- Then 系統增加指定金額至中央銀行帳戶

#### Scenario: 增發金額驗證
- Given 輸入的增發金額無效（負數或超限）
- When 嘗試執行增發
- Then 系統拒絕操作並提示金額錯誤

### Requirement: State Council Configuration Validation
在國務院未完成基本設定前（領袖、疑犯身分組），任何治理相關功能必須（MUST）被拒絕並顯示設定指引。

#### Scenario: 未完成設定拒絕操作
- Given 國務院尚未完成基本設定
- When 嘗試使用任何部門功能
- Then 系統拒絕並提示完成基本設定

### Requirement: Audit and Transaction Logging
系統必須（MUST）記錄所有國務院相關操作，包括領袖設定、權限配置、福利發放、稅收徵收、身分變更、貨幣增發和帳戶轉帳，並支援匯出功能。

#### Scenario: 操作記錄保存
- Given 任何國務院操作執行
- Then 系統詳細記錄操作者、時間、內容和結果

#### Scenario: 稽核資料匯出
- Given 具備稽核權限的人員請求匯出
- Then 系統產出指定期間的操作記錄檔案

### Requirement: Unified Department Identification Format
系統必須（MUST）提供統一的政府部門識別格式，以 JSON 格式定義部門元資料，包含識別碼、顯示名稱、帳戶代碼等資訊。此格式必須（MUST）支援動態載入與擴展，無需在代碼中硬編碼部門列表。

#### Scenario: 部門定義載入
- GIVEN 系統啟動時存在部門定義 JSON 檔案
- WHEN 應用載入部門定義
- THEN 系統從配置載入所有部門資訊並快取於記憶體
- AND 部門定義包含以下必要欄位：id（唯一識別碼）、name（顯示名稱）、code（數值代碼）

#### Scenario: 部門查詢介面
- GIVEN 部門定義已載入
- WHEN 服務層需要查詢部門資訊
- THEN 系統提供統一的查詢介面，可依 ID、名稱或代碼查詢部門
- AND 查詢結果包含完整的部門元資料

#### Scenario: 部門列表動態取得
- GIVEN 部門定義支援動態擴展
- WHEN 需要取得所有可用部門列表
- THEN 系統從統一的部門註冊表返回當前所有部門，無需硬編碼

#### Scenario: 部門 ID 與名稱映射
- GIVEN 部門定義已載入
- WHEN 需要將部門 ID 轉換為顯示名稱，或將名稱轉換為 ID
- THEN 系統提供雙向映射功能，確保一致性

#### Scenario: 向後相容的字串名稱支援
- GIVEN 現有代碼使用字串名稱（如「內政部」）識別部門
- WHEN 使用統一的部門識別格式
- THEN 系統保留字串名稱映射，確保現有代碼仍可正常運作
- AND 允許漸進式遷移至使用部門 ID

### Requirement: Department Definition File Format
部門定義檔案必須（MUST）採用標準 JSON 格式，每個部門包含必要的識別資訊與可選的顯示屬性。

#### Scenario: JSON 格式驗證
- GIVEN 部門定義 JSON 檔案
- WHEN 系統載入檔案
- THEN 驗證 JSON 格式正確性
- AND 驗證必要欄位存在（id, name, code）
- AND 驗證 code 為有效的正整數

#### Scenario: 部門定義結構
- GIVEN 有效的部門定義 JSON
- WHEN 解析部門資訊
- THEN 每個部門物件包含：
  - `id`: 字串，唯一識別碼（如 "interior_affairs"）
  - `name`: 字串，顯示名稱（如 "內政部"）
  - `code`: 整數，帳戶 ID 推導用代碼（如 1）
  - `emoji`: 可選字串，表情符號（如 "🏘️"）

#### Scenario: 部門定義檔案缺失處理
- GIVEN 部門定義檔案不存在或無法讀取
- WHEN 系統嘗試載入部門定義
- THEN 系統記錄錯誤並使用預設部門列表作為後備
- AND 確保核心功能仍可運作

### Requirement: Citizen and Suspect Role Configuration
系統必須（MUST）提供指令以設定公民身分組和嫌犯身分組。這些身分組必須（MUST）由管理員或管理伺服器權限的使用者設定，並儲存在國務院配置中。

#### Scenario: 設定公民身分組成功
- **GIVEN** 管理員執行 `/state_council config_citizen_role` 指令
- **AND** 指定有效的 Discord 身分組
- **WHEN** 系統處理設定請求
- **THEN** 系統保存公民身分組 ID 至配置中
- **AND** 回覆成功訊息

#### Scenario: 設定嫌犯身分組成功
- **GIVEN** 管理員執行 `/state_council config_suspect_role` 指令
- **AND** 指定有效的 Discord 身分組
- **WHEN** 系統處理設定請求
- **THEN** 系統保存嫌犯身分組 ID 至配置中
- **AND** 回覆成功訊息

#### Scenario: 未設定身分組時拒絕操作
- **GIVEN** 公民身分組或嫌犯身分組未設定
- **WHEN** 嘗試執行需要身分組的操作（如逮捕）
- **THEN** 系統拒絕操作並提示需要先設定對應的身分組

### Requirement: Comprehensive Test Coverage for State Council Governance Commands

系統必須（MUST）為國務院治理 slash commands 提供全面的測試覆蓋，確保達到 90%以上的代碼覆蓋率，包括部門管理、貨幣發行、稅收收集、福利發放和所有 Result<T,E>錯誤處理路徑。

#### Scenario: State Council 部門管理測試覆蓋

- **WHEN** 測試套件驗證 state_council 命令的部門管理功能
- **THEN** 部門創建、編輯、刪除、領導人配置等所有操作必須有對應測試案例
- **AND** Result<T,E>成功和失敗路徑必須被完整測試

#### Scenario: State Council 貨幣發行測試覆蓋

- **WHEN** 測試套件測試國務院貨幣發行機制
- **THEN** 發行限制驗證、部門分配、餘額檢查等所有分支必須有測試案例
- **AND** 權限檢查和審計記錄必須被驗證

#### Scenario: State Council 稅收收集測試覆蓋

- **WHEN** 測試套件驗證國務院稅收收集功能
- **THEN** 稅率配置、征收計算、部門分配等所有邏輯必須有測試案例
- **AND** Result<T,E>錯誤處理和邊界條件必須被完整覆蓋

#### Scenario: State Council 福利發放測試覆蓋

- **WHEN** 測試套件測試國務院福利發放系統
- **THEN** 發放資格驗證、金額計算、目標分配等所有情況必須有測試案例
- **AND** 權限驗證和資金來源檢查必須被驗證

#### Scenario: State Council 權限管理測試覆蓋

- **WHEN** 測試套件驗證國務院權限檢查
- **THEN** 部門領導人、國務院領袖、法務部等所有權限級別必須有測試案例
- **AND** StateCouncilNotConfiguredError 等錯誤處理必須被完整測試

#### Scenario: State Council 集成測試覆蓋

- **WHEN** 測試套件執行國務院集成測試
- **THEN** 完整的部門-發行-稅收-福利流程必須被測試
- **AND** 與經濟系統和理事會系統的交互必須被驗證
