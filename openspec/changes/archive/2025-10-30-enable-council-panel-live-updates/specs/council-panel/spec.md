## ADDED Requirements
### Requirement: Realtime Panel Updates
「常任理事會面板」在開啟期間必須（MUST）自動反映與本 guild 治理相關事件（建案、投票、撤案、狀態變更）。面板為 ephemeral，更新僅對開啟者可見，並於 View 結束（timeout/stop）後停止更新。

#### Scenario: 建案後面板自動出現新提案
- WHEN 理事在同一 guild 新建立一筆提案
- THEN 已開啟的面板下拉清單在數秒內出現該提案

#### Scenario: 投票後合計票數更新
- GIVEN 已開啟面板且顯示某進行中提案
- WHEN 任一理事對該提案投票或改票
- THEN 面板中該提案的狀態摘要/合計票數在數秒內更新

#### Scenario: 撤案或逾時/執行後移出清單
- WHEN 提案被撤案、逾時、已通過並執行或執行失敗
- THEN 面板清單移除該提案或更新為結案狀態摘要

#### Scenario: View 結束即停止更新
- WHEN 面板 View 因 timeout 或使用者關閉而結束
- THEN 不再接收或套用任何更新
