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
- 必須啟用 PostgreSQL 擴充套件：`pg_cron`、`pgcrypto`
- 推薦使用 `uv` 作為套件管理工具

## 安裝步驟
```bash
# 取得原始碼
git clone https://github.com/Yamiyorunoshura/DRoASMS.git

# 進入專案目錄
cd DRoASMS

# 建立虛擬環境（可自選管理工具）
python3 -m venv .venv
source .venv/bin/activate  # Windows 使用 .venv\Scripts\activate

# 安裝專案依賴
uv sync  # 推薦使用 uv
# 或
pip install -e .
```

## 環境設定
複製 `.env.example` 產生 `.env` 檔案，填入必要的 Discord 憑證與設定：

```env
DISCORD_TOKEN=你的Discord機器人令牌
DATABASE_URL=postgresql://username:password@localhost/dbname
DISCORD_GUILD_ALLOWLIST=伺服器ID1,伺服器ID2  # 選填
```

若需要多個環境設定，可搭配 `.env.development.local`、`.env.production.local` 等檔案與設定管理工具。

## 資料庫設定
```bash
# 執行資料庫遷移
alembic upgrade head

# 初始化經濟系統配置（可選）
python -m src.db.seeds.initial_config
```

## 運行機器人
```bash
# 啟動機器人
python -m src.bot.main
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

### Q: 如何修改伺服器的經濟設定？
A: 目前需要直接修改資料庫中的 `economy_configurations` 表格，未來版本將提供管理命令。

### Q: 為什麼機器人沒有回應我的命令？
A: 請確認：
- 機器人在線上且有權限存取頻道
- 命令格式正確
- 機器人有讀取訊息和發送訊息的權限

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
