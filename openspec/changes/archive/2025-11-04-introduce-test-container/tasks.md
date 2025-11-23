## 1. 建立測試容器 Dockerfile
- [x] 1.1 建立 `docker/test.Dockerfile`，基於 Python 3.13-slim
- [x] 1.2 安裝 `uv` 工具（與應用容器一致）
- [x] 1.3 複製專案定義檔案（`pyproject.toml`、`uv.lock`）
- [x] 1.4 使用 `uv sync --group dev` 安裝所有開發依賴（包含測試工具）
- [x] 1.5 複製測試相關檔案（`tests/`、`src/`）
- [x] 1.6 設置工作目錄與非 root 用戶（與應用容器一致）
- [x] 1.7 驗證測試容器可以成功建置並包含所有測試工具

## 2. 建立測試執行腳本
- [x] 2.1 建立 `docker/bin/test.sh`，提供統一的測試執行入口
- [x] 2.2 實現參數解析，支援不同測試類型（unit, contract, integration, performance, db, ci）
- [x] 2.3 實現 `ci` 模式：執行格式化檢查、lint、型別檢查、所有測試
- [x] 2.4 實現各測試類型執行邏輯（unit, contract, integration, performance, db）
- [x] 2.5 設置 `RUN_DISCORD_INTEGRATION_TESTS=1` 環境變數（整合測試用）
- [x] 2.6 確保腳本錯誤時返回非零退出碼
- [x] 2.7 設置腳本為可執行

## 3. 配置 Compose 測試服務
- [x] 3.1 在 `compose.yaml` 中新增 `test` 服務
- [x] 3.2 設定測試服務使用 `docker/test.Dockerfile` 建置
- [x] 3.3 設定測試服務依賴 PostgreSQL 服務（等待健康檢查）
- [x] 3.4 設定測試服務使用專案根目錄作為工作目錄
- [x] 3.5 設定測試服務讀取 `.env` 檔案（支援環境變數）
- [x] 3.6 設定測試服務使用 `docker/bin/test.sh` 作為入口點
- [x] 3.7 設定測試服務掛載測試目錄（可選，用於開發時即時更新）
- [x] 3.8 驗證測試服務可以成功啟動並連接到 PostgreSQL

## 4. 測試驗證
- [x] 4.1 驗證測試容器可以執行單元測試
- [x] 4.2 驗證測試容器可以執行合約測試
- [x] 4.3 驗證測試容器可以執行資料庫測試（連接到 Compose PostgreSQL）
- [x] 4.4 驗證測試容器可以執行整合測試（需要 Discord Token）
- [x] 4.5 驗證測試容器可以執行效能測試
- [x] 4.6 驗證測試容器可以執行完整 CI 流程（格式化、lint、型別檢查、測試）
- [x] 4.7 驗證測試結果正確輸出到標準輸出
- [x] 4.8 驗證覆蓋率報告可以輸出到掛載的卷

## 5. 文件更新
- [x] 5.1 更新 `README.md`，說明如何使用測試容器執行測試
- [x] 5.2 更新 `README.md`，說明測試容器的不同執行模式
- [x] 5.3 更新 `README.md`，說明如何查看覆蓋率報告
- [x] 5.4 更新 `CHANGELOG.md`，記錄測試容器功能

## 6. Makefile 整合
- [x] 6.1 在 `Makefile` 中新增 `test-container` 命令，執行 `docker compose run --rm test`
- [x] 6.2 在 `Makefile` 中新增 `test-container-unit` 命令，執行單元測試
- [x] 6.3 在 `Makefile` 中新增 `test-container-contract` 命令，執行合約測試
- [x] 6.4 在 `Makefile` 中新增 `test-container-integration` 命令，執行整合測試
- [x] 6.5 在 `Makefile` 中新增 `test-container-performance` 命令，執行效能測試
- [x] 6.6 在 `Makefile` 中新增 `test-container-db` 命令，執行資料庫測試
- [x] 6.7 在 `Makefile` 中新增 `test-container-economy` 命令，執行經濟相關測試
- [x] 6.8 在 `Makefile` 中新增 `test-container-council` 命令，執行議會相關測試
- [x] 6.9 在 `Makefile` 中新增 `test-container-all` 命令，執行所有測試類型（不含整合測試）
- [x] 6.10 在 `Makefile` 中新增 `test-container-ci` 命令，執行完整 CI 流程（格式化、lint、型別檢查、所有測試）
- [x] 6.11 在 `Makefile` 中新增 `test-container-build` 命令，建置測試容器映像檔
- [x] 6.12 更新 `Makefile` 的 `help` 命令與 `.PHONY` 聲明，說明新的測試容器命令

## 7. 最終驗證
- [x] 7.1 執行完整測試套件，確保所有測試通過
- [x] 7.2 驗證測試容器可以在乾淨環境中成功建置（無本地快取）
- [x] 7.3 驗證測試容器與應用容器可以同時運行而不衝突
- [x] 7.4 驗證文件完整且準確
