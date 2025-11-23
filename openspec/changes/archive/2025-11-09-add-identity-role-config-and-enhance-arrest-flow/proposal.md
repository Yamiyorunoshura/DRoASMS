## Why
增強國土安全部的身分管理功能，提供更直觀的逮捕流程，並允許管理員配置公民和嫌犯身分組。同時修復最高人民會議傳召功能，當有多個常任理事時能夠正確通知所有成員。

## What Changes
- 新增 `/state_council config_citizen_role` 指令，允許管理員設定公民身分組
- 新增 `/state_council config_suspect_role` 指令，允許管理員設定嫌犯身分組
- 修改國土安全部面板：將「身分管理」按鈕改為「逮捕人員」
- 修改逮捕流程：按下按鈕後發送新的嵌入訊息，使用下拉選單選擇要逮捕的人，並要求填寫逮捕原因
- 修改逮捕操作：被逮捕的人會被自動移除公民身分組並掛上嫌犯身分組
- 修復最高人民會議傳召功能：當選擇傳召常任理事時，發送新面板讓用戶選擇要傳召哪一個或哪些常任理事（可多選）

## Impact
- Affected specs:
  - `state-council-governance`: 新增身分組配置功能
  - `state-council-panel`: 修改國土安全部面板的逮捕流程
  - `supreme-assembly-panel`: 修復傳召常任理事的選擇機制
- Affected code:
  - `src/bot/commands/state_council.py`: 新增配置指令，修改面板按鈕和逮捕流程
  - `src/bot/services/state_council_service.py`: 新增身分組配置服務方法，修改逮捕邏輯
  - `src/db/gateway/state_council_governance.py`: 新增身分組配置的資料庫操作
  - `src/db/migrations/`: 新增遷移以支援身分組配置欄位
  - `src/bot/commands/supreme_assembly.py`: 修改傳召常任理事的選擇機制
