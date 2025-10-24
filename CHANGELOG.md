# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- 進一步的監控與可觀測性（metrics/log tracing）
- 更多治理功能與工作流程命令

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
