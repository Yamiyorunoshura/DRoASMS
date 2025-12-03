# 安裝指南

本指南說明如何安裝與設定 DRoASMS Discord 機器人，包括環境準備、依賴安裝、資料庫設置與機器人啟動。

## 系統需求

### 最低要求
- **作業系統**: Linux、macOS 或 Windows（建議 Linux 伺服器）
- **Python**: 3.13（專案使用 `uv python pin 3.13` 鎖定解譯器）
- **PostgreSQL**: 15+ 版本
- **記憶體**: 最少 512MB RAM
- **儲存空間**: 最少 100MB 可用空間

### 推薦配置
- **CPU**: 2+ 核心
- **記憶體**: 1GB+ RAM
- **儲存空間**: 1GB+ 可用空間（視交易記錄量增加）
- **網路**: 穩定的網路連線，可存取 Discord API 與資料庫

### 必要擴展
PostgreSQL 必須啟用以下擴展：
- **pgcrypto**（必需）：用於加密功能與 UUID 生成
- **pg_cron**（選用）：用於自動化任務（交易記錄歸檔）

## 安裝步驟

### 1. 取得原始碼
```bash
# 克隆專案
git clone https://github.com/Yamiyorunoshura/DRoASMS.git
cd DRoASMS

# 切換到穩定分支（可選）
git checkout main
```

### 2. 安裝 uv（推薦的套件管理器）
uv 是現代化的 Python 套件管理器，提供快速的依賴解析與虛擬環境管理。

```bash
# 安裝 uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# 重新載入 shell
exec "$SHELL" -l

# 驗證安裝
uv --version
```

**替代方案**：如果您偏好使用傳統工具，也可以使用 `pip` 與 `venv`，但 uv 是本專案的推薦工具。

### 3. 安裝專案依賴
```bash
# 使用 uv 同步依賴（會自動建立虛擬環境）
uv sync

# 或使用傳統方式（不推薦）
# python3 -m venv .venv
# source .venv/bin/activate
# pip install -e .
```

### 4. 環境設定
複製環境變數範本並設定必要的值：

```bash
# 複製範本
cp .env.example .env

# 編輯 .env 檔案，填入以下必要設定
nano .env  # 或使用您喜歡的文字編輯器
```

#### 必要環境變數
```env
# Discord 機器人令牌（從 Discord 開發者後台取得）
DISCORD_TOKEN=你的Discord機器人令牌

# PostgreSQL 資料庫連線字串
DATABASE_URL=postgresql://username:password@127.0.0.1:5432/dbname
```

#### 可選環境變數
```env
# 伺服器白名單（逗號分隔的伺服器 ID）
DISCORD_GUILD_ALLOWLIST=伺服器ID1,伺服器ID2

# 啟用轉帳事件池（建議 true，可避免互動逾時）
TRANSFER_DAILY_LIMIT=1000

# 冷卻時間（秒）
TRANSFER_COOLDOWN_SECONDS=300

# 日誌等級
LOG_LEVEL=INFO
```

### 5. 資料庫設置
您可以選擇以下任一方式設置 PostgreSQL 資料庫：

#### 選項 A：使用 Docker Compose（最簡單）
專案提供 `compose.yaml` 檔案，可一鍵啟動機器人與資料庫：

```bash
# 啟動所有服務（背景執行）
docker compose up -d

# 檢查服務狀態
docker compose ps

# 查看日誌
docker compose logs -f bot
```

#### 選項 B：本機 PostgreSQL 安裝（Linux）
```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# 建立資料庫使用者與資料庫
sudo -u postgres createuser bot -P           # 會提示輸入密碼
sudo -u postgres createdb -O bot economy

# 啟用 pgcrypto 擴展
sudo -u postgres psql -d economy -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 啟用 pg_cron 擴展（選用，用於自動歸檔）
sudo apt-get install -y postgresql-16-cron  # 依版本調整
sudo -u postgres psql -d economy -c "CREATE EXTENSION IF NOT EXISTS pg_cron;"
```

#### 選項 C：雲端 PostgreSQL（Neon、Supabase、RDS）
- 從供應商後台取得連線字串
- 通常需要 `?sslmode=require` 參數
- 在雲端資料庫啟用 pgcrypto 擴展

### 6. 執行資料庫遷移
```bash
# 執行所有遷移
uv run alembic upgrade head

# 若 head 遷移失敗（缺少 pg_cron），可先升級到 003
uv run alembic upgrade 003_economy_adjustments
```

**遷移說明：**
- `head`：最新遷移，需要 pg_cron 擴展支援自動歸檔
- `003_economy_adjustments`：不包含自動歸檔的基本功能

### 7. 初始化預設配置（選用）
```bash
# 初始化經濟系統預設配置
uv run -m src.db.seeds.initial_config
```

## 驗證安裝

### 1. 資料庫連線測試
```bash
uv run python - <<'PY'
import asyncio, asyncpg, os
async def main():
    dsn = os.getenv('DATABASE_URL')
    print('DSN =', dsn)
    conn = await asyncpg.connect(dsn=dsn)
    ver = await conn.fetchval('select version()')
    print('connected ->', ver)
    await conn.close()
asyncio.run(main())
PY
```

### 2. 配置驗證測試
```bash
uv run python - <<'PY'
import os
from src.config.settings import BotSettings

try:
    settings = BotSettings()
    print('✅ 配置驗證成功')
    print(f'   - Discord Token: {settings.discord_token[:10]}...')
    print(f'   - 資料庫 URL: {settings.database_url[:30]}...')
except Exception as e:
    print(f'❌ 配置驗證失敗: {e}')
PY
```

### 3. 快速功能測試
```bash
# 執行單元測試
uv run pytest tests/unit/test_balance_service.py -v
```

## 啟動機器人

### 方法 1：使用 uv 直接運行
```bash
# 使用 uv 啟動（自動載入 .env）
uv run -m src.bot.main

# 或指定環境變數檔案
uv run --env-file .env -m src.bot.main
```

### 方法 2：使用 Docker Compose
```bash
# 啟動所有服務
docker compose up -d bot

# 查看啟動日誌
docker compose logs -f bot

# 等待就緒訊號（約 60 秒內）
docker compose logs -f bot | grep '"event":"bot.ready"'
```

### 方法 3：系統服務（Linux systemd）
建立 systemd 服務檔案 `/etc/systemd/system/droasms.service`：

```ini
[Unit]
Description=DRoASMS Discord Bot
After=network.target postgresql.service

[Service]
Type=simple
User=botuser
WorkingDirectory=/opt/DRoASMS
EnvironmentFile=/opt/DRoASMS/.env
ExecStart=/opt/DRoASMS/.venv/bin/python -m src.bot.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

啟用並啟動服務：
```bash
sudo systemctl daemon-reload
sudo systemctl enable droasms
sudo systemctl start droasms
sudo systemctl status droasms
```

## 安裝後檢查清單

### 必要檢查
- [ ] Discord 機器人在線上且顯示為「線上」狀態
- [ ] 日誌中出現 `{"event":"bot.ready"}` 就緒訊號
- [ ] 資料庫遷移成功執行（無錯誤）
- [ ] 環境變數設定正確（無遺漏）

### 功能測試
- [ ] 執行 `/help` 命令，確認機器人回應
- [ ] 執行 `/balance` 命令，查看自己的餘額
- [ ] 執行 `/currency_config` 命令（管理員），設定貨幣名稱與圖示

### 監控檢查
- [ ] 日誌輸出正常，無重複錯誤訊息
- [ ] 系統資源使用率正常（CPU、記憶體、磁碟）
- [ ] 資料庫連線池運作正常

## 故障排除

### 常見問題

#### 1. Discord Token 無效
```
錯誤：Unauthorized 或 401 錯誤
```
**解決方案：**
- 確認 Token 正確無誤
- 在 Discord 開發者後台重新生成 Token
- 確認機器人有正確的權限範圍（bot、applications.commands）

#### 2. 資料庫連線失敗
```
錯誤：Multiple exceptions: [Errno 111] Connect call failed
```
**解決方案：**
- 確認 PostgreSQL 服務正在運行：`systemctl status postgresql`
- 確認連線字串正確：`DATABASE_URL=postgresql://...`
- 確認防火牆允許連線：`sudo ufw allow 5432`

#### 3. 遷移失敗（缺少 pg_cron）
```
錯誤：pg_cron extension not found
```
**解決方案：**
- 安裝 pg_cron 擴展（見上述安裝步驟）
- 或先升級到 003 遷移：`uv run alembic upgrade 003_economy_adjustments`

#### 4. 機器人無回應
```
症狀：命令無反應，機器人狀態正常
```
**解決方案：**
- 確認機器人有「應用程式命令」權限
- 確認命令已註冊：`/help` 應顯示命令列表
- 等待命令同步（最多 1 小時），或使用全局命令

### 日誌分析

#### 關鍵日誌事件
```bash
# 查看日誌
docker compose logs -f bot

# 過濾重要事件
docker compose logs -f bot | grep -E 'bot.ready|db.connect|transfer|error'
```

#### 日誌等級
- `ERROR`: 需要立即關注的錯誤
- `WARN`: 潛在問題或異常情況
- `INFO`: 正常業務流程記錄
- `DEBUG`: 詳細除錯資訊（開發時啟用）

## 升級指南

當有新版本發布時，請依以下步驟升級：

```bash
# 1. 取得最新程式碼
git fetch origin
git switch main
git pull --ff-only

# 2. 更新依賴
uv sync

# 3. 更新資料庫遷移
uv run alembic upgrade head

# 4. 重新啟動服務
docker compose build --pull bot && docker compose up -d bot

# 5. 驗證升級
docker compose logs -f bot | grep '"event":"bot.ready"'
```

## 安全建議

### 環境變數安全
- 永遠不要將 `.env` 檔案提交到版本控制
- 使用環境變數管理敏感資訊（Token、密碼）
- 定期旋轉 Discord Token 與資料庫密碼

### 資料庫安全
- 使用強密碼保護資料庫使用者
- 限制資料庫連線來源（防火牆規則）
- 定期備份資料庫資料

### 應用程式安全
- 保持依賴套件更新至最新安全版本
- 限制 Discord 伺服器白名單避免未授權訪問
- 審查管理員操作記錄與異常活動

## 下一步

安裝完成後，您可以：

1. **閱讀 [快速開始指南](quickstart.md)** - 五分鐘內運行第一個機器人
2. **查看 [配置說明](configuration.md)** - 詳細環境變數說明
3. **探索 [架構概述](../architecture/overview.md)** - 理解系統設計
4. **參考 [命令參考](../api/commands/overview.md)** - 所有可用命令說明
5. **閱讀 [部署指南](deployment.md)** - 生產環境部署最佳實踐
