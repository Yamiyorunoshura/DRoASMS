FROM postgres:16

# 安裝 pg_cron 擴充
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-cron \
    && rm -rf /var/lib/apt/lists/*

# 其餘設定交由 docker-compose 的 command 以 -c 參數注入

