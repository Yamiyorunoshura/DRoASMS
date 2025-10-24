# DRoASMS

DRoASMS 是以 Python 打造的 Discord 機器人原型，專注於社群的經濟系統與治理流程。

## 功能特色

### 經濟系統
- **虛擬貨幣系統**：完整的社群內經濟體系，支援點數轉移、餘額查詢和交易歷史
- **點數轉移**：成員之間可以自由轉移虛擬貨幣，並可選擇添加備註
- **餘額查詢**：隨時查看自己或他人（需權限）的當前餘額
- **交易歷史**：完整的交易記錄查詢，支援分頁顯示
- **管理員調整**：授權管理員可以調整成員點數，支援加值或扣點

### 權限系統
- **分級權限控制**：基於 Discord 角色的權限管理
- **管理員專用功能**：調整點數和查看他人餘額需要特定權限
- **安全審計**：所有管理員操作都會記錄並可追蹤

### 交易限流機制
- **每日轉帳限制**：防止濫用的每日轉帳上限
- **冷卻時間**：頻繁操作後的短暫限制，確保系統穩定
- **餘額保護**：防止餘額變為負數的保護機制

### 數據庫架構
- **PostgreSQL 後端**：使用可靠的 PostgreSQL 資料庫儲存所有經濟數據
- **ACID 事務**：確保所有交易操作的一致性和可靠性
- **自動歸檔**：30 天後自動歸檔舊交易記錄，保持資料庫效能
- **多伺服器支援**：每個 Discord 伺服器有獨立的經濟系統

## 系統需求
- Python 3.13（專案使用 `uv python pin 3.13` 鎖定解譯器）
- PostgreSQL 15 以上版本（儲存帳戶、交易與治理資料）
- 必須啟用 PostgreSQL 擴充套件：`pgcrypto`（建議）與 `pg_cron`（僅供自動歸檔，無此擴充亦可先運行機器人）
- 推薦使用 `uv` 作為套件管理工具

## 安裝步驟（含 uv）
```bash
# 取得原始碼
git clone https://github.com/Yamiyorunoshura/DRoASMS.git
cd DRoASMS

# 安裝 uv（若尚未安裝）
curl -LsSf https://astral.sh/uv/install.sh | sh
# 重新載入 shell（依你的 shell 類型）
exec "$SHELL" -l

# 使用 uv 建置隔離環境並安裝依賴
uv sync
# 若改用傳統 venv/pip：
#   python3 -m venv .venv && source .venv/bin/activate && pip install -e .
```

## 環境設定
複製 `.env.example` 產生 `.env` 檔案，填入必要的 Discord 憑證與設定：

```env
DISCORD_TOKEN=你的Discord機器人令牌
DATABASE_URL=postgresql://username:password@127.0.0.1:5432/dbname
DISCORD_GUILD_ALLOWLIST=伺服器ID1,伺服器ID2  # 選填
```

注意：請勿將 `.env` 提交到版本控制；若你的 token 不慎外洩，務必在 Discord 開發者平台旋轉（重設）它。

### `DATABASE_URL` 範例
- 本機 TCP：`postgresql://bot:bot@127.0.0.1:5432/economy`
- 本機 Unix Socket（PostgreSQL 僅啟用 Socket、未開 TCP）：
  - Debian/Ubuntu 常見：`postgresql://bot@/economy?host=/var/run/postgresql`
  - 其他路徑：`postgresql://bot@/economy?host=/tmp`
- 雲端/遠端資料庫（多半需要 SSL）：
  - `postgresql://USER:PASSWORD@HOST:5432/DBNAME?sslmode=require`

若需要多個環境設定，可搭配 `.env.development.local`、`.env.production.local` 等檔案與設定管理工具。

## 資料庫設定與啟動

你可以選擇「本機 PostgreSQL」或「雲端/遠端 PostgreSQL」。以下以 Linux 伺服器為例：

### A. 在本機安裝 PostgreSQL（Debian/Ubuntu）
```bash
sudo apt-get update
sudo apt-get install -y postgresql postgresql-contrib
sudo systemctl enable --now postgresql

# 建立資料庫使用者與資料庫（以帳號 bot / 資料庫 economy 為例）
sudo -u postgres createuser bot -P           # 會提示輸入密碼
sudo -u postgres createdb -O bot economy

# 建議安裝與啟用 pgcrypto（供 UUID/雜湊等用途）
sudo -u postgres psql -d economy -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# （選用）若需啟用 pg_cron 以支援每日自動歸檔：
# 1) 安裝對應版本的套件（套件名稱依發行版而異，請依你系統版本調整）：
#    sudo apt-get install -y postgresql-15-cron  # 或 postgresql-16-cron
# 2) 在 postgresql.conf 設定：shared_preload_libraries = 'pg_cron'
# 3) 重新啟動 PostgreSQL：sudo systemctl restart postgresql
# 4) 在目標資料庫啟用：
#    sudo -u postgres psql -d economy -c "CREATE EXTENSION IF NOT EXISTS pg_cron;"
```

### B. 使用 Docker 快速啟動 PostgreSQL（不依賴系統套件）
```bash
docker volume create pgdata
docker run -d --name postgres \
  -e POSTGRES_USER=bot \
  -e POSTGRES_PASSWORD=bot \
  -e POSTGRES_DB=economy \
  -p 5432:5432 \
  -v pgdata:/var/lib/postgresql/data \
  postgres:16

# 連線後於資料庫內啟用 pgcrypto（建議）
docker exec -it postgres psql -U bot -d economy -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;"

# 注意：官方 postgres 映像未預載 pg_cron；若需要 pg_cron，請改用支援該擴充的映像或自行安裝
```

### B2. 使用 Docker Compose 一次啟動 Bot + 依賴
專案已提供 `compose.yaml`（Docker Compose 預設支援的檔名；亦可使用 `docker-compose.yml/yaml`），可一鍵啟動「機器人 + PostgreSQL（與可選 pgAdmin）」。

```bash
# 1) 準備 .env（至少要正確的 DISCORD_TOKEN；Compose 會提供預設的 `DATABASE_URL` 指向 `postgres` 服務，但可由 `.env` 中的 `DATABASE_URL` 覆寫為外部資料庫）
cp .env.example .env
# 編輯 .env，填入 DISCORD_TOKEN 與（選填）DISCORD_GUILD_ALLOWLIST

# 2) 建立與啟動所有服務（背景執行）
docker compose up -d

# 檢查健康狀態
docker compose ps

# （可選）啟用 pgAdmin 介面（預設 8081，或以 .env 中 PGADMIN_PORT 覆寫；帳密 admin@example.com / admin）
docker compose --profile dev up -d pgadmin

# 停止 / 移除
docker compose down        # 停止
docker compose down -v     # 停止並刪除資料卷（會清空資料庫）
```

> 目標：啟動後於 60 秒內觀察到 `{"event":"bot.ready"}`（P95 ≤ 120 秒）。
> 可透過 `docker compose logs -f bot | rg '"event"\s*:\s*"bot.ready"'` 觀察就緒訊號。

Compose 預設內容：
- PostgreSQL：使用者 `bot`、密碼 `bot`、資料庫 `economy`、埠對外 `5432`
- Bot：容器啟動時會先執行 Alembic 遷移，再啟動機器人
- Alembic 目標：預設升級至 `003_economy_adjustments`（避免官方 Postgres 因無 `pg_cron` 導致 004 失敗）
- 初次啟動會自動在資料庫建立 `pgcrypto` 擴充（見 `docker/init/001_extensions.sql`）
- 若需 `pg_cron`，請改用支援該擴充的映像或自行安裝後，將環境變數 `ALEMBIC_UPGRADE_TARGET` 設為 `head`

依需要調整 Alembic 目標版本：
```bash
# 升到 head（需要資料庫已安裝 pg_cron 並設定 shared_preload_libraries）
ALEMBIC_UPGRADE_TARGET=head docker compose up -d --build bot
```

### C. 使用雲端/受管 PostgreSQL（Neon、Supabase、RDS…）
- 於供應商後台取得連線字串，通常需要 `?sslmode=require`。
- 若供應商不提供 `pg_cron`，可以暫時先不啟用每日歸檔（見下方遷移說明）。

### 執行遷移與初始化
```bash
# 讀取 .env、執行資料庫遷移（uv 方式）
uv run alembic upgrade head

# 若你的 PostgreSQL 尚未安裝 pg_cron，且執行 head 失敗：
# 可先升級至 003（不包含每日歸檔腳本），稍後再升至 head：
#   uv run alembic upgrade 003_economy_adjustments

# （可選）初始化經濟系統預設配置
uv run -m src.db.seeds.initial_config
```

### 連線自測（非必要，但便於排錯）
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

## 運行機器人
```bash
# 使用 uv 啟動（會自動載入 .env）
uv run -m src.bot.main

# 或使用傳統 Python（請先啟用虛擬環境並確保安裝 dotenv）
python -m src.bot.main
```

### 啟動前檢查清單
- `.env` 已設定正確的 `DISCORD_TOKEN` 與 `DATABASE_URL`
- PostgreSQL 正在執行，且 `pg_isready -h 127.0.0.1 -p 5432` 顯示 ready（或以 Unix Socket 連線）
- 已執行 `uv run alembic upgrade head`（或至少升級到 `003_economy_adjustments`）

## 使用 Git 更新專案

當專案有更新時，建議以下流程（保持歷史乾淨並避免意外 merge commit）：

```bash
# 1) 取得最新提交（主分支假設為 main）
git fetch origin
git switch main
git pull --ff-only

# 2) 同步相依套件（使用 uv）或重建容器（使用 Compose）
uv sync
# 若使用 Docker Compose：
docker compose build --pull bot && docker compose up -d bot

# 3) 更新資料庫遷移（若 head 需要 pg_cron 而你的 DB 未安裝，可改升到 003）
uv run alembic upgrade head
# 或：uv run alembic upgrade 003_economy_adjustments

# 4) 重新套用依賴服務（若使用 Compose）
docker compose up -d
```

## 斜杠命令列表

### `/balance`
檢視你的虛擬貨幣餘額，或在有權限時查詢他人餘額。

**參數：**
- `member`（選填）：要查詢的成員，需要管理權限才能查詢其他成員

**範例：**
```
/balance                    # 查看自己的餘額
/balance @username          # 管理員查看指定成員的餘額
```

### `/history`
檢視虛擬貨幣的近期交易歷史。

**參數：**
- `member`（選填）：要查詢的成員，需要管理權限才能查詢其他成員
- `limit`（選填）：最多顯示多少筆紀錄（1-50，預設 10）
- `before`（選填）：ISO 8601 時間戳，僅顯示該時間點之前的紀錄

**範例：**
```
/history                   # 查看自己的交易歷史
/history @username         # 管理員查看指定成員的交易歷史
/history limit 20          # 顯示最近 20 筆記錄
/history before 2025-10-20T00:00:00Z  # 顯示指定時間之前的記錄
```

### `/transfer`
將虛擬貨幣轉移給伺服器中的其他成員。

**參數：**
- `target`（必填）：要接收點數的成員
- `amount`（必填）：要轉出的整數點數
- `reason`（選填）：會記錄在交易歷史中的備註

**範例：**
```
/transfer @username 100                    # 轉移 100 點給指定成員
/transfer @username 50 reason:午餐費用      # 轉移 50 點並添加備註
```

### `/adjust`
管理員調整成員點數（正數加值，負數扣點）。

**參數：**
- `target`（必填）：要調整點數的成員
- `amount`（必填）：可以為正數（加值）或負數（扣點）
- `reason`（必填）：將寫入審計紀錄的原因

**權限要求：**
- 需要「管理伺服器」或「系統管理員」Discord 權限

**範例：**
```
/adjust @username 100 reason:活動獎勵         # 給成員加值 100 點
/adjust @username -50 reason:違規懲罰         # 扣除成員 50 點
```

## 權限系統說明

### 一般成員權限
- 查看自己的餘額
- 查看自己的交易歷史
- 向其他成員轉移點數

### 管理員權限
具有「管理伺服器」或「系統管理員」Discord 權限的成員可以：
- 查看任何成員的餘額
- 查看任何成員的交易歷史
- 調整任何成員的點數（加值或扣點）

所有管理員操作都會記錄在交易歷史中，包含操作者、目標、變動數量和原因。

## 交易限流機制說明

### 每日轉帳限制
- 每個伺服器設有每日轉帳上限（預設 500 點）
- 超過限制後將無法繼續轉帳，直到次日重置

### 冷卻時間
- 頻繁轉帳操作會觸發短暫冷卻（預設 5 分鐘）
- 冷卻期間無法進行轉帳操作
- 查詢餘額和歷史記錄不受冷卻影響

### 餘額保護
- 餘額不能變為負數
- 轉帳前會檢查發送者是否有足夠餘額
- 管理員扣點也不能使餘額變為負數

## 使用示例

### 基本使用流程
1. 查看自己的餘額：`/balance`
2. 向朋友轉帳：`/transfer @friend 50 reason:午餐`
3. 確認轉帳成功：`/balance`
4. 查看交易歷史：`/history`

### 管理員操作流程
1. 查看成員餘額：`/balance @member`
2. 調整成員點數：`/adjust @member 100 reason:活動獎勵`
3. 查看調整結果：`/balance @member`
4. 查看完整歷史：`/history @member limit 20`

## 常見問題解答

### Q: 為什麼我無法轉帳？
A: 可能的原因：
- 餘額不足
- 已達每日轉帳限制
- 正在冷卻期內
- 嘗試轉帳給自己

### Q: 為什麼我看不到其他成員的餘額？
A: 只有具有「管理伺服器」或「系統管理員」權限的成員才能查看他人的餘額和交易歷史。

### Q: 交易歷史會保留多久？
A: 交易記錄會保留 30 天，之後會自動歸檔以保持資料庫效能。

## 故障排除（Linux 伺服器）

### OSError: Multiple exceptions: [Errno 111] Connect call failed ('::1', 5432), ('127.0.0.1', 5432)
- 意義：連線被拒絕，表示 `localhost:5432` 沒有任何服務在聽（PostgreSQL 未啟動、沒開 TCP、或防火牆阻擋）。
- 檢查：
  - `pg_isready -h 127.0.0.1 -p 5432` 應顯示 `accepting connections`
  - `ss -ltnp | rg 5432` 應看到 `postgres` 正在 LISTEN
  - 若僅啟用 Unix Socket，請改用上方的 Socket `DATABASE_URL` 寫法
- 修復：
  - 啟動或安裝 PostgreSQL（見「資料庫設定與啟動」章節）
  - 確認 `.env` 的 `DATABASE_URL` 指向正確主機與埠（建議用 `127.0.0.1` 明確走 IPv4）
  - 再跑一次遷移：`uv run alembic upgrade head`

### 遷移 004 失敗：`pg_cron` 不存在
- 代表你的 PostgreSQL 沒有安裝 `pg_cron` 擴充。兩種作法：
  1) 依系統文件安裝 `pg_cron` 並於 `postgresql.conf` 加入 `shared_preload_libraries='pg_cron'` 後重啟，再執行 `uv run alembic upgrade head`
  2) 先將資料庫升級到 `003_economy_adjustments`，待環境允許後再升到 head

### 認證失敗（password authentication failed）
- 請確認 `DATABASE_URL` 的使用者、密碼、資料庫名稱一致，並且該使用者已被授權連線與存取資料庫。


### Q: 如何修改伺服器的經濟設定？
A: 目前需要直接修改資料庫中的 `economy_configurations` 表格，未來版本將提供管理命令。

### Q: 為什麼機器人沒有回應我的命令？
A: 請確認：
- 機器人在線上且有權限存取頻道
- 命令格式正確
- 機器人有讀取訊息和發送訊息的權限

## 日誌與可觀測性

- 輸出格式：JSON Lines（每行一筆 JSON），核心鍵為 `ts`、`level`、`msg`、`event`。
- 重要事件：
  - `bot.ready`：機器人完成啟動與初始化（就緒訊號）。
  - `db.connect.attempt` / `db.connect.retry` / `db.connect.success` / `db.unavailable`：入口腳本的資料庫連線重試流程與結果。
  - `bot.migrate.start` / `bot.migrate.done` / `bot.migrate.error`：Alembic 遷移狀態。
- 敏感遮罩：應用端日誌會遮罩常見敏感鍵（例如 `token`、`authorization`、`password` 等），避免在 stdout 洩露密碼或 Token。
- 退出碼對照：
  - `64`：缺少必要環境變數（例如未設定 `DISCORD_TOKEN`）。
  - `69`：依賴不可用（例如資料庫在期限內不可達）。
  - `70`：遷移失敗（Alembic 升級錯誤）。
  - `78`：無效設定/Schema（例如 `DATABASE_URL` 非 `postgresql://` 開頭）。
- 觀察就緒：
  - `docker compose logs -f bot | rg '"event"\s*:\s*"bot.ready"'`
  - 建議搭配 `jq`：`docker compose logs -f bot | jq -cr`

## 測試與品質維護
```bash
# 單元測試
pytest

# 型別檢查
mypy src/

# 程式碼品質檢查
ruff check .

# 程式碼格式化
black src/
```

## 貢獻指南
歡迎提交 Issue 或 Pull Request，分享你的想法與改善建議。

## 授權條款
本專案採用 Apache License 2.0，詳細內容請參考 [LICENSE](LICENSE)。

## 作者群
- Yamiyorunoshura

## 致謝
- 建立於 Python + PostgreSQL 生態系
- 感謝 Discord API 提供的整合能力
