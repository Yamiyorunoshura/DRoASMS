## Context
專案採用「重資料庫原則」（Database-Centric Architecture），目標是將業務規則盡量實作於資料庫層，Python 層僅負責 Discord 互動、基本驗證與授權、呼叫 Gateway 與日誌/遙測。此原則確保 PostgreSQL 作為單一真實來源與一致性邏輯核心。

目前發現 `StateCouncilGovernanceGateway.fetch_government_accounts` 方法直接查詢 `governance.government_accounts` 資料表，而非使用已存在的 `fn_list_government_accounts` SQL 函式。根據註解，這是因為舊版函式有 ambiguous column 問題，但該問題已在 SQL 函式中修正（使用表別名 `ga`）。

## Goals / Non-Goals
- Goals:
  - 確保所有 Gateway 層程式碼統一使用 SQL 函式，符合中心化架構原則
  - 移除所有直接操作資料表的程式碼
  - 維持現有功能不變

- Non-Goals:
  - 不改變現有 SQL 函式的介面或行為
  - 不改變資料模型或資料表結構
  - 不新增功能，僅重構現有實作

## Decisions
- Decision: 將 `fetch_government_accounts` 改為使用 `fn_list_government_accounts` SQL 函式
  - Rationale: 該函式已存在且已修正 ambiguous column 問題，符合中心化架構原則
  - Alternatives considered: 保留直接查詢（違反架構原則，不採用）

- Decision: 全面檢查所有 Gateway 檔案
  - Rationale: 確保沒有遺漏其他直接查詢的情況
  - Alternatives considered: 僅修正已知問題（風險較高，不採用）

## Risks / Trade-offs
- Risk: 修改後可能影響現有功能 → Mitigation: 完整執行測試套件確保功能正常
- Risk: SQL 函式效能可能不如直接查詢 → Mitigation: 若效能差異可忽略，優先符合架構原則；若效能差異顯著，再評估優化 SQL 函式

## Migration Plan
1. 確認 `fn_list_government_accounts` 函式已正確修正（已在遷移檔案中）
2. 修改 Gateway 程式碼改用 SQL 函式
3. 執行測試驗證功能正常
4. 檢查其他 Gateway 檔案確保沒有類似問題

## Open Questions
- 是否需要檢查 Service 層是否有直接操作資料庫的程式碼？（應由 Gateway 層統一處理）
