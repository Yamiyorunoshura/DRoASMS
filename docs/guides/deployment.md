# 部署指南

本指南提供 DRoASMS 專案在生產環境的部署最佳實踐，包括系統架構、安全配置、監控告警與維護流程。

## 部署架構

### 推薦生產架構
```
┌─────────────────────────────────────────────────────────┐
│                   負載平衡器 / 反向代理                   │
│                  (可選，多實例部署時需要)                  │
└─────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────┐
│                   應用程式層 (DRoASMS Bot)                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   實例 1    │  │   實例 2    │  │   實例 N    │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────┐
│                    資料庫層 (PostgreSQL)                  │
│  ┌─────────────────────────────────────────────────┐    │
│  │                  主從複製架構                     │    │
│  │  ┌─────────────┐          ┌─────────────┐      │    │
│  │  │   主資料庫   │ ──────▶  │   從資料庫   │      │    │
│  │  └─────────────┘          └─────────────┘      │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
                               │
┌─────────────────────────────────────────────────────────┐
│                    監控與日誌層                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   指標收集   │  │   日誌聚合   │  │   告警系統   │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 單實例最小部署
對於小型社群，單實例部署已足夠：
- 1 台應用伺服器 (2GB RAM, 2 CPU)
- 1 台資料庫伺服器 (2GB RAM, 2 CPU) 或使用託管資料庫
- 靜態 IP 或域名

## 前置準備

### 系統要求
| 資源 | 最小規格 | 推薦規格 | 說明 |
|------|----------|----------|------|
| CPU | 2 核心 | 4+ 核心 | 支援併發處理 |
| 記憶體 | 2GB | 4GB+ | 應用 + 資料庫 |
| 儲存空間 | 20GB | 50GB+ | 日誌與資料庫增長 |
| 網路頻寬 | 10Mbps | 100Mbps | Discord API 通訊 |

### 軟體要求
- **作業系統**: Ubuntu 22.04 LTS 或 Rocky Linux 9（推薦）
- **容器運行時**: Docker 24+ 或 Podman 4+
- **資料庫**: PostgreSQL 15+ 與 pgcrypto 擴展
- **反向代理**: Nginx 或 Traefik（可選）

### 網路要求
- 允許輸出連線到 Discord API (`*.discord.com`)
- 允許資料庫連線（如果資料庫分離部署）
- HTTPS 終端（如果使用 Webhook 或自訂儀表板）

## 部署方法

### 方法一：Docker Compose（推薦）
最簡單的部署方式，適合單機部署：

```bash
# 1. 準備環境變數
cp .env.example .env.production
# 編輯 .env.production，填入生產環境設定

# 2. 調整 Compose 配置（如果需要）
cp compose.yaml compose.production.yaml
# 編輯 compose.production.yaml，調整資源限制與網路配置

# 3. 啟動服務
docker compose -f compose.production.yaml up -d

# 4. 檢查狀態
docker compose -f compose.production.yaml ps
docker compose -f compose.production.yaml logs -f bot
```

**生產環境 Compose 配置建議：**
```yaml
services:
  bot:
    image: your-registry/droasms:latest
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
        reservations:
          cpus: '1'
          memory: 1G
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import sys; sys.exit(0)"]
      interval: 30s
      timeout: 10s
      retries: 3

  postgres:
    image: postgres:16
    deploy:
      resources:
        limits:
          cpus: '2'
          memory: 2G
    restart: unless-stopped
    command: |
      postgres
      -c shared_preload_libraries=pg_cron
      -c cron.database_name=economy
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./docker/init:/docker-entrypoint-initdb.d
```

### 方法二：Kubernetes
適合大規模部署與高可用性需求：

```yaml
# kubernetes/deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: droasms-bot
spec:
  replicas: 3
  selector:
    matchLabels:
      app: droasms-bot
  template:
    metadata:
      labels:
        app: droasms-bot
    spec:
      containers:
      - name: bot
        image: your-registry/droasms:latest
        env:
        - name: DISCORD_TOKEN
          valueFrom:
            secretKeyRef:
              name: discord-secret
              key: token
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: database-secret
              key: url
        resources:
          limits:
            memory: "1Gi"
            cpu: "500m"
          requests:
            memory: "512Mi"
            cpu: "250m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10
```

### 方法三：傳統系統服務
不使用容器，直接在系統上運行：

```bash
# 1. 安裝系統依賴
sudo apt-get update
sudo apt-get install -y python3.13 python3.13-venv postgresql postgresql-contrib

# 2. 建立專用使用者
sudo useradd -r -s /bin/false droasms
sudo mkdir -p /opt/droasms
sudo chown -R droasms:droasms /opt/droasms

# 3. 複製程式碼
sudo -u droasms git clone https://github.com/Yamiyorunoshura/DRoASMS.git /opt/droasms/app

# 4. 安裝應用程式
cd /opt/droasms/app
sudo -u droasms uv sync --python 3.13

# 5. 設定系統服務
sudo cp /opt/droasms/app/deploy/droasms.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable droasms
sudo systemctl start droasms
```

## 環境配置

### 生產環境變數
```env
# .env.production

# Discord 設定
DISCORD_TOKEN=你的生產環境Token
DISCORD_GUILD_ALLOWLIST=生產伺服器ID1,生產伺服器ID2

# 資料庫設定
DATABASE_URL=postgresql://user:password@db-host:5432/economy_prod?sslmode=require

# 安全設定
DEVELOPMENT_MODE=false
LOG_LEVEL=INFO

# 性能設定
TRANSFER_EVENT_POOL_ENABLED=true
TRANSFER_DAILY_LIMIT=1000
TRANSFER_COOLDOWN_SECONDS=300

# 監控設定
METRICS_ENABLED=true
TRACING_ENABLED=true
```

### 資料庫配置
```sql
-- 生產資料庫最佳化配置
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '2GB';
ALTER SYSTEM SET maintenance_work_mem = '256MB';
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET default_statistics_target = 100;

-- 建立專門的使用者
CREATE USER droasms_prod WITH PASSWORD '強密碼';
GRANT CONNECT ON DATABASE economy_prod TO droasms_prod;

-- 啟用必要擴展
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_cron;
```

### 安全配置
```bash
# 防火牆規則 (UFW)
sudo ufw allow 22/tcp          # SSH
sudo ufw allow 5432/tcp        # PostgreSQL (如果外部存取)
sudo ufw --force enable

# 設定 fail2ban
sudo apt-get install -y fail2ban
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local
# 編輯配置保護 SSH 與 PostgreSQL
```

## 監控與日誌

### 應用程式日誌
```bash
# 日誌輪轉配置 (/etc/logrotate.d/droasms)
/var/log/droasms/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 droasms droasms
    postrotate
        systemctl reload droasms > /dev/null 2>&1 || true
    endscript
}
```

### 指標收集
```python
# 內建遙測配置
from src.infra.telemetry import metrics, tracing

# 啟用 Prometheus 指標端點
if settings.metrics_enabled:
    metrics.configure_prometheus(port=9090)

# 啟用分散式追蹤
if settings.tracing_enabled:
    tracing.configure_jaeger(
        service_name="droasms-bot",
        agent_host="jaeger-agent",
        agent_port=6831
    )
```

### 健康檢查端點
```python
# 新增健康檢查路由
@app.route('/health')
async def health_check():
    return json_response({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "database": await check_database(),
            "discord": await check_discord()
        }
    })
```

## 備份與災難恢復

### 資料庫備份策略
```bash
# 每日完整備份
0 2 * * * pg_dump -Fc economy_prod > /backup/economy_prod_$(date +%Y%m%d).dump

# 每小時 WAL 歸檔
archive_command = 'cp %p /backup/wal/%f'

# 備份保留策略
find /backup -name "*.dump" -mtime +30 -delete
find /backup/wal -name "*.wal" -mtime +7 -delete
```

### 恢復程序
```bash
# 停止應用程式
systemctl stop droasms

# 恢復資料庫
pg_restore -d economy_prod /backup/economy_prod_最新備份.dump

# 恢復 WAL 日誌（如果需要時間點恢復）
cp /backup/wal/* /var/lib/postgresql/wal_archive/
# 在 postgresql.conf 中設定恢復目標

# 重新啟動
systemctl start droasms
```

### 災難恢復檢查清單
1. **識別故障**：監控告警觸發
2. **隔離問題**：停止受影響服務
3. **恢復資料**：從備份恢復資料庫
4. **驗證完整性**：檢查資料一致性
5. **重新上線**：逐步恢復服務
6. **事後分析**：撰寫事故報告與改進措施

## 安全最佳實踐

### 應用程式安全
1. **最小權限原則**：應用程式使用者僅有必要權限
2. **環境變數管理**：使用密鑰管理服務（如 HashiCorp Vault）
3. **依賴掃描**：定期掃描依賴套件漏洞
4. **輸入驗證**：所有使用者輸入都經過驗證
5. **輸出編碼**：防止 XSS 與注入攻擊

### 網路安全
1. **網路隔離**：資料庫不直接暴露在公網
2. **TLS 加密**：所有外部通訊使用 TLS
3. **速率限制**：防止濫用與 DDoS 攻擊
4. **WAF 配置**：使用 Web 應用防火牆
5. **VPN 存取**：管理存取透過 VPN

### 資料安全
1. **加密儲存**：敏感資料加密儲存
2. **資料遮罩**：日誌中的敏感資料遮罩
3. **審計日誌**：所有管理操作記錄
4. **資料保留**：制定資料保留與刪除政策
5. **合規檢查**：符合 GDPR 等法規要求

## 性能調優

### 資料庫性能
```sql
-- 重要索引
CREATE INDEX CONCURRENTLY idx_transfers_guild_member
ON economy.transfers(guild_id, member_id);

CREATE INDEX CONCURRENTLY idx_balance_guild_member
ON economy.balances(guild_id, member_id);

-- 定期維護
VACUUM ANALYZE economy.transfers;
REINDEX TABLE economy.transfers;
```

### 應用程式性能
```python
# 連線池配置
pool_config = PoolConfig(
    min_size=5,
    max_size=20,
    max_queries=50000,
    max_inactive_connection_lifetime=300.0
)

# 快取策略
from functools import lru_cache

@lru_cache(maxsize=128)
def get_currency_config(guild_id: int):
    # 快取常用配置
    pass
```

### 系統層級調優
```bash
# Linux 系統調優
sudo sysctl -w net.core.somaxconn=65535
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=65535
sudo sysctl -w vm.swappiness=10
sudo sysctl -w vm.overcommit_memory=1
```

## 擴展策略

### 垂直擴展
增加單一實例資源：
- CPU：升級到更多核心
- 記憶體：增加 RAM 容量
- 儲存：使用 SSD 提升 I/O 性能
- 網路：升級網路頻寬

### 水平擴展
增加更多實例：
1. **無狀態應用層**：增加 bot 實例數量
2. **負載平衡**：使用反向代理分配流量
3. **資料庫分片**：按 guild_id 分片資料
4. **讀寫分離**：主資料庫寫入，從資料庫讀取

### 自動擴展配置
```yaml
# Kubernetes HPA 配置
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: droasms-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: droasms-bot
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

## 維護作業

### 日常維護
```bash
# 檢查系統狀態
systemctl status droasms postgresql

# 檢查日誌
journalctl -u droasms -f

# 檢查資源使用
htop
df -h
```

### 定期維護
- **每週**：檢查日誌輪轉與磁碟空間
- **每月**：更新作業系統與安全修補
- **每季**：審計安全配置與存取權限
- **每年**：進行災難恢復演練

### 升級程序
```bash
# 1. 通知使用者維護窗口
# 2. 停止服務
systemctl stop droasms

# 3. 備份資料庫
pg_dump -Fc economy_prod > /backup/pre_upgrade_$(date +%Y%m%d).dump

# 4. 升級應用程式
git pull
uv sync
uv run alembic upgrade head

# 5. 重新啟動
systemctl start droasms

# 6. 驗證功能
# 7. 通知使用者升級完成
```

## 故障排除

### 常見問題與解決方案

#### 1. 機器人離線
```
症狀：Discord 顯示機器人離線，日誌無新訊息
```
**解決步驟：**
1. 檢查系統服務狀態：`systemctl status droasms`
2. 檢查日誌錯誤：`journalctl -u droasms -n 50`
3. 檢查網路連線：`curl https://discord.com`
4. 檢查 Token 有效性：重新生成 Token

#### 2. 資料庫連線問題
```
症狀：日誌顯示資料庫連線錯誤
```
**解決步驟：**
1. 檢查資料庫服務：`systemctl status postgresql`
2. 檢查連線字串：確認 `DATABASE_URL` 正確
3. 檢查防火牆：`sudo ufw status`
4. 檢查使用者權限：`psql -U droasms_prod -d economy_prod`

#### 3. 性能下降
```
症狀：回應緩慢，日誌顯示超時
```
**解決步驟：**
1. 檢查系統資源：`top`, `free -h`
2. 檢查資料庫效能：`pg_stat_statements`
3. 檢查慢查詢：`EXPLAIN ANALYZE`
4. 調整連線池設定

### 緊急聯絡人
- **主要維護者**: @Yamiyorunoshura
- **備援維護者**: [設定備援人員]
- **Discord 支援頻道**: [設定支援頻道]
- **監控告警**: [設定告警聯絡方式]

## 合規與法務

### 資料保護
- **隱私政策**：明確說明資料收集與使用方式
- **使用者同意**：取得使用者同意資料處理
- **資料主體權利**：支援 GDPR 資料主體權利請求
- **資料保留**：制定資料保留與刪除政策

### 服務等級協議 (SLA)
- **可用性**：99.5% 月可用性
- **支援回應**：24 小時內回應非緊急問題
- **故障恢復**：4 小時內恢復服務
- **維護窗口**：每月最多 4 小時計畫維護

### 法律聲明
- **服務條款**：明確使用條款與限制
- **免責聲明**：限制責任範圍
- **智慧財產權**：說明專案授權與貢獻者協議

## 後續步驟

部署完成後，建議：

1. **建立監控儀表板**：Grafana + Prometheus
2. **設定自動告警**：異常活動即時通知
3. **制定備份驗證程序**：定期測試備份恢復
4. **進行安全審計**：定期第三方安全評估
5. **建立知識庫**：記錄操作經驗與解決方案

## 相關資源

- [安裝指南](installation.md) - 基礎安裝步驟
- [配置參考](../reference/environment-variables.md) - 完整環境變數說明
- [監控指南](monitoring.md) - 詳細監控配置
- [安全指南](security.md) - 安全最佳實踐
