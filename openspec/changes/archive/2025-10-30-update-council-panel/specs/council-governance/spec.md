## MODIFIED Requirements

### Requirement: DM-Only Communications (MVP)
MVP 既有「僅 DM」互動調整為「面板優先 + DM 輔助」：互動入口以 `/council panel` 面板為主；系統仍須（MUST）以 DM 進行建案通知、截止前提醒與結案結果投遞（含個別票揭露）；不得（MUST NOT）在公開頻道發佈摘要或結果（本修改不變更此限制）。

#### Scenario: 面板為主、DM 投遞結果
- GIVEN 有一筆新提案建立
- THEN 系統於理事 DM 投遞投票入口（並/或於面板提供投票區）
- AND 結案後以 DM 投遞結果（含各理事最終投票）
