# 重構直接資料庫操作以符合中心化架構

## Why
專案採用「重資料庫原則」（Database-Centric），業務規則應在資料庫層以 SQL 函式實作，Python Gateway 層僅負責呼叫 SQL 函式。經檢查發現部分 Gateway 程式碼仍直接查詢資料表，違反中心化架構設計原則，需要統一改為使用 SQL 函式。

## What Changes
- 修正 `StateCouncilGovernanceGateway.fetch_government_accounts` 方法，改用已存在的 `fn_list_government_accounts` SQL 函式，移除直接查詢 `governance.government_accounts` 資料表的程式碼
- 檢查所有 Gateway 程式碼，確保沒有其他直接操作資料表的程式碼
- 註：Migrations 和 Seeds 檔案中的直接 SQL 操作是合理的，因為它們是資料庫管理工具，不屬於業務邏輯層
- 如有需要，撰寫新的 SQL 函式以滿足現有程式碼的資料庫操作需求
- 更新相關測試以確保重構後功能正常

## Impact
- Affected specs: state-council-governance, council-governance, economy-commands
- Affected code:
  - `src/db/gateway/state_council_governance.py:286-315` (fetch_government_accounts)
  - 可能影響其他 Gateway 檔案
