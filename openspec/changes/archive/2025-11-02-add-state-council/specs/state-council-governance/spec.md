# state-council-governance Specification

## Purpose
定義國務院治理系統的資料模型與業務邏輯，包含國務院領袖設定、部門權限管理、獨立政府帳戶、定期福利發放、所得稅徵收、身分管理和貨幣政策功能。此規格涵蓋核心業務邏輯，UI 互動由 `state-council-panel` 規格定義。

## ADDED Requirements
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
國土安全部必須（MUST）提供身分管理功能，可以移除被選中使用者的公民身分組並掛上疑犯身分。疑犯身分組必須（MUST）由國務院領袖預先配置。

#### Scenario: 移除公民身分
- Given 具備國土安全部權限的人員
- When 在面板中選擇目標使用者並執行移除操作
- Then 系統移除使用者的公民身分並掛上疑犯身分

#### Scenario: 疑犯身分設定驗證
- Given 國務院領袖未設定疑犯身分組
- When 嘗試移除公民身分
- Then 系統拒絕操作並提示需要先設定疑犯身分組

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
