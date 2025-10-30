CREATE EXTENSION IF NOT EXISTS pgcrypto;
-- 需要 shared_preload_libraries 已包含 pg_cron 才能建立成功
CREATE EXTENSION IF NOT EXISTS pg_cron;
