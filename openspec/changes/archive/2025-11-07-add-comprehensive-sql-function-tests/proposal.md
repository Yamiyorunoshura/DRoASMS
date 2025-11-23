## Why
目前專案中有 54 個 SQL 函式，但僅有 5 個函式具備 pgTAP 測試（`fn_adjust_balance`、`fn_check_transfer_balance`、`fn_create_pending_transfer`、`fn_get_balance`、`fn_transfer_currency`）。缺乏完整的 SQL 函式測試會導致：
1. 資料庫層業務邏輯變更時無法及時發現回歸問題
2. 無法驗證 SQL 函式的邊界條件與錯誤處理
3. 違反 TDD 原則與專案的「重資料庫原則」（Database-Centric Architecture）

## What Changes
- **ADDED**: 為所有尚未測試的 SQL 函式補足 pgTAP 測試
  - Economy schema 函式：`fn_get_history`、`fn_has_more_history`、`fn_record_throttle`、`fn_notify_adjustment`、`fn_check_transfer_cooldown`、`fn_check_transfer_daily_limit`、`fn_get_pending_transfer`、`fn_list_pending_transfers`、`fn_update_pending_transfer_status`、`fn_check_and_approve_transfer`、`trigger_pending_transfer_check`
  - Governance schema 函式：所有 Council 與 State Council 相關函式（共 33 個）
- **MODIFIED**: 更新現有 SQL 函式測試以確保覆蓋率完整
- **MODIFIED**: 確保 `make ci` 流程明確包含資料庫函式測試（目前已在 `run_all()` 中，但需明確文件化）

## Impact
- **Affected specs**: `test-infrastructure`（新增 SQL 函式測試完整性要求）
- **Affected code**:
  - `tests/db/*.sql`（新增約 40+ 個測試檔案）
  - `docker/bin/test.sh`（驗證 `run_db()` 在 CI 流程中的執行）
  - `Makefile`（確保 `make ci` 明確包含資料庫測試）
