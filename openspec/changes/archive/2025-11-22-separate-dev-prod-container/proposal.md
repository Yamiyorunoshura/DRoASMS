# Change: 分離開發與生產環境容器依賴

## Why
目前專案使用單一 Docker 配置，無法區分開發和生產環境的不同依賴需求，導致生產環境包含不必要的開發工具，增加安全風險和映像檔大小。

## What Changes
- 建立開發環境專用的 Dockerfile，包含所有開發依賴和工具
- 優化生產環境 Dockerfile，僅包含運行所需的最小依賴
- 修改 compose.yaml 配置，支援多階段建置和環境特化
- 更新 Makefile 目標，確保 `make start-dev` 和 `make start-prod` 使用對應的容器配置

## Impact
- Affected specs: infrastructure
- Affected code: docker/Dockerfile, compose.yaml, Makefile
- **BREAKING**: 生產環境容器將不再包含開發工具，可能影響除錯流程
