# DRoASMS

DRoASMS 是以 Python 打造的 Discord 機器人原型，專注於社群的經濟系統與治理流程。

## 功能特色

### 經濟系統

- **虛擬貨幣系統**：完整的社群內經濟體系，支援點數轉移、餘額查詢和交易歷史
- **個人面板**：整合式個人經濟管理介面（`/personal_panel`）
  - 首頁分頁：查看當前餘額和帳戶狀態
  - 財產分頁：查看完整交易歷史，支援分頁顯示
  - 轉帳分頁：支援轉帳給使用者或政府機構（常任理事會、最高人民會議、國務院及其下屬部門）
- **點數轉移**：成員之間可以自由轉移虛擬貨幣，並可選擇添加備註
- **管理員調整**：授權管理員可以調整成員點數，支援加值或扣點

### 權限系統

- **分級權限控制**：基於 Discord 角色的權限管理
- **管理員專用功能**：調整點數和查看他人餘額需要特定權限
- **安全審計**：所有管理員操作都會記錄並可追蹤

### 交易限流機制

- **每日轉帳限制（可關閉）**：預設已關閉；如需啟用，設定環境變數 `TRANSFER_DAILY_LIMIT` 為正整數（例如 1000）
- **冷卻時間**：頻繁操作後的短暫限制，確保系統穩定
- **餘額保護**：防止餘額變為負數的保護機制

### 轉帳事件池（Transfer Event Pool）

- **異步轉帳處理**：啟用事件池模式後，轉帳請求將進入異步處理流程
- **自動重試機制**：當檢查失敗時（餘額不足、冷卻中、每日上限），系統會自動重試（指數退避，最多 10 次）
- **事件驅動架構**：透過 PostgreSQL NOTIFY/LISTEN 機制實現檢查與執行的解耦
- **啟用方式**：設定環境變數 `TRANSFER_EVENT_POOL_ENABLED=true`（預設 false，向後相容）
- 詳細架構說明請參考 [轉帳事件池文件](docs/transfer-event-pool.md)

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

## Cython 編譯工作流程

1. `make unified-compile`：呼叫 `scripts/compile_modules.py compile`，依 `pyproject.toml` 的 `[tool.cython-compiler.targets]` 逐一產出 `.so`。
2. `make unified-compile-test`：執行 `[tool.cython-compiler].test_command`（預設為性能測試）。
3. `make unified-status`：檢視 `build/cython/compile_report.json`，確認成功/失敗與輸出位置。
4. `make unified-compile-clean`：清掉 `build/cython` 與 `src/cython_ext` 中的 `.so`，回復純 Python fallback。
5. `make unified-refresh-baseline`：在編譯成功後附加 `--refresh-baseline`，重新量測模組匯入基線。

詳細設定與疑難排解請見 `docs/unified-compiler-guide.md`。

## 環境設定

複製 `.env.example` 產生 `.env` 檔案，填入必要的 Discord 憑證與設定（括號內為預設）：

```env
DISCORD_TOKEN=你的Discord機器人令牌
DATABASE_URL=postgresql://username:password@127.0.0.1:5432/dbname
DISCORD_GUILD_ALLOWLIST=伺服器ID1,伺服器ID2  # 選填
# 啟用轉帳事件池（建議 true，可避免互動逾時與長時操作）：
TRANSFER_EVENT_POOL_ENABLED=true
# （選填）每日轉帳上限，僅事件池檢查使用，預設 500
# TRANSFER_DAILY_LIMIT=1000
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
- 遷移策略：啟動時先嘗試 `alembic upgrade head`，若失敗（常見於 004 需要 `pg_cron`）才回退到 `ALEMBIC_UPGRADE_TARGET`（預設 `003_economy_adjustments`）
- 初次啟動會自動在資料庫建立 `pgcrypto` 擴充（見 `docker/init/001_extensions.sql`）
- 若需 `pg_cron` 或使用最新功能（如轉帳事件池），建議改用支援該擴充的映像或自行安裝後，將環境變數 `ALEMBIC_UPGRADE_TARGET` 設為 `head`

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
- 已執行 `uv run alembic upgrade head`（或至少升級到 `003_economy_adjustments`；容器啟動亦會先嘗試升到 head）

## 治理（Council Governance，MVP）

本功能提供「常任理事會」以提案＋投票決議是否由「理事會帳戶」向指定成員執行轉帳。

- 設定理事角色：`/council config_role <role>`（需管理員或管理伺服器權限）
- 建立轉帳提案：`/council propose_transfer <target> <amount> <description> [attachment_url]`（僅理事可用）
  - 建案瞬間鎖定理事名冊快照 N，門檻 `T = floor(N/2) + 1`，截止時間 +72 小時
  - 同一伺服器進行中提案最多 5 個
  - 會以 DM 向理事發送投票訊息（按鈕：同意／反對／棄權）
  - 進行中僅顯示合計票數；結案時揭露個別最終投票
  - 達門檻即嘗試執行轉帳；若餘額不足或其他錯誤 → 記錄「執行失敗」
  - 截止前 24 小時會 DM 提醒未投者
  - 截止未達門檻 → 「已逾時」
- 撤案：`/council cancel <proposal_id>`（無人投票前可撤）
- 匯出：`/council export <start> <end> <json|csv>`（管理者）

### 理事會面板（Panel）

- 開啟面板：`/council panel`（僅理事）
  - 在單一面板完成：建立提案（Modal）、選擇進行中提案並投票、（僅提案人且無票前）撤案
  - 匯出：按「匯出資料」按鈕取得 `/council export` 使用指引（仍由 Slash 指令執行）
  - 面板為 ephemeral（僅自己可見），投票按鈕沿用 persistent `VotingView`（重開機後仍有效）

注意事項：

- 需要於 Discord 開發者後台啟用「成員 Intent」以取得角色成員清單（本專案已於程式中啟用 `intents.members = True`）。
- MVP 僅以 DM 進行互動與通知，沒有公開頻道摘要。

## 國務院治理（State Council Governance）

本功能提供「國務院」以部門為單位的治理系統，支援部門配置、點數發行與轉帳。

- 設定國務院領袖：`/state_council config_leader <leader|leader_role>`（需管理員或管理伺服器權限）
- 開啟國務院面板：`/state_council panel`（僅國務院領袖可用）
  - 部門管理：設定各部門領導人身分組、稅率、發行上限
  - 點數發行：向各部門發行點數
  - 部門轉帳：各部門可向成員轉帳（透過政府帳戶）
  - 匯出功能：匯出部門配置與發行記錄
- `/adjust` 與 `/transfer` 支援以理事會身分組、國務院領袖身分組、以及部門領導人身分組為目標（自動映射至對應政府帳戶）

注意事項：

- 需要於 Discord 開發者後台啟用「成員 Intent」以取得角色成員清單
- 部門轉帳透過政府帳戶執行，不受冷卻時間與每日上限限制

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

將虛擬貨幣轉移給伺服器中的其他成員或政府相關身分組。

**參數：**

- `target`（必填）：成員、理事會身分組、國務院領袖身分組，或部門領導人身分組
- `amount`（必填）：要轉出的整數點數
- `reason`（選填）：會記錄在交易歷史中的備註

**範例：**

```
/transfer @username 100                         # 轉移 100 點給指定成員
/transfer @username 50 reason:午餐費用           # 轉移 50 點並添加備註
/transfer @CouncilRole 1000 reason:理事會補助     # 對理事會公共帳戶轉帳（自動映射）
/transfer @StateLeader 500 reason:國庫撥款        # 對國務院主帳戶轉帳（領袖身分組自動映射）
/transfer @DeptLeader 300 reason:部門預算         # 對對應部門帳戶轉帳（部門領導人身分組自動映射）
```

### `/adjust`

管理員調整成員點數（正數加值，負數扣點）。

**參數：**

- `target`（必填）：要調整點數的成員或部門領導人身分組
- `amount`（必填）：可以為正數（加值）或負數（扣點）
- `reason`（必填）：將寫入審計紀錄的原因

**權限要求：**

- 需要「管理伺服器」或「系統管理員」Discord 權限

**範例：**

```
/adjust @username 100 reason:活動獎勵         # 給成員加值 100 點
/adjust @username -50 reason:違規懲罰         # 扣除成員 50 點
/adjust @DepartmentLeaderRole 500 reason:部門預算  # 調整部門政府帳戶餘額
```

### `/currency_config`

設定該伺服器的貨幣名稱和圖示（僅限管理員）。

**參數：**

- `name`（選填）：貨幣名稱（1-20 字元）
- `icon`（選填）：貨幣圖示（單一 emoji 或 Unicode 字元，最多 10 字元）

**權限要求：**

- 需要「管理伺服器」或「系統管理員」Discord 權限

**範例：**

```
/currency_config name:金幣 icon:🪙          # 設定貨幣名稱為「金幣」，圖示為 🪙
/currency_config name:點數                   # 僅更新貨幣名稱為「點數」
/currency_config icon:💰                     # 僅更新貨幣圖示為 💰
```

**說明：**

- 設定後，所有經濟相關指令（`/balance`、`/transfer`、`/adjust`、`/history`）和國務院面板都會使用新的貨幣名稱和圖示
- 未設定時，預設使用「點」作為貨幣名稱，無圖示
- 每個伺服器可以獨立設定自己的貨幣配置

### `/help`

顯示所有可用指令的說明，或查詢特定指令的詳細資訊。

**參數：**

- `command`（選填）：要查詢的指令名稱（例如：transfer、council panel）

**範例：**

```
/help                    # 顯示所有可用指令列表
/help transfer           # 查詢 /transfer 指令的詳細說明
/help state_council      # 查詢國務院治理相關指令
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

- 預設「無上限」。自遷移 `025_unlimited_daily_limit_by_default` 起，若未設定
  `TRANSFER_DAILY_LIMIT`（或設為 0、負數），系統視為無上限且此檢查一律通過。
  若要開啟限制，將 `TRANSFER_DAILY_LIMIT` 設為正整數（例如 1000）。
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
  1. 依系統文件安裝 `pg_cron` 並於 `postgresql.conf` 加入 `shared_preload_libraries='pg_cron'` 後重啟，再執行 `uv run alembic upgrade head`
  2. 先將資料庫升級到 `003_economy_adjustments`，待環境允許後再升到 head

### 認證失敗（password authentication failed）

- 請確認 `DATABASE_URL` 的使用者、密碼、資料庫名稱一致，並且該使用者已被授權連線與存取資料庫。

### Q: 如何修改伺服器的經濟設定？

A: 可以使用 `/currency_config` 指令設定貨幣名稱和圖示。其他經濟設定（如每日轉帳限制）可透過環境變數 `TRANSFER_DAILY_LIMIT` 設定。

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

### 執行測試

#### 方法 1：本機執行（需要本地環境）

```bash
# 執行所有測試（並行執行，自動偵測 CPU 核心數）
uv run pytest -n auto

# 執行特定測試套件
uv run pytest tests/unit/ -v
uv run pytest tests/integration/ -v

# 查看測試覆蓋率報告
uv run pytest --cov=src --cov-report=html --cov-report=term
# HTML 報告會產生在 htmlcov/ 目錄
```

#### 方法 2：使用測試容器（推薦，環境一致）

測試容器提供一致的測試環境，無需手動配置本地環境，可在本地運行完整的 CI 測試流程。

**建置測試容器**

```bash
# 建置測試容器映像檔
make test-container-build
```

**執行測試**

```bash
# 執行所有測試（不含整合測試）
make test-container
# 或指定測試類型
make test-container-unit       # 單元測試
make test-container-contract   # 合約測試
make test-container-integration # 整合測試（需要 Discord Token）
make test-container-performance # 效能測試
make test-container-db         # 資料庫測試
make test-container-economy    # 經濟相關測試
make test-container-council    # 議會相關測試
make test-container-all        # 所有測試（含整合測試）
make test-container-ci         # 完整 CI 流程（格式化、lint、MyPy、Pyright、所有測試含整合測試）
```

**查看覆蓋率報告**
測試容器會將覆蓋率報告輸出到 `htmlcov/` 目錄，可在本地查看：

```bash
# 執行測試後，查看 HTML 報告
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**測試容器特性**

- 基於 Python 3.13，包含所有測試依賴（dev dependencies）
- 自動連接到 Compose 中的 PostgreSQL 服務進行資料庫測試
- 支援環境變數傳遞（透過 `.env` 檔案）
- 測試目錄掛載為唯讀，開發時可即時更新測試檔案
- 覆蓋率報告自動掛載到本地 `htmlcov/` 目錄

### 程式碼品質工具

```bash
# 型別檢查
# MyPy（成熟穩定的 Python 類型檢查器）
uv run mypy src/

# Pyright（Microsoft 開發的類型檢查器，嚴格模式）
uv run pyright src/

# 程式碼品質檢查
uv run ruff check .

# 程式碼格式化
uv run black src/
```

**雙重類型檢查策略**
專案採用 MyPy 和 Pyright 雙重類型檢查來提供最全面的類型安全：

- **MyPy**：成熟穩定，擁有豐富的生態系統和對 Python 特性的良好支援
- **Pyright**：Microsoft 開發，擁有優異的類型推斷能力，能捕獲 MyPy 可能遺漏的類型錯誤
- **嚴格模式**：兩個檢查器都在嚴格模式下運行，確保最高的類型安全標準

### Pre-commit Hooks

專案已配置 pre-commit hooks，在提交前自動執行格式化與檢查：

```bash
# 安裝 pre-commit hooks
uv run pre-commit install

# 手動執行所有 hooks
uv run pre-commit run --all-files
```

### 本地執行 CI/CD 檢查

為避免推送後才發現 CI 檢查失敗，可以在本地提前執行所有 CI 檢查。

#### 方法 1：使用 Makefile（推薦）

專案提供了 `Makefile`，統一管理所有檢查命令：

```bash
# 查看所有可用命令
make help

# 安裝依賴
make install

# 安裝並啟用 pre-commit hooks
make install-pre-commit

# 執行格式化
make format

# 執行 lint 檢查
make lint

# lint 並自動修復
make lint-fix

# 執行型別檢查（MyPy）
make type-check

# 執行型別檢查（Pyright）
make pyright-check

# 檢查格式化（不修改檔案）
make format-check

# 執行 Cython 編譯檢查（增量編譯，錯誤不阻止執行）
make compile-check

# 執行所有本地 CI 檢查（格式化、lint、MyPy、Pyright、pre-commit、Cython編譯檢查）
make ci-local

# 執行所有測試（不含整合測試）
make ci-test

# 執行完整的 CI 檢查（包含所有測試）
make ci-full

# 執行特定測試套件
make test-unit
make test-contract
make test-economy
make test-db
make test-council

# 或使用測試容器執行（環境一致，推薦）
make test-container-unit
make test-container-contract
make test-container-economy
make test-container-db
make test-container-council
```

#### 方法 2：使用 Pre-commit（最簡單）

Pre-commit hooks 會在 `git commit` 時自動執行，但也可以手動觸發：

```bash
# 安裝 pre-commit hooks（只需執行一次）
uv run pre-commit install

# 對所有檔案執行檢查（等同於 CI 中的 pre-commit-check）
uv run pre-commit run --all-files
```

#### 方法 3：使用 act（運行 GitHub Actions）

如果要完全模擬 GitHub Actions 的執行環境，可以使用 [act](https://github.com/nektos/act)：

```bash
# 安裝 act（macOS）
brew install act

# 或使用其他安裝方式見 https://github.com/nektos/act#installation

# Linux 上安裝 act
curl https://raw.githubusercontent.com/nektos/act/master/install.sh | sudo bash

# 執行 CI workflow
act push

# 執行特定 job（例如只執行 lint）
act -j lint
```

**注意**：act 需要 Docker，且執行整合測試時可能需要額外設定。

#### 推薦工作流程

1. **開發過程中**：啟用 pre-commit hooks 自動檢查

   ```bash
   make install-pre-commit
   ```

2. **提交前**：執行快速 CI 檢查

   ```bash
   make ci-local
   ```

3. **重要變更前**：執行完整測試
   ```bash
   make ci-full
   ```

### 推薦本地開發工作流程

為確保程式碼品質並與 CI 環境保持一致，建議採用以下開發流程：

1. **開發過程中**：啟用 pre-commit hooks 自動檢查

   ```bash
   make install-pre-commit
   ```

2. **提交前**：執行快速本地 CI 檢查

   ```bash
   make ci-local  # 包含 MyPy + Pyright 雙重類型檢查
   ```

3. **重要變更前**：執行完整 CI 流程（包含整合測試）

   ```bash
   make ci  # 使用測試容器執行完整 CI 流程
   ```

4. **類型檢查**：確保兩個類型檢查器都通過
   ```bash
   make type-check     # MyPy 檢查
   make pyright-check  # Pyright 檢查
   ```

### 開發工具說明

#### Pydantic 設定管理

- 使用 Pydantic v2 進行設定驗證與載入
- `BotSettings`：Discord bot 設定（`src/config/settings.py`）
- `PoolConfig`：資料庫連線池設定（`src/config/db_settings.py`）
- 自動驗證環境變數格式與型別，提供友善的錯誤訊息

#### Faker 測試資料生成

- 在測試中使用 Faker 自動生成假資料（guild_id、user_id、金額等）
- 支援中文與英文 locale
- 使用方式：在測試中注入 `faker` fixture

#### Hypothesis 屬性測試

- 使用 Hypothesis 進行屬性測試，自動生成邊界案例
- 適合測試複雜邏輯，如轉帳驗證、餘額計算等
- 範例檔案：`tests/unit/test_balance_validation_property.py`
- 使用方式：

  ```python
  from hypothesis import given, strategies as st

  @given(
      balance=st.integers(min_value=0, max_value=1_000_000_000),
      amount=st.integers(min_value=1, max_value=1_000_000_000),
  )
  def test_balance_check(balance: int, amount: int) -> None:
      # Hypothesis 會自動生成多組測試案例
      check_result = 1 if balance >= amount else 0
      assert check_result in (0, 1)
  ```

#### Tenacity 重試邏輯

- 使用 Tenacity 簡化重試邏輯實作
- 提供指數退避與抖動策略
- 已應用於轉帳事件池的重試機制

#### 測試覆蓋率

- 使用 pytest-cov 產生覆蓋率報告
- CI 中自動上傳 HTML 報告作為 artifact
- 覆蓋率設定見 `pyproject.toml` 的 `[tool.coverage.*]` 區段

#### 並行測試執行

- 使用 pytest-xdist 加速測試執行
- 預設使用 `-n auto` 自動偵測 CPU 核心數
- 確保測試使用獨立資料庫連線池與交易隔離

#### Cython 編譯（性能優化）

- 已為核心模塊提供 Cython 編譯管線，以獲得顯著性能提升：
  - 經濟系統模塊：`adjustment_service`, `transfer_service`, `balance_service`, `transfer_event_pool`, `currency_config_service`
  - 數據網關：`economy_adjustments`, `economy_transfers`, `economy_queries`, `economy_pending_transfers`, `economy_configuration`
  - 治理系統模塊：`council_governance`, `supreme_assembly_governance`, `state_council_governance`
- 編譯輸出至 `src/cython_ext/` 目錄
- 指令：
  - 編譯：`make cython-compile` 或 `python scripts/compile_modules.py compile`
  - 測試：`make cython-test` 或 `python scripts/compile_modules.py test`
  - 性能基線：`make unified-refresh-baseline`
- 性能提升：
  - 編譯速度提升：7-12 倍
  - 運行時性能提升：5-10 倍
  - 記憶體效率優化
- 支持並行編譯和增量編譯功能

#### 依賴注入容器（Dependency Injection Container）

專案使用自訂的依賴注入容器來管理服務依賴，取代模組層級的全域單例模式。這使得測試更容易（可替換依賴）並提供統一的依賴管理機制。

**核心概念：**

- 容器位於 `src/infra/di/`
- 支援三種生命週期：`SINGLETON`（單例）、`FACTORY`（每次新建）、`THREAD_LOCAL`（每執行緒一個）
- 自動從建構子參數推斷依賴（基於型別提示）

**使用方式：**

```python
from src.infra.di.container import DependencyContainer
from src.infra.di.lifecycle import Lifecycle

# 建立容器
container = DependencyContainer()

# 註冊服務（自動推斷依賴）
container.register(MyService, lifecycle=Lifecycle.SINGLETON)

# 解析服務
service = container.resolve(MyService)
```

**測試中使用：**

```python
# 使用 conftest.py 提供的 di_container fixture
def test_my_feature(di_container):
    # 可以替換依賴為 mock
    mock_service = Mock()
    di_container.register_instance(MyService, mock_service)

    # 測試邏輯...
```

**在命令模組中使用：**
命令模組的 `register()` 函數現在接受可選的 `container` 參數：

```python
def register(tree: app_commands.CommandTree, *, container: DependencyContainer | None = None):
    if container is None:
        # 向後相容：使用舊的實例化方式
        service = MyService()
    else:
        service = container.resolve(MyService)
    # ...
```

詳細實作請參考 `src/infra/di/` 目錄。

## 生產環境實作要求

根據專案憲章原則 X，本專案禁止在生產環境中使用模擬實現：

- **真實資料整合**：所有外部服務整合（Discord API、資料庫連線、第三方服務）必須使用真實端點與認證
- **禁止模擬資料**：生產環境程式碼不得包含 mock data 或假資料接入
- **環境區隔**：開發階段的模擬介面必須明確標記為開發用途，並在發行前替換為真實實現
- **驗證機制**：若需使用模擬實現進行開發，必須提供明確的環境配置區隔（如 `DEVELOPMENT_MODE=true`），並確保生產環境無法啟用此模式

## 貢獻指南

歡迎提交 Issue 或 Pull Request，分享你的想法與改善建議。

## 授權條款

本專案採用 Apache License 2.0，詳細內容請參考 [LICENSE](LICENSE)。

## 作者群

- Yamiyorunoshura

## 致謝

- 建立於 Python + PostgreSQL 生態系
- 感謝 Discord API 提供的整合能力
