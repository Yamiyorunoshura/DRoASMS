FROM postgres:16

# 安裝 pg_cron + pgTAP（包含伺服器端 extension 與 pg_prove CLI）
# 官方 postgres 基底映像未預設啟用 PGDG APT，故先加入來源與金鑰再安裝：
# - postgresql-16-cron: pg_cron 伺服器擴充
# - postgresql-16-pgtap: pgTAP extension
# - pgtap: pg_prove 指令，用於執行 TAP 格式的 SQL 測試
RUN set -eux; \
    export DEBIAN_FRONTEND=noninteractive; \
    apt-get update; \
    apt-get install -y --no-install-recommends curl gnupg ca-certificates; \
    echo "deb http://apt.postgresql.org/pub/repos/apt $(. /etc/os-release && echo $VERSION_CODENAME)-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list; \
    curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
      | gpg --dearmor -o /etc/apt/trusted.gpg.d/pgdg.gpg; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        postgresql-16-cron \
        postgresql-16-pgtap \
        pgtap; \
    rm -rf /var/lib/apt/lists/*

# 其餘設定交由 docker-compose 的 command 以 -c 參數注入
