## Why
目前部分指令的描述文字仍為英文（例如 `/transfer` 的 `description="Transfer virtual currency to another member in this guild."` 與 `/council` 群組的 `description="Council governance commands"`），與專案整體中文化不一致。為提供一致的使用者體驗，需要將所有指令相關的介紹與指引完全中文化。

## What Changes
- 將所有 slash command 裝飾器中的 `description` 參數中文化
- 確保所有指令的 `get_help_data()` 函數回傳的描述與參數說明皆為中文
- 統一指令群組（`/council`, `/state_council`）的描述為中文
- 確保 `/help` 指令顯示的所有文字皆為中文

## Impact
- 受影響的規格：
  - `help-command`：確保幫助系統顯示中文內容
  - `economy-commands`：經濟類指令描述中文化
  - `council-panel`：理事會指令描述中文化
  - `state-council-panel`：國務院指令描述中文化
- 受影響的程式碼：
  - `src/bot/commands/transfer.py`：`build_transfer_command` 中的 `description` 參數
  - `src/bot/commands/council.py`：`build_council_group` 中的 `description` 參數
  - 其他指令檔案中可能存在的英文描述
