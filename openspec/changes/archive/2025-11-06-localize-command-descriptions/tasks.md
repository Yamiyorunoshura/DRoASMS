## 1. 實作
- [x] 1.1 將 `/transfer` 指令的 `description` 參數從英文改為中文
- [x] 1.2 將 `/council` 群組的 `description` 參數從英文改為中文
- [x] 1.3 檢查所有其他指令檔案，確保所有 `@app_commands.command` 與 `@app_commands.Group` 的 `description` 皆為中文
- [x] 1.4 驗證所有 `get_help_data()` 函數回傳的描述與參數說明皆為中文
- [x] 1.5 檢查並更新所有指令參數的 `@app_commands.describe` 裝飾器，確保描述為中文

## 2. 測試
- [x] 2.1 執行 `/help` 指令，確認所有指令描述皆顯示為中文
- [x] 2.2 執行 `/help command:transfer`，確認詳細說明為中文
- [x] 2.3 執行 `/help command:council`，確認群組與子指令說明為中文
- [x] 2.4 執行 `/help command:state_council`，確認群組與子指令說明為中文
- [x] 2.5 驗證所有指令在 Discord 中的自動完成提示為中文

## 3. 驗證
- [x] 3.1 執行 `openspec validate localize-command-descriptions --strict` 確保規格正確
- [x] 3.2 檢查所有指令的參數描述在 Discord 介面中顯示為中文
- [x] 3.3 確認沒有遺漏任何英文描述文字
