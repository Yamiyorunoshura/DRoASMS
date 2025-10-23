# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- 進一步的監控與可觀測性（metrics/log tracing）
- 更多治理功能與工作流程命令

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
