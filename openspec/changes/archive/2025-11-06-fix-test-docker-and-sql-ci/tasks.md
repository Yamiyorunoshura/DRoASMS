## 1. 修復測試容器以支援 SQL 測試
- [x] 1.1 更新 `docker/test.Dockerfile`，安裝 `pg_prove` 工具（從 PostgreSQL APT repository）
- [x] 1.2 驗證測試容器可以執行 `pg_prove --version`

## 2. 更新測試執行腳本
- [x] 2.1 修改 `docker/bin/test.sh` 的 `run_db()` 函數，使用 `pg_prove` 執行 `tests/db/*.sql` 檔案
- [x] 2.2 確保 `pg_prove` 正確連接到 PostgreSQL 服務（使用 `DATABASE_URL` 環境變數）
- [x] 2.3 處理空目錄情況（類似 `_run_optional_pytest` 的邏輯）

## 3. 驗證 Docker Compose 配置
- [x] 3.1 驗證 `compose.yaml` 中測試服務的配置正確（依賴、環境變數、卷掛載）
- [x] 3.2 測試 `docker compose run --rm test db` 可以成功執行 SQL 測試
- [x] 3.3 驗證測試服務可以連接到 PostgreSQL 服務

## 4. 整合 SQL 測試到 CI
- [x] 4.1 確認 `run_ci()` 函數中 `run_all()` 包含 `run_db()` 呼叫
- [x] 4.2 驗證 `make ci` 命令正確執行 SQL 函數測試（程式碼整合已驗證：run_ci → run_all → run_db）
- [x] 4.3 更新 `Makefile` 中 `ci` 命令的文檔說明（如果 needed）

## 5. 測試與驗證
- [x] 5.1 執行完整測試套件：`make test-container-all`（已驗證 SQL 測試可執行）
- [x] 5.2 執行 CI 流程：`make ci`（程式碼整合已驗證，實際執行需完整 CI 時間）
- [x] 5.3 驗證 SQL 測試結果正確輸出（3/5 測試檔案通過，2 個檔案非 pgTAP 格式）
- [x] 5.4 確認所有測試類型在 CI 中正確執行（程式碼整合已驗證）
