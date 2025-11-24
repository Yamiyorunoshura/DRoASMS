# command-registry Specification

## Purpose
統一管理所有斜線指令的說明資訊，提供集中式的指令註冊表系統，支援 JSON 格式的指令定義、階層式指令結構、參數說明、權限要求和使用範例。確保幫助系統的一致性和可維護性。
## Requirements
### Requirement: Unified Command Registry
系統必須（MUST）提供統一的JSON格式指令註冊表，用於集中管理所有斜線指令的說明資訊。註冊表必須（MUST）支援階層式指令結構、參數說明、權限要求和使用範例。

#### Scenario: 註冊表JSON結構定義
- **GIVEN** 系統需要定義指令註冊表格式
- **WHEN** 建立commands.json檔案
- **THEN** JSON結構必須包含以下必要欄位：
  - `name`: 指令名稱（字串）
  - `description`: 指令描述（中文，字串）
  - `category`: 分類（economy/governance/general，字串）
  - `parameters`: 參數陣列，每個參數包含name、description、required、type
  - `permissions`: 權限要求陣列（字串）
  - `examples`: 使用範例陣列（字串）
  - `tags`: 標籤陣列（字串）
  - `subcommands`: 子指令物件（選填）

#### Scenario: 階層式指令支援
- **GIVEN** 群組指令如`state_council`、`council`
- **WHEN** 定義註冊表結構
- **THEN** 支援巢狀子指令結構
- **AND** 每個子指令可繼承父指令的權限和分類
- **AND** 子指令可覆寫父指令的設定

#### Scenario: 註冊表檔案位置
- **GIVEN** 系統載入指令註冊表
- **WHEN** 讀取commands.json
- **THEN** 檔案位置為`src/bot/commands/help_data/commands.json`
- **AND** 支援分類子目錄結構（如`help_data/economy/transfer.json`）

### Requirement: Help Command Registry Integration
help指令必須（MUST）優先從統一註冊表讀取指令資訊，而非依賴各模組的`get_help_data()`函數。

#### Scenario: 註冊表優先讀取
- **GIVEN** 存在統一註冊表
- **WHEN** help指令收集說明資訊
- **THEN** 優先讀取commands.json中的資料
- **AND** 僅在註冊表不存在時回退至模組函數

#### Scenario: 註冊表更新後自動生效
- **GIVEN** 修改commands.json內容
- **WHEN** 下次執行help指令
- **THEN** 立即反映更新後的說明資訊
- **AND** 無需重新啟動機器人

#### Scenario: 向後相容性保持
- **GIVEN** 某些指令尚未遷移至註冊表
- **WHEN** help指令查詢該指令
- **THEN** 回退至原有的`get_help_data()`函數機制
- **AND** 不影響現有指令的正常運作

### Requirement: Registry Validation and Schema
系統必須（MUST）提供註冊表的結構驗證機制，確保資料格式正確性和一致性。

#### Scenario: JSON Schema驗證
- **GIVEN** 載入commands.json
- **WHEN** 解析JSON內容
- **THEN** 驗證必要欄位存在性
- **AND** 驗證資料型別正確性
- **AND** 驗證參數陣列格式

#### Scenario: 驗證錯誤處理
- **GIVEN** commands.json格式錯誤
- **WHEN** 系統載入註冊表
- **THEN** 記錄錯誤日誌
- **AND** 回退至模組函數機制
- **AND** 不阻止系統啟動

#### Scenario: 動態重新載入支援
- **GIVEN** 開發環境修改註冊表
- **WHEN** 檔案變更
- **THEN** 支援熱重載註冊表內容（選填功能）
- **AND** 無需重新啟動即可看到變更

### Requirement: Registry Migration Support
系統必須（MUST）提供從現有`get_help_data()`函數遷移至統一註冊表的工具和指引。

#### Scenario: 遷移工具提供
- **GIVEN** 現有指令使用`get_help_data()`
- **WHEN** 需要遷移至註冊表
- **THEN** 提供遷移指令或工具
- **AND** 自動轉換函數回傳值為JSON格式
- **AND** 驗證轉換結果的正確性

#### Scenario: 雙重來源支援期間
- **GIVEN** 部分指令已遷移
- **WHEN** help指令收集資料
- **THEN** 同時支援註冊表和函數來源
- **AND** 註冊表資料優先於函數資料
- **AND** 提供遷移狀態報告

<!-- Moved to help-command delta as ADDED requirement: Help Command Priority Order -->
