## Why

目前專案的測試執行依賴本地環境設定，開發者需要手動安裝依賴、配置環境變數，並確保 Docker/Compose 可用才能運行完整的測試套件。這導致：
- 不同開發者的環境差異導致測試結果不一致
- 整合測試需要本地 Docker 環境，設定複雜
- CI 測試流程無法在本地完全複現
- 新成員加入時需要大量時間配置測試環境

建立獨立的測試容器可提供一致的測試環境，讓開發者能夠在本地運行完整的 CI 測試流程（包括整合測試、資料庫測試、單元測試等），無需手動配置複雜的環境。

## What Changes

- **測試容器 Dockerfile**：建立 `docker/test.Dockerfile`，基於 Python 3.13，安裝所有測試依賴（dev dependencies）
- **測試服務配置**：在 `compose.yaml` 新增 `test` 服務，使用測試容器執行測試套件
- **測試執行腳本**：建立 `docker/bin/test.sh`，提供統一的測試執行入口，支援不同測試類型（unit, contract, integration, performance, db）
- **CI 流程整合**：測試容器支援執行完整的 CI 測試流程（格式化檢查、lint、型別檢查、測試套件）
- **Makefile 快捷命令**：在 `Makefile` 中新增測試容器相關命令（`test-container`, `test-container-unit`, `test-container-ci` 等），與現有測試命令保持一致
- **環境隔離**：測試容器與應用容器分離，確保測試環境不影響應用運行
- **資料庫測試支援**：測試容器能夠連接到 Compose 中的 PostgreSQL 服務進行資料庫測試

## Impact

- **Affected specs**:
  - 新增 `test-infrastructure` spec：定義測試容器與 CI 測試流程需求
- **Affected code**:
  - `docker/test.Dockerfile`：新增測試容器映像檔定義
  - `compose.yaml`：新增 `test` 服務配置
  - `docker/bin/test.sh`：新增測試執行腳本
  - `Makefile`：新增 `test-container` 相關命令（`test-container`, `test-container-unit`, `test-container-ci` 等）
  - `README.md`：更新測試執行說明

## Breaking Changes

無。此變更為新增功能，不影響現有測試執行方式。開發者仍可使用 `uv run pytest` 在本機執行測試，測試容器提供額外的選項。
