# Change: 新增個人面板

## Why

目前系統缺少一個統一的個人資訊入口，使用者需要分別執行 `/balance` 和 `/transfer` 等多個指令來完成日常操作。新增個人面板可提供一站式的個人經濟管理介面，提升用戶體驗。

## What Changes

- 新增 `/personal_panel` 斜線指令，開啟個人面板
- 個人面板首頁顯示用戶名稱和貨幣餘額
- 新增「財產」分頁，顯示交易歷史記錄（分頁顯示）
- 新增「轉帳」分頁，提供轉帳功能
- 轉帳分頁可選擇轉帳給使用者或政府部門
- 轉帳收款人使用下拉式選單選擇

## Impact

- **Affected specs**: 新建 `personal-panel` capability
- **Affected code**:
  - `src/bot/commands/` - 新增 personal_panel 指令
  - `src/bot/ui/` - 新增 personal_panel_paginator.py
  - `src/bot/services/` - 可能需要新增或擴充服務層
