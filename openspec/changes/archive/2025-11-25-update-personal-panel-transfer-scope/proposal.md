# Change: 擴展個人面板政府部門轉帳範圍並移除舊指令

## Why

目前個人面板的「轉帳給政府部門」功能僅支援國務院下屬部門，缺乏對常任理事會、最高人民會議和國務院主帳戶的轉帳能力。此外，`/balance` 和 `/history` 指令與個人面板功能重疊，應予移除以簡化指令結構。

## What Changes

- **擴展個人面板政府部門轉帳範圍**：
  - 新增常任理事會（理事會帳戶）作為轉帳目標
  - 新增最高人民會議（議會帳戶）作為轉帳目標
  - 新增國務院主帳戶作為轉帳目標
  - 保留現有國務院下屬部門轉帳功能
- **更新 departments.json**：
  - 新增 `supreme_assembly`（最高人民會議）項目
  - 確保所有政府機構正確映射到對應的經濟帳戶
- **BREAKING**: 移除 `/balance` 指令
- **BREAKING**: 移除 `/history` 指令

## Impact

- **Affected specs**:
  - `personal-panel`：修改政府部門轉帳功能
  - `economy-commands`：移除 balance 和 history 相關需求
- **Affected code**:
  - `src/bot/ui/personal_panel.py`：擴展政府部門選項
  - `src/config/departments.json`：新增政府機構定義
  - `src/bot/commands/`：移除 balance 和 history 指令
  - `tests/`：更新相關測試
