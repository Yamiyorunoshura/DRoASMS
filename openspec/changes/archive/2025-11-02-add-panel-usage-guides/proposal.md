## Why
政府相關面板（常任理事會、國務院）已具備完整操作，但新進或非常態使用的官員不易快速理解流程與權限。加入「使用指引」可於面板內即時提供操作說明，降低誤用與支援成本。

## What Changes
- 在 `/council panel` 面板新增「使用指引」按鈕，顯示理事會面板使用說明（建案、投票、撤案、匯出、即時更新、私密性）。
- 在 `/state_council panel` 面板新增「使用指引」按鈕，依「總覽/各部門（內政/財政/國土安全/中央銀行）」切換對應指引。
- 指引以 ephemeral Embed 呈現，僅對開啟者可見。

## Impact
- Affected specs: council-panel, state-council-panel（新增）
- Affected code: src/bot/commands/council.py, src/bot/commands/state_council.py
