## 1. 盤點與規劃
- [x] 1.1 列出所有 SQL 函式清單（economy 與 governance schema）
- [x] 1.2 識別已測試與未測試的函式
- [x] 1.3 為每個未測試函式規劃測試場景（成功路徑、邊界條件、錯誤處理）

## 2. Economy Schema 函式測試
- [x] 2.1 新增 `test_fn_get_history.sql`（測試分頁、游標、邊界值）
- [x] 2.2 新增 `test_fn_has_more_history.sql`（測試游標判斷邏輯）
- [x] 2.3 新增 `test_fn_record_throttle.sql`（測試限流記錄）
- [x] 2.4 新增 `test_fn_notify_adjustment.sql`（測試 NOTIFY 觸發）
- [x] 2.5 新增 `test_fn_check_transfer_cooldown.sql`（測試冷卻時間檢查）
- [x] 2.6 新增 `test_fn_check_transfer_daily_limit.sql`（測試每日上限檢查）
- [x] 2.7 新增 `test_fn_get_pending_transfer.sql`（測試待處理轉帳查詢）
- [x] 2.8 新增 `test_fn_list_pending_transfers.sql`（測試待處理轉帳列表）
- [x] 2.9 新增 `test_fn_update_pending_transfer_status.sql`（測試狀態更新）
- [x] 2.10 新增 `test_fn_check_and_approve_transfer.sql`（測試轉帳審核）
- [x] 2.11 新增 `test_trigger_pending_transfer_check.sql`（測試觸發器）

## 3. Governance Schema - Council 函式測試
- [x] 3.1 新增 `test_fn_upsert_council_config.sql`
- [x] 3.2 新增 `test_fn_get_council_config.sql`
- [x] 3.3 新增 `test_fn_create_proposal.sql`（測試提案建立、快照、並發限制）
- [x] 3.4 新增 `test_fn_get_proposal.sql`
- [x] 3.5 新增 `test_fn_get_snapshot_members.sql`
- [x] 3.6 新增 `test_fn_count_active_proposals.sql`
- [x] 3.7 新增 `test_fn_attempt_cancel_proposal.sql`
- [x] 3.8 新增 `test_fn_upsert_vote.sql`（測試投票、重複投票、狀態檢查）
- [x] 3.9 新增 `test_fn_fetch_tally.sql`（測試計票邏輯）
- [x] 3.10 新增 `test_fn_list_votes_detail.sql`
- [x] 3.11 新增 `test_fn_mark_status.sql`（測試狀態轉換、執行轉帳）
- [x] 3.12 新增 `test_fn_list_due_proposals.sql`
- [x] 3.13 新增 `test_fn_list_reminder_candidates.sql`
- [x] 3.14 新增 `test_fn_list_active_proposals.sql`
- [x] 3.15 新增 `test_fn_mark_reminded.sql`
- [x] 3.16 新增 `test_fn_export_interval.sql`（測試匯出邏輯）
- [x] 3.17 新增 `test_fn_list_unvoted_members.sql`

## 4. Governance Schema - State Council 函式測試
- [x] 4.1 新增 `test_fn_upsert_state_council_config.sql`
- [x] 4.2 新增 `test_fn_get_state_council_config.sql`
- [x] 4.3 新增 `test_fn_upsert_department_config.sql`
- [x] 4.4 新增 `test_fn_list_department_configs.sql`
- [x] 4.5 新增 `test_fn_get_department_config.sql`
- [x] 4.6 新增 `test_fn_upsert_government_account.sql`
- [x] 4.7 新增 `test_fn_list_government_accounts.sql`
- [x] 4.8 新增 `test_fn_update_government_account_balance.sql`
- [x] 4.9 新增 `test_fn_create_welfare_disbursement.sql`（測試福利發放）
- [x] 4.10 新增 `test_fn_list_welfare_disbursements.sql`
- [x] 4.11 新增 `test_fn_create_tax_record.sql`（測試稅收記錄）
- [x] 4.12 新增 `test_fn_list_tax_records.sql`
- [x] 4.13 新增 `test_fn_create_identity_record.sql`（測試身分記錄）
- [x] 4.14 新增 `test_fn_list_identity_records.sql`
- [x] 4.15 新增 `test_fn_create_currency_issuance.sql`（測試貨幣增發）
- [x] 4.16 新增 `test_fn_list_currency_issuances.sql`
- [x] 4.17 新增 `test_fn_sum_monthly_issuance.sql`（測試月度彙總）
- [x] 4.18 新增 `test_fn_create_interdepartment_transfer.sql`（測試跨部門轉帳）
- [x] 4.19 新增 `test_fn_list_interdepartment_transfers.sql`
- [x] 4.20 新增 `test_fn_list_all_department_configs_with_welfare.sql`
- [x] 4.21 新增 `test_fn_list_all_department_configs_for_issuance.sql`

## 5. 更新現有測試
- [x] 5.1 檢視 `test_fn_adjust_balance.sql`，確保覆蓋率完整
- [x] 5.2 檢視 `test_fn_check_transfer_balance.sql`，確保覆蓋率完整
- [x] 5.3 檢視 `test_fn_create_pending_transfer.sql`，確保覆蓋率完整
- [x] 5.4 檢視 `test_fn_get_balance.sql`，確保覆蓋率完整
- [x] 5.5 檢視 `test_fn_transfer_currency.sql`，確保覆蓋率完整

## 6. CI 整合驗證
- [x] 6.1 驗證 `docker/bin/test.sh` 的 `run_ci()` 函式確實呼叫 `run_all()`（已包含 `run_db()`）
- [x] 6.2 驗證 `make ci` 命令正確執行資料庫函式測試
- [x] 6.3 執行完整 CI 流程確認所有 SQL 測試通過
- [x] 6.4 更新文件說明 CI 流程包含資料庫函式測試

## 7. 測試執行與驗證
- [x] 7.1 執行所有新增的 SQL 測試：`make test-db`
- [x] 7.2 確認所有測試通過
- [x] 7.3 執行完整 CI 流程：`make ci`
- [x] 7.4 確認 CI 流程中資料庫測試正確執行並報告結果
