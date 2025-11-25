# help-command Specification

## Purpose
提供統一的指令幫助系統，支援所有可用指令的查詢與說明顯示。整合統一註冊表、模組函數和指令元資料等多種資料來源，確保幫助資訊的一致性與完整性，並提供中文介面的用戶體驗。
## Requirements
### Requirement: Help Command
系統必須（MUST）提供 `/help` slash command，讓使用者查詢所有可用指令的說明與用法。所有指令的描述、參數說明與提示文字必須（MUST）以中文顯示。

#### Scenario: 顯示所有指令列表
- **WHEN** 使用者在伺服器中執行 `/help`（無參數）
- **THEN** 系統回覆 ephemeral 訊息，顯示所有已註冊指令的分組列表（例如：經濟類、治理類）
- **AND** 每個指令顯示名稱與簡短描述（中文）
- **AND** 訊息中包含如何查看特定指令詳細說明的提示（中文）

#### Scenario: 顯示特定指令詳細說明
- **WHEN** 使用者在伺服器中執行 `/help command:<指令名稱>`
- **THEN** 系統回覆 ephemeral 訊息，顯示該指令的完整說明（中文）
- **AND** 包含指令描述、所有參數說明、權限要求、使用範例（皆為中文）
- **AND** 若指令不存在，顯示錯誤訊息並列出可用指令（中文）

#### Scenario: 指令不存在錯誤處理
- **WHEN** 使用者執行 `/help command:<不存在的指令名稱>`
- **THEN** 系統回覆 ephemeral 錯誤訊息，提示指令不存在（中文）
- **AND** 提供可用指令的快速參考（中文）

### Requirement: Standardized Help Data Format
系統必須（MUST）支援標準化的 JSON 格式用於定義每個指令的幫助資訊，以便機器解析與自動彙整。所有幫助資訊的描述與參數說明必須（MUST）以中文提供。

#### Scenario: JSON 格式包含必要欄位
- **GIVEN** 指令開發者提供幫助資訊 JSON
- **WHEN** JSON 包含以下必要欄位：`name`（指令名稱）、`description`（描述，中文）、`category`（分類，如 "economy"、"governance"）
- **AND** 可選欄位：`parameters`（參數列表，每個參數包含 `name`、`description`（中文）、`required`、`type`）、`permissions`（權限要求）、`examples`（使用範例陣列）
- **THEN** `/help` 指令能正確解析並顯示該指令的幫助資訊（中文）

#### Scenario: 參數說明格式化
- **GIVEN** 指令提供參數說明
- **WHEN** 參數包含 `name`、`description`（中文）、`required`（布林值）、`type`（字串，如 "Member"、"int"、"str"）
- **THEN** `/help` 指令在詳細模式中格式化顯示每個參數，標示必填/選填與型別（中文）

### Requirement: Automatic Help Discovery
系統必須（MUST）支援自動發現指令的幫助資訊，使新增指令後無需手動註冊即可在 `/help` 中顯示。當指令未提供標準化幫助資訊時，系統必須（MUST）使用命令裝飾器中的 `description` 作為預設描述，且該描述必須（MUST）為中文。

#### Scenario: 從命令樹自動收集
- **GIVEN** 新的 slash command 已註冊到命令樹
- **WHEN** 該命令模組提供 `get_help_data()` 函數或對應的 JSON 檔案
- **THEN** `/help` 指令自動發現並包含該指令
- **AND** 若未提供幫助資訊，則使用命令裝飾器中的 `description`（必須為中文）作為預設描述

#### Scenario: 群組指令支援
- **GIVEN** 群組指令（如 `/council`, `/state_council`）及其子指令
- **WHEN** 提供群組層級與子指令層級的幫助資訊（中文）
- **THEN** `/help` 指令顯示群組與子指令的階層結構（中文）
- **AND** 詳細模式可顯示群組下所有子指令的說明（中文）

### Requirement: Help Data Structure
系統必須（MUST）定義並驗證幫助資訊的資料結構，確保一致性與可擴充性。所有描述文字必須（MUST）以中文提供。

#### Scenario: JSON Schema 驗證（可選）
- **GIVEN** 指令提供幫助資訊 JSON
- **WHEN** JSON 符合預定義的 Schema（包含必要欄位與型別檢查）
- **THEN** 系統接受並使用該幫助資訊
- **AND** 若 JSON 格式不符，記錄警告並使用預設描述（中文）

#### Scenario: 向後相容性
- **GIVEN** 現有指令未提供標準化幫助資訊
- **WHEN** `/help` 指令嘗試讀取該指令的幫助資訊
- **THEN** 系統回退到使用命令裝飾器中的 `description`（必須為中文）作為基本說明
- **AND** 仍能在指令列表中顯示該指令（中文）

### Requirement: Help Command Priority Order
系統必須（MUST）將 `/help` 指令的資料來源優先順序明確化，並以統一註冊表為最高優先，以確保一致性與可維護性。

#### Scenario: 新的優先順序
- **GIVEN** `/help` 指令需要取得指令說明資料
- **WHEN** 查詢某一指令的說明資訊
- **THEN** 依以下優先順序取得資料：
  1) 統一註冊表（`commands.json`）
  2) 模組函數 `get_help_data()`
  3) 指令定義中的元資料（decorator `description` 等）
- **AND** 系統記錄實際採用的資料來源以利除錯

### Requirement: Comprehensive Test Coverage for Help Command System

系統必須（MUST）為幫助命令系統提供全面的測試覆蓋，確保達到 90%以上的代碼覆蓋率，包括命令收集、格式化輸出、幫助數據管理和所有 Result<T,E>錯誤處理路徑。

#### Scenario: Help 命令收集器測試覆蓋

- **WHEN** 測試套件驗證 help 命令的收集功能
- **THEN** 命令註冊發現、分類整理、動態更新等所有操作必須有對應測試案例
- **AND** Result<T,E>成功和失敗路徑必須被完整測試

#### Scenario: Help 命令格式化器測試覆蓋

- **WHEN** 測試套件測試幫助格式化系統
- **THEN** 不同格式輸出、長度限制、特殊字符處理等所有分支必須有測試案例
- **AND** 用戶體驗和可讀性必須被驗證

#### Scenario: Help 命令數據管理測試覆蓋

- **WHEN** 測試套件驗證幫助數據管理
- **THEN** 數據結構、元數據處理、分類邏輯等所有情況必須有測試案例
- **AND** 數據一致性和完整性必須被完整測試

#### Scenario: Help 命令交互測試覆蓋

- **WHEN** 測試套件測試幫助命令用戶交互
- **THEN** 無參數調用、指定命令查詢、無效命令處理等所有情況必須有測試案例
- **AND** 錯誤消息和用戶引導必須被驗證

#### Scenario: Help 命令集成測試覆蓋

- **WHEN** 測試套件執行幫助系統集成測試
- **THEN** 與所有 slash 命令的集成、動態命令發現、多語言支持等必須被測試
- **AND** 系統擴展性和維護性必須被驗證
