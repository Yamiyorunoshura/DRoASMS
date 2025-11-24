## ADDED Requirements
### Requirement: SQL 函式測試完整性
系統 SHALL 為所有 SQL 函式（economy 與 governance schema）提供完整的 pgTAP 測試，確保資料庫層業務邏輯的正確性與穩定性。

#### Scenario: Economy Schema 函式測試覆蓋
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** 所有 economy schema 的 SQL 函式都有對應的 pgTAP 測試檔案（`tests/db/test_fn_*.sql`）
- **AND** 測試涵蓋以下函式：
  - `fn_adjust_balance`、`fn_transfer_currency`、`fn_get_balance`、`fn_get_history`、`fn_has_more_history`
  - `fn_record_throttle`、`fn_notify_adjustment`
  - `fn_create_pending_transfer`、`fn_get_pending_transfer`、`fn_list_pending_transfers`、`fn_update_pending_transfer_status`
  - `fn_check_transfer_balance`、`fn_check_transfer_cooldown`、`fn_check_transfer_daily_limit`、`fn_check_and_approve_transfer`
  - `trigger_pending_transfer_check`
- **AND** 每個測試檔案驗證函式簽名、成功路徑、邊界條件與錯誤處理

#### Scenario: Governance Schema - Council 函式測試覆蓋
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** 所有 governance schema 的 Council 相關 SQL 函式都有對應的 pgTAP 測試檔案
- **AND** 測試涵蓋以下函式：
  - 設定：`fn_upsert_council_config`、`fn_get_council_config`
  - 提案：`fn_create_proposal`、`fn_get_proposal`、`fn_get_snapshot_members`、`fn_count_active_proposals`、`fn_attempt_cancel_proposal`
  - 投票：`fn_upsert_vote`、`fn_fetch_tally`、`fn_list_votes_detail`、`fn_list_unvoted_members`
  - 狀態：`fn_mark_status`、`fn_list_due_proposals`、`fn_list_reminder_candidates`、`fn_list_active_proposals`、`fn_mark_reminded`
  - 匯出：`fn_export_interval`
- **AND** 測試驗證提案建立限制（最多 5 個進行中提案）、投票邏輯、狀態轉換、執行轉帳等關鍵業務邏輯

#### Scenario: Governance Schema - State Council 函式測試覆蓋
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** 所有 governance schema 的 State Council 相關 SQL 函式都有對應的 pgTAP 測試檔案
- **AND** 測試涵蓋以下函式：
  - 設定：`fn_upsert_state_council_config`、`fn_get_state_council_config`、`fn_upsert_department_config`、`fn_list_department_configs`、`fn_get_department_config`
  - 帳戶：`fn_upsert_government_account`、`fn_list_government_accounts`、`fn_update_government_account_balance`
  - 福利：`fn_create_welfare_disbursement`、`fn_list_welfare_disbursements`
  - 稅收：`fn_create_tax_record`、`fn_list_tax_records`
  - 身分：`fn_create_identity_record`、`fn_list_identity_records`
  - 貨幣：`fn_create_currency_issuance`、`fn_list_currency_issuances`、`fn_sum_monthly_issuance`
  - 轉帳：`fn_create_interdepartment_transfer`、`fn_list_interdepartment_transfers`
  - 查詢：`fn_list_all_department_configs_with_welfare`、`fn_list_all_department_configs_for_issuance`
- **AND** 測試驗證各部門操作的正確性、餘額更新、跨部門轉帳等關鍵業務邏輯

#### Scenario: SQL 測試品質標準
- **WHEN** 開發者新增或更新 SQL 函式測試
- **THEN** 測試檔案 MUST 使用 pgTAP 框架（`SELECT plan(...)`、`SELECT ok(...)`、`SELECT throws_like(...)` 等）
- **AND** 測試 MUST 驗證函式簽名（`SELECT has_function(...)`）
- **AND** 測試 MUST 涵蓋成功路徑、邊界條件（NULL、空值、極值）、錯誤處理（例外、約束違反）
- **AND** 測試 MUST 使用交易隔離（`BEGIN; ... ROLLBACK;`）確保不影響其他測試
- **AND** 測試 MUST 使用唯一的測試資料（snowflake ID）避免衝突

#### Scenario: SQL 測試執行與報告
- **WHEN** 開發者執行 `make test-db` 或 `docker compose run test db`
- **THEN** `pg_prove` 正確執行所有 `tests/db/*.sql` 檔案
- **AND** 測試結果輸出到標準輸出，包含通過/失敗統計
- **AND** 測試失敗時返回非零退出碼
- **AND** 如果 `tests/db/` 目錄為空或沒有 SQL 檔案，腳本優雅處理（不失敗）

## MODIFIED Requirements
### Requirement: 完整 CI 流程包含整合和資料庫測試
系統 SHALL 確保完整 CI 流程（`test.sh ci` 命令）執行所有必要的測試類型，包括整合測試和資料庫函數測試。

#### Scenario: CI 流程執行順序
- **WHEN** 開發者執行 `docker compose run test ci` 或 `make ci`
- **THEN** 腳本執行以下步驟（按順序）：
  1. 格式化檢查（`black --check`）
  2. Lint 檢查（`ruff check`）
  3. 型別檢查（`mypy`）
  4. Pre-commit 檢查
  5. 單元測試
  6. 合約測試
  7. 經濟測試
  8. 資料庫測試（SQL 函數測試）**MUST** 被執行
  9. 議會測試
  10. 效能測試
  11. 整合測試
- **AND** 資料庫測試使用 `pg_prove` 執行所有 `tests/db/*.sql` 檔案
- **AND** 資料庫測試失敗時 CI 流程停止並返回非零退出碼

#### Scenario: 資料庫測試在 CI 中執行
- **WHEN** 完整 CI 流程執行
- **THEN** 資料庫函數測試（`tests/db/*.sql`）使用 `pg_prove` 被包含在流程中
- **AND** SQL 測試正確連接到 PostgreSQL 服務（使用 `DATABASE_URL` 環境變數）
- **AND** 測試結果被正確報告
- **AND** SQL 測試失敗時 CI 流程停止並返回非零退出碼
- **AND** `make ci` 命令明確包含資料庫函式測試（透過 `docker/bin/test.sh ci` 的 `run_all()` 函式）
