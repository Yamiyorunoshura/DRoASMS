## Why
目前專案已有多個 slash commands（如 `/transfer`, `/balance`, `/history`, `/adjust`, `/council`, `/state_council`），但缺乏統一的幫助指令。使用者需要逐一嘗試或查看原始碼才能了解每個指令的用法、參數與權限。建立標準化的幫助系統後，新指令只需定義一次 JSON 格式的幫助資訊，`/help` 指令即可自動收集並顯示所有可用指令的完整說明。

## What Changes
- 新增 `/help` slash command，顯示所有已註冊指令的說明
- 定義標準化的 JSON 格式用於儲存每個指令的幫助資訊（包含名稱、描述、參數說明、權限要求、使用範例等）
- 每個命令模組可選擇性地提供幫助資訊（JSON 檔案或 Python 字典），`/help` 指令自動發現並彙整
- 支援分組顯示（例如經濟類、治理類）與單一指令詳細說明模式
- `/help` 可接受選填的 `command` 參數，用於顯示特定指令的詳細說明

## Impact
- Affected specs: 新增 `help-command` capability
- Affected code:
  - 新增 `src/bot/commands/help.py`
  - 新增 `src/bot/commands/help_data/` 目錄（存放各指令的 JSON 幫助檔案，可選）
  - 各命令模組可選擇性地匯出幫助資訊（透過 `get_help_data()` 函數或 JSON 檔案）
