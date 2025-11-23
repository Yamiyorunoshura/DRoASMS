# Change: Integrate Homeland Security Suspects Management into State Council Panel

## Why
嫌犯管理功能目前通過斜線指令實現，但國土安全部面板規格已定義完整界面需求，造成功能重複和使用者體驗不一致。

## What Changes
- 將嫌犯管理邏輯從 `/state_council suspects` 斜線指令遷移到國土安全部面板
- 移除重複的斜線指令註冊和相關UI組件
- **BREAKING**: 移除 `/state_council suspects` 斜線指令

## Impact
- Affected specs: `homeland-security-panel`, `command-registry`
- Affected code: `src/bot/commands/state_council.py`,面板相關實現文件
