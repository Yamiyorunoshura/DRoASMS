## Why
目前測試容器無法正確執行 SQL 函數測試（`tests/db/*.sql`），因為這些測試使用 pgTAP 框架，需要 `pg_prove` 工具執行，但測試容器中未安裝此工具。此外，SQL 函數測試未正確整合到 CI 流程中（`make ci`），即使測試腳本有 `db` 命令，實際上無法執行 SQL 檔案。

## What Changes
- **BREAKING**: 更新測試容器映像檔，安裝 `pg_prove` 工具以支援 SQL 測試執行
- 修改 `docker/bin/test.sh` 的 `run_db()` 函數，使用 `pg_prove` 執行 SQL 測試而非 `pytest`
- 確保 SQL 函數測試正確整合到 CI 流程（`make ci`）
- 驗證 Docker Compose 測試服務可以成功啟動並執行所有測試類型

## Impact
- Affected specs: `test-infrastructure`
- Affected code:
  - `docker/test.Dockerfile` - 需要安裝 `pg_prove`
  - `docker/bin/test.sh` - 更新 `run_db()` 函數
  - `compose.yaml` - 驗證測試服務配置正確
  - `Makefile` - 確保 `ci` 命令包含 SQL 測試
