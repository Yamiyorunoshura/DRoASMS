# 參考資料

本目錄包含 DRoASMS 專案的參考資料，包括術語表、常見問題、故障排除指南與其他技術參考。

## 文件列表

- [術語表](glossary.md) - 專案相關術語與概念解釋（待撰寫）
- [常見問題](faq.md) - 常見問題與解答（待撰寫）
- [故障排除](troubleshooting.md) - 問題診斷與解決方案（待撰寫）
- [命令參考](command-reference.md) - 所有 Discord 命令的完整參考（待撰寫）
- [環境變數參考](environment-variables.md) - 所有環境變數說明（待撰寫）
- [錯誤代碼參考](error-codes.md) - 系統錯誤代碼與含義（待撰寫）
- [性能指標](performance-metrics.md) - 系統性能指標與監控（待撰寫）
- [安全指南](security-guide.md) - 安全最佳實踐與配置（待撰寫）

## 快速參考

### 常用命令

#### 開發命令
```bash
# 安裝依賴
uv sync

# 執行格式化
make format

# 執行 lint 檢查
make lint

# 執行類型檢查
make type-check

# 執行測試
make test-unit

# 執行完整 CI 檢查
make ci-local
```

#### 資料庫命令
```bash
# 執行遷移
uv run alembic upgrade head

# 降級遷移
uv run alembic downgrade -1

# 產生新遷移
uv run alembic revision --autogenerate -m "描述"

# 初始化配置
uv run -m src.db.seeds.initial_config
```

#### Docker 命令
```bash
# 啟動所有服務
docker compose up -d

# 停止服務
docker compose down

# 查看日誌
docker compose logs -f bot

# 重新建置容器
docker compose build --pull bot
```

### 配置參考

#### 必要環境變數
```env
DISCORD_TOKEN=你的Discord機器人令牌
DATABASE_URL=postgresql://username:password@127.0.0.1:5432/dbname
```

#### 可選環境變數
```env
# 伺服器白名單（逗號分隔）
DISCORD_GUILD_ALLOWLIST=伺服器ID1,伺服器ID2

# 啟用轉帳事件池（建議 true）
TRANSFER_EVENT_POOL_ENABLED=true

# 每日轉帳上限（0 表示無限制）
TRANSFER_DAILY_LIMIT=1000

# 冷卻時間（秒）
TRANSFER_COOLDOWN_SECONDS=300

# 日誌等級
LOG_LEVEL=INFO
```

### 錯誤代碼速查

| 代碼 | 含義 | 建議動作 |
|------|------|----------|
| 64 | 缺少必要環境變數 | 檢查 `.env` 檔案設定 |
| 69 | 依賴服務不可用 | 檢查資料庫連線與狀態 |
| 70 | 遷移失敗 | 檢查資料庫權限與擴展 |
| 78 | 無效配置 | 檢查環境變數格式與值 |
| 100 | 餘額不足 | 檢查發送者餘額 |
| 101 | 冷卻時間內 | 等待冷卻時間結束 |
| 102 | 超過每日限制 | 等待次日重置或調整限制 |
| 200 | 權限不足 | 檢查用戶權限與角色 |

## 技術規格

### 系統需求
- **Python**: 3.13（使用 `uv python pin 3.13` 鎖定）
- **PostgreSQL**: 15+ 版本，支援 pgcrypto 擴展
- **記憶體**: 最少 512MB，建議 1GB+
- **儲存空間**: 最少 100MB，視交易記錄量增加

### 資料庫擴展
- **pgcrypto**: 必需，用於加密功能與 UUID 生成
- **pg_cron**: 選用，用於自動化任務（交易記錄歸檔）

### 性能指標
- **啟動時間**: P95 ≤ 120 秒
- **轉帳延遲**: P95 ≤ 5 秒（同步模式）
- **事件池處理**: P95 ≤ 30 秒（異步模式）
- **資料庫連線**: 最大 20 個連線池大小

## 最佳實踐

### 部署最佳實踐
1. 使用 Docker 容器化部署確保環境一致性
2. 配置適當的資料庫連線池大小
3. 啟用轉帳事件池避免互動逾時
4. 設置監控與告警機制
5. 定期備份資料庫與審計記錄

### 安全最佳實踐
1. 定期旋轉 Discord Token 與資料庫密碼
2. 限制 Discord 伺服器白名單避免未授權訪問
3. 審查管理員操作記錄與異常活動
4. 保持依賴套件更新至最新安全版本
5. 使用環境變數管理敏感資訊

### 性能最佳實踐
1. 啟用 Cython 編譯提升核心模組性能
2. 配置適當的冷卻時間與每日限制
3. 定期歸檔舊交易記錄保持資料庫效能
4. 監控系統資源使用與瓶頸點
5. 使用索引優化常用查詢路徑

## 故障排除流程

### 基本檢查
1. **檢查日誌**: `docker compose logs -f bot` 或查看應用日誌
2. **檢查狀態**: `docker compose ps` 確認服務運行狀態
3. **檢查連線**: `pg_isready -h 127.0.0.1 -p 5432` 確認資料庫可達
4. **檢查配置**: 確認 `.env` 檔案設定正確

### 常見問題診斷

#### 機器人無法啟動
- 症狀: 容器反覆重啟或立即退出
- 檢查: 日誌中的錯誤訊息，常見原因：
  - 缺少 `DISCORD_TOKEN`
  - 無效的 `DATABASE_URL`
  - 資料庫連線失敗
  - 遷移執行失敗

#### 命令無回應
- 症狀: 輸入命令後機器人無反應
- 檢查:
  - 機器人是否在線上
  - 命令權限是否正確
  - 是否在允許的伺服器中
  - 命令格式是否正確

#### 轉帳失敗
- 症狀: 轉帳命令顯示錯誤
- 檢查:
  - 餘額是否充足
  - 是否在冷卻時間內
  - 是否超過每日限制
  - 目標用戶是否有效

### 日誌分析

#### 關鍵日誌事件
- `bot.ready`: 機器人完成啟動與初始化
- `db.connect.success`: 資料庫連線成功
- `transfer.executed`: 轉帳成功執行
- `transfer.failed`: 轉帳失敗，包含原因
- `proposal.created`: 治理提案建立
- `proposal.resolved`: 提案決議完成

#### 日誌等級
- `ERROR`: 需要立即關注的錯誤
- `WARN`: 潛在問題或異常情況
- `INFO`: 正常業務流程記錄
- `DEBUG`: 詳細除錯資訊（開發時啟用）

## 支援與資源

### 官方資源
- **GitHub 倉庫**: https://github.com/Yamiyorunoshura/DRoASMS
- **問題追蹤**: https://github.com/Yamiyorunoshura/DRoASMS/issues
- **討論區**: https://github.com/Yamiyorunoshura/DRoASMS/discussions

### 相關文檔
- [Discord.py 文檔](https://discordpy.readthedocs.io/)
- [PostgreSQL 文檔](https://www.postgresql.org/docs/)
- [Pydantic 文檔](https://docs.pydantic.dev/)
- [uv 文檔](https://docs.astral.sh/uv/)

### 社群支援
- 在 GitHub Discussions 提問
- 查閱現有 Issue 與 Pull Request
- 參考專案範例與測試程式碼

## 版本相容性

### Python 版本
- 專案鎖定 Python 3.13，不保證其他版本相容性
- 使用 `uv python pin 3.13` 確保版本一致性

### 資料庫版本
- 支援 PostgreSQL 15+
- 遷移系統可能依賴特定版本功能
- 降級資料庫版本可能需要手動調整遷移

### 依賴套件
- 依賴版本鎖定在 `uv.lock` 檔案中
- 定期執行 `uv sync` 更新至最新相容版本
- 重大版本更新可能需要程式碼調整
