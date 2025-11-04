# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **測試容器基礎設施**：新增獨立的測試容器，提供一致的測試執行環境
  - 建立 `docker/test.Dockerfile`：基於 Python 3.13，包含所有測試依賴（dev dependencies）
  - 建立 `docker/bin/test.sh`：統一的測試執行腳本，支援不同測試類型（unit, contract, integration, performance, db, economy, council, ci）
  - 在 `compose.yaml` 中新增 `test` 服務：自動連接到 PostgreSQL，支援環境變數傳遞
  - 在 `Makefile` 中新增測試容器相關命令：
    - `test-container-build`：建置測試容器映像檔
    - `test-container`：執行所有測試（不含整合測試）
    - `test-container-unit`：執行單元測試
    - `test-container-contract`：執行合約測試
    - `test-container-integration`：執行整合測試
    - `test-container-performance`：執行效能測試
    - `test-container-db`：執行資料庫測試
    - `test-container-economy`：執行經濟相關測試
    - `test-container-council`：執行議會相關測試
    - `test-container-all`：執行所有測試（不含整合測試）
    - `test-container-ci`：執行完整 CI 流程（格式化、lint、型別檢查、所有測試）
  - 測試容器特性：
    - 環境隔離：測試容器與應用容器分離，確保測試環境不影響應用運行
    - 資料庫測試支援：測試容器能夠連接到 Compose 中的 PostgreSQL 服務
    - 覆蓋率報告：自動掛載到本地 `htmlcov/` 目錄
    - 開發時即時更新：測試目錄掛載為唯讀，開發時可即時更新測試檔案
  - 更新 `README.md`：添加測試容器使用說明與各種執行模式說明

## [0.5.0] - 2025-11-04

### Added
- **開發工具堆疊**：引入業界標準工具提升開發效率與程式碼品質
  - **Pydantic v2**：重構設定管理為 Pydantic 模型，提供型別安全與自動驗證
    - `BotSettings`：Discord bot 設定（`src/config/settings.py`）
    - `PoolConfig`：資料庫連線池設定（`src/config/db_settings.py`）
    - 自動驗證環境變數格式與型別，提供友善的錯誤訊息
  - **pytest-cov**：新增測試覆蓋率報告，整合至 CI 與開發流程
    - HTML 與終端報告輸出
    - CI 中自動上傳覆蓋率報告作為 artifact
  - **Faker**：在測試中引入 Faker 自動生成假資料（中文/英文）
    - 減少手寫測試資料，提升測試效率
    - 在 `tests/conftest.py` 提供 `faker` fixture
  - **Tenacity**：重構重試邏輯使用 Tenacity 裝飾器
    - 簡化重試實作，支援指數退避與抖動策略
    - 應用於轉帳事件池的重試機制（`src/bot/services/transfer_event_pool.py`）
    - 建立共通重試策略模組（`src/infra/retry.py`）
  - **pytest-xdist**：支援並行執行測試，縮短測試時間
    - 預設使用 `-n auto` 自動偵測 CPU 核心數
    - CI 中所有測試套件使用並行執行
  - **pre-commit**：新增 Git hooks 自動執行格式化、lint、型別檢查
    - 設定檔案：`.pre-commit-config.yaml`
    - 包含 black、ruff、mypy 檢查
  - **Hypothesis**：引入屬性測試框架（選用）
    - 可用於複雜邏輯的邊界案例測試
    - 版本要求調整為 `>=6.0.0`（與可用版本相容）
  - **Typer + Rich**：為 CLI 工具預留架構（選用）
  - **watchfiles**：開發時自動重載支援（選用）

### Changed
- 設定載入：從手動 `os.getenv()` 遷移至 Pydantic 模型
  - `src/bot/main.py`：使用新的 `BotSettings` Pydantic 模型
  - `src/db/pool.py`：使用新的 `PoolConfig` Pydantic 模型
  - `tests/conftest.py`：更新測試 fixture 使用新的設定模型
- 重試邏輯：重構轉帳事件池重試機制使用 Tenacity
  - `_retry_checks` 方法使用 `@retry` 裝飾器自動重試資料庫錯誤
- CI 工作流程：整合覆蓋率報告與並行測試執行
  - 所有測試任務使用 `-n auto` 並行執行
  - 自動上傳覆蓋率報告作為 artifact
- 依賴修正：新增 `pydantic-settings>=2.0.0` 作為獨立依賴（Pydantic v2 中 BaseSettings 已分離）
- 測試修正：更新 `transfer_event_pool.py` 的異常處理，支援 Pydantic 驗證錯誤（ValueError）

## [0.4.0] - 2025-11-03

### Added
- **轉帳事件池（Transfer Event Pool）**：實現事件驅動的異步轉帳處理架構
  - 透過 PostgreSQL NOTIFY/LISTEN 機制實現自動檢查與重試
  - 支援餘額、冷卻時間、每日上限的異步檢查
  - 自動重試機制（指數退避，最多 10 次）
  - 預設過期時間 24 小時，定期清理過期請求
  - 環境變數 `TRANSFER_EVENT_POOL_ENABLED` 控制啟用（預設 false，向後相容）
  - 新增 `pending_transfers` 表與相關 SQL 函式（遷移 022-026）
  - 新增 `TransferEventPoolCoordinator` 協調器與 `TelemetryListener` 事件監聽器
  - 新增完整測試覆蓋與架構文檔（`docs/transfer-event-pool.md`）
- **幫助命令系統（/help）**：新增指令說明與查詢功能
  - `/help`：顯示所有可用指令列表或查詢特定指令詳細資訊
  - 自動收集指令樹中的指令資訊（名稱、描述、參數、權限、範例）
  - 支援分類顯示與搜尋功能
  - 新增 `HelpCollector`、`HelpFormatter`、`HelpData` 模組
- **國務院治理系統（State Council Governance）**：擴充完整的部門治理功能
  - `/state_council config_leader`：設定國務院領袖（使用者或身分組）
  - `/state_council panel`：開啟國務院面板（部門管理、發行點數、匯出）
  - 部門配置管理：各部門可設定領導人身分組、稅率、發行上限
  - 部門點數發行：國務院領袖可向各部門發行點數
  - 部門轉帳：各部門可向成員轉帳（透過政府帳戶）
  - 匯出功能：支援匯出部門配置與發行記錄
  - 新增 `StateCouncilService`、`StateCouncilReports`、`StateCouncilScheduler` 服務
  - 新增 `state_council_governance` 資料庫 schema 與相關 SQL 函式（遷移 006-020）
  - 新增完整測試覆蓋（單元、整合、契約測試）
- **CI/CD 工作流程**：新增 GitHub Actions CI 配置
  - 自動執行測試、型別檢查、程式碼品質檢查
  - 支援多 Python 版本測試（3.13）
  - 支援 Docker Compose 整合測試
  - 自動測試轉帳事件池、國務院治理等新功能

### Changed
- `/transfer`：支援事件池模式（當 `TRANSFER_EVENT_POOL_ENABLED=true` 時）
- `/adjust`：支援以部門領導人身分組為目標（自動映射至對應政府帳戶）
- `/balance`：改善分頁顯示與歷史記錄查詢
- `/council`：改善面板功能與指令同步
- 資料庫函式：擴充 `fn_transfer_currency` 支援政府帳戶豁免檢查
- 測試架構：擴充測試工具與契約測試覆蓋

### Planned
- 進一步的監控與可觀測性（metrics/log tracing）
- 更多治理功能與工作流程命令

## [0.3.1] - 2025-10-30

### Fixed
- **斜線指令重複顯示問題**：修復使用 Guild Allowlist 時，允許清單中的伺服器同時看到全域與 Guild 專屬兩份指令的問題
  - Guild Allowlist 現在會自動去重，避免同一 Guild 被重複同步造成潛在副作用或額外延遲
  - 完成 Guild 指令同步後，自動清除全域指令，避免歷史遺留的全域指令與 Guild 指令重複

### Changed
- 改善程式碼品質：優化 import 語句排序、加強類型註解、改善字串格式化

## [0.3.0] - 2025-10-30

### Added
- **治理系統（Council Governance）**：實現完整的常任理事會提案與投票機制
  - `/council config_role`：設定常任理事身分組（需管理員權限）
  - `/council panel`：開啟理事會面板，整合建案、投票、撤案與匯出功能
  - 理事會面板支援即時更新（透過事件訂閱機制）
  - 提案建立時自動鎖定理事名冊快照（N 人）並計算門檻（T = ⌊N/2⌋ + 1）
  - 72 小時投票期限，截止前 24 小時 DM 提醒未投票理事
  - 達門檻自動執行轉帳；餘額不足或錯誤記錄「執行失敗」
  - 結案時向全體理事與提案人揭露個別最終投票
  - 同一伺服器進行中提案上限 5 個
  - 提案人可於無票前撤案
- 新增 `src/infra/events/council_events.py`：治理事件發布訂閱機制（支援 Panel 即時更新）
- 新增 `src/db/gateway/council_governance.py`：治理資料層（CouncilConfig、Proposal、Vote、Tally）
- 新增 `src/bot/services/council_service.py`：治理業務邏輯層（建案、投票、執行、匯出）
- 新增 `src/bot/commands/council.py`：Discord UI（Panel、VotingView、Modal）與背景排程器
- 新增資料庫 migration `005_governance_council.py`：建立 governance schema（council_config、proposals、proposal_snapshots、votes）
- 新增完整測試覆蓋：
  - `tests/unit/test_council_service.py`：服務層單元測試
  - `tests/unit/test_council_math.py`：門檻計算邏輯測試
  - `tests/integration/council/test_council_flow.py`：完整提案流程整合測試
  - `tests/integration/council/test_panel_contract.py`：面板契約測試
- 新增 `AGENTS.md`：OpenSpec 指引（AI 助手開發規範）

### Changed
- `/adjust` 與 `/transfer` 命令支援以理事會身分組為目標（自動映射至理事會帳戶）
- `src/bot/main.py`：啟用成員 Intent（`intents.members = True`）以讀取角色成員清單
- `src/bot/main.py`：改進指令同步機制（使用 `copy_global_to()` 加速公會內指令可見性）
- `compose.yaml`：改用自訂 `docker/postgres.Dockerfile` 並啟用 pg_cron（`shared_preload_libraries=pg_cron`）
- `docker/init/001_extensions.sql`：新增 `CREATE EXTENSION pg_cron`
- `.gitignore`：新增 `*.pyc`、`.envrc`、`.claude/`、`.cursor/`、`openspec/`
- README.md：新增「治理（Council Governance，MVP）」與「理事會面板（Panel）」完整使用說明

### Removed
- 刪除 `.envrc`（已加入 .gitignore）
- 清理所有 `__pycache__/*.pyc` 編譯快取檔案

### Notes
- 治理功能需要 Discord 開發者後台啟用「成員 Intent」
- MVP 版本僅透過 DM 進行互動與通知，無公開頻道摘要
- 需要 PostgreSQL 安裝 pg_cron 擴充以支援背景排程任務

## [0.2.2] - 2025-10-24

### Added
- 新增 `docker/Dockerfile`（基於 uv 的精簡建置流程）與 `docker/bin/entrypoint.sh`（啟動前環境檢查、DB 連線重試、Alembic 自動遷移、結構化 JSON 日誌事件）。
- 新增 `src/infra/logging/config.py`：統一 JSON Lines 日誌格式（鍵包含 `ts`,`level`,`msg`,`event`），並內建敏感值遮罩（`token`/`authorization`/`password` 等）。
- 新增契約與規格（`specs/002-docker-run-bot`）：Compose 環境變數 Schema、日誌事件 Schema、OpenAPI 草案等。
- 新增測試覆蓋：
  - contracts：`.env.example` 必要鍵驗證、日誌事件 Schema、日誌遮罩。
  - integration：Compose 就緒（於 120s 內 `{"event":"bot.ready"}`）、依賴順序、外部 DB 覆寫/不可用（退出碼 69）、遷移失敗（退出碼 70）、缺少必要環境（退出碼 64）、重試退避參數行為等。
- 新增 `scripts/check_image_layers.sh` 供鏡像層級敏感字樣掃描；新增 `.envrc`（direnv）。

### Changed
- 將根目錄 `Dockerfile` 移至 `docker/Dockerfile`，`compose.yaml` 改以新路徑建置；調整 `.dockerignore` 以縮小映像內容。
- 更新 `.env.example`：新增 `ALEMBIC_UPGRADE_TARGET` 與 pgAdmin 預設設定與說明。
- README：新增「日誌與可觀測性」章節，補充就緒事件與退出碼說明。

### Security
- 日誌遮罩常見敏感鍵，避免在 stdout 泄露密碼或 Token。

### Notes
- 無安裝 `pg_cron` 的環境預設遷移目標為 `003_economy_adjustments`；如需每日歸檔請安裝 `pg_cron` 後升級至 `head`。
- 直接透過 Docker 建置時請使用 `-f docker/Dockerfile`。

## [0.2.1] - 2025-10-23

### Added
- 新增 `compose.yaml` + `Dockerfile`，可透過 `docker compose up -d` 一鍵啟動 Bot 與 PostgreSQL（與選用 pgAdmin），避免因未啟動資料庫導致連線被拒。
- 新增 `docker/init/001_extensions.sql`，首次啟動自動建立 `pgcrypto` 擴充。

### Changed
- README：擴充安裝與啟動指南，加入 Docker Compose（可直接啟動 Bot）、連線自測、故障排除，並新增「使用 Git 更新專案」章節。
- 專案版本提升至 0.2.1。

### Notes
- Alembic 遷移 `004_economy_archival` 需要 `pg_cron`。若環境未安裝 `pg_cron`，可先升級至 `003_economy_adjustments` 後再升級至 `head`。

## [0.2.0] - 2025-10-23

### Added
- 實現完整的 Discord 經濟系統功能
- 新增 `/balance` 斜杠命令，支援查詢個人和他人餘額
- 新增 `/history` 斜杠命令，支援查看交易歷史記錄
- 新增 `/transfer` 斜杠命令，支援成員間虛擬貨幣轉移
- 新增 `/adjust` 斜杠命令，支援管理員調整成員點數
- 實現基於 Discord 權限的分級權限系統
- 新增交易限流機制，包含每日轉帳限制和冷卻時間
- 實現 PostgreSQL 資料庫架構，包含經濟系統表和事務處理
- 新增自動歸檔機制，30 天後自動歸檔舊交易記錄
- 實現完整的審計系統，記錄所有管理員操作
- 新增多伺服器支援，每個 Discord 伺服器有獨立的經濟系統

### Changed
- 更新項目描述，反映經濟系統功能
- 更新安裝和配置說明，包含資料庫設定步驟
- 更新 README.md，添加詳細的功能說明和使用指南

### Fixed
- 修復餘額不能變為負數的保護機制
- 確保所有交易操作的 ACID 特性

## [0.1.0] - 2025-10-18

### Changed
- 將專案技術棧更新為 Python 與 PostgreSQL
- 調整 README 與開發流程文件以支援 Python 工具鏈
- 更新 `.gitignore` 以忽略 Python 相關暫存檔案與虛擬環境
