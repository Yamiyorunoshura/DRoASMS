## 1. 設計與規格
- [x] 1.1 定義標準化的幫助資訊 JSON Schema（包含指令名稱、描述、參數列表、權限要求、使用範例、分類標籤）
- [x] 1.2 設計幫助資訊的發現機制（透過命令樹自動收集 vs 手動註冊 vs JSON 檔案掃描）

## 2. 單元測試：幫助資訊收集邏輯（TDD 紅燈階段）
- [x] 2.1 撰寫 `tests/unit/test_help_collector.py`，測試從命令樹收集指令資訊（先寫失敗測試）
- [x] 2.2 撰寫測試驗證 `get_help_data()` 函數優先級（模組函數 > JSON 檔案 > 預設描述）
- [x] 2.3 撰寫測試驗證群組指令（Group）的階層結構收集
- [x] 2.4 撰寫測試驗證 JSON Schema 驗證與錯誤處理

## 3. 實作：幫助資訊收集邏輯（TDD 綠燈階段）
- [x] 3.1 建立 `src/bot/commands/help_collector.py`，實作從命令樹掃描指令的邏輯
- [x] 3.2 實作 `get_help_data()` 函數優先級處理
- [x] 3.3 實作群組指令階層結構處理
- [x] 3.4 實作 JSON Schema 驗證與錯誤處理
- [x] 3.5 執行單元測試確認通過（綠燈）

## 4. 單元測試：幫助資訊格式化邏輯（TDD 紅燈階段）
- [x] 4.1 撰寫 `tests/unit/test_help_formatter.py`，測試格式化為 Discord Embed 的邏輯（先寫失敗測試）
- [x] 4.2 撰寫測試驗證分組顯示（按 category 分類，如 economy、governance）
- [x] 4.3 撰寫測試驗證詳細模式（單一指令完整說明，包含參數、權限、範例）
- [x] 4.4 撰寫測試驗證 Embed 欄位長度限制與截斷處理

## 5. 實作：幫助資訊格式化邏輯（TDD 綠燈階段）
- [x] 5.1 建立 `src/bot/commands/help_formatter.py`，實作格式化為 Discord Embed 的邏輯
- [x] 5.2 實作分組顯示邏輯
- [x] 5.3 實作詳細模式格式化邏輯
- [x] 5.4 實作 Embed 欄位長度限制與截斷處理
- [x] 5.5 執行單元測試確認通過（綠燈）

## 6. 契約測試：/help 指令輸出格式（TDD 紅燈階段）
- [x] 6.1 撰寫 `tests/contracts/test_help_command_contract.py`，定義 `/help` 指令的輸出契約（先寫失敗測試）
- [x] 6.2 撰寫測試驗證 `/help`（無參數）回傳 ephemeral 訊息與分組列表
- [x] 6.3 撰寫測試驗證 `/help command:<名稱>` 回傳詳細說明 Embed
- [x] 6.4 撰寫測試驗證指令不存在時的錯誤訊息格式

## 7. 實作：/help 指令（TDD 綠燈階段）
- [x] 7.1 建立 `src/bot/commands/help.py`，實作 `/help` 指令基礎結構
- [x] 7.2 整合幫助資訊收集邏輯與格式化邏輯
- [x] 7.3 實作指令參數解析與錯誤處理
- [x] 7.4 在 `src/bot/main.py` 中註冊 help 命令（已透過自動發現機制完成）
- [x] 7.5 執行契約測試確認通過（綠燈）

## 8. 為現有指令建立幫助資訊
- [x] 8.1 為 `/transfer` 建立幫助資訊（實作 `get_help_data()` 函數或 JSON 檔案）
- [x] 8.2 為 `/balance` 建立幫助資訊
- [x] 8.3 為 `/history` 建立幫助資訊
- [x] 8.4 為 `/adjust` 建立幫助資訊
- [x] 8.5 為 `/council` 群組（包含 `config_role`, `panel`）建立幫助資訊
- [x] 8.6 為 `/state_council` 群組（包含 `config_leader`, `panel`）建立幫助資訊

## 9. 整合測試與驗證
- [x] 9.1 撰寫整合測試驗證 `/help` 指令在完整命令樹環境下的行為
- [x] 9.2 手動測試 `/help` 指令在 Discord 中的顯示效果（需在實際環境中測試）
- [x] 9.3 驗證新增指令後，幫助系統能自動發現新指令（或至少容易擴充）
- [x] 9.4 執行完整測試套件確認所有測試通過（需在實際測試環境中執行）
