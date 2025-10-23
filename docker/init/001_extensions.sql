-- 初始化資料庫擴充：僅在資料庫首次建立時執行
-- 注意：官方 postgres 映像未預載 pg_cron，若需要請改用自訂映像並設定 shared_preload_libraries。

CREATE EXTENSION IF NOT EXISTS pgcrypto;

