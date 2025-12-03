# 使用指南

本目錄包含 DRoASMS 專案的使用指南，從安裝配置到開發部署的完整流程說明。

## 指南列表

### 入門指南
- [安裝指南](installation.md) - 環境設置與依賴安裝（待撰寫）
- [快速開始](quickstart.md) - 五分鐘內運行第一個機器人（待撰寫）
- [配置說明](configuration.md) - 環境變數與設定檔說明（待撰寫）

### 開發指南
- [開發環境設置](development-environment.md) - 本地開發環境配置（待撰寫）
- [測試指南](testing.md) - 單元測試、整合測試與屬性測試（待撰寫）
- [程式碼風格](code-style.md) - 專案約定的程式碼風格與規範（待撰寫）
- [貢獻指南](../contributing/README.md) - 貢獻程式碼的流程與要求

### 部署指南
- [本地部署](deployment-local.md) - 在本地環境運行機器人（待撰寫）
- [容器化部署](deployment-docker.md) - 使用 Docker 部署（待撰寫）
- [生產環境部署](deployment-production.md) - 生產環境最佳實踐（待撰寫）
- [監控與日誌](monitoring-logging.md) - 系統監控與日誌收集（待撰寫）

### 功能指南
- [經濟系統使用](economy-usage.md) - 經濟系統功能詳細說明（待撰寫）
- [治理系統使用](governance-usage.md) - 治理系統功能詳細說明（待撰寫）
- [權限系統說明](permissions.md) - 權限分級與管理（待撰寫）
- [事件池配置](event-pool-configuration.md) - 轉帳事件池配置與調優（待撰寫）

## 學習路徑

### 新手開發者
1. 閱讀 [安裝指南](installation.md) 設置環境
2. 按照 [快速開始](quickstart.md) 運行第一個機器人
3. 查看 [經濟系統使用](economy-usage.md) 了解核心功能
4. 參考 [開發環境設置](development-environment.md) 配置開發工具

### 進階開發者
1. 閱讀 [架構概述](../architecture/overview.md) 理解系統設計
2. 查看 [API 參考](../api/README.md) 了解各層級介面
3. 參考 [測試指南](testing.md) 編寫高品質測試
4. 閱讀 [部署指南](deployment-production.md) 準備生產環境

### 系統管理員
1. 閱讀 [配置說明](configuration.md) 了解所有設定選項
2. 查看 [容器化部署](deployment-docker.md) 使用 Docker 運行
3. 參考 [監控與日誌](monitoring-logging.md) 設置監控系統
4. 閱讀 [事件池配置](event-pool-configuration.md) 優化系統性能

## 常見任務

### 環境設置
```bash
# 克隆專案
git clone https://github.com/Yamiyorunoshura/DRoASMS.git
cd DRoASMS

# 使用 uv 安裝依賴
uv sync

# 配置環境變數
cp .env.example .env
# 編輯 .env 填入 Discord Token 和資料庫連線字串

# 執行資料庫遷移
uv run alembic upgrade head

# 啟動機器人
uv run -m src.bot.main
```

### 開發工作流程
```bash
# 安裝 pre-commit hooks
make install-pre-commit

# 執行本地 CI 檢查
make ci-local

# 運行測試
make test-unit

# 執行完整 CI 流程
make ci-full
```

### 容器化運行
```bash
# 使用 Docker Compose 啟動所有服務
docker compose up -d

# 查看日誌
docker compose logs -f bot

# 停止服務
docker compose down
```

## 故障排除

常見問題與解決方案請參考 [故障排除指南](../reference/troubleshooting.md)。

## 更新專案

當專案有新版本時，請參考以下更新流程：

```bash
# 獲取最新程式碼
git fetch origin
git switch main
git pull --ff-only

# 更新依賴
uv sync

# 更新資料庫遷移（如果需要）
uv run alembic upgrade head

# 重新啟動服務
docker compose build --pull bot && docker compose up -d bot
```
