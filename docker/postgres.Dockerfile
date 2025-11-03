FROM postgres:16

# 安裝 pg_cron + pgTAP（包含伺服器端 extension 與 pg_prove CLI）
# - postgresql-16-cron: pg_cron 伺服器擴充
# - postgresql-16-pgtap: pgTAP extension
# - pgtap: pg_prove 指令，用於執行 TAP 格式的 SQL 測試
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-16-cron \
        postgresql-16-pgtap \
        pgtap \
    && rm -rf /var/lib/apt/lists/*

# 其餘設定交由 docker-compose 的 command 以 -c 參數注入
