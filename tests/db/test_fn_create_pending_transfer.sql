\set ON_ERROR_STOP 1

BEGIN;

-- 使用 pgTAP 規劃並設定 search_path
SELECT plan(6);
SELECT set_config('search_path', 'pgtap, economy, public', false);

-- 基本存在性檢查
SELECT has_schema('economy', 'economy schema exists');
SELECT has_function(
    'economy',
    'fn_create_pending_transfer',
    ARRAY['bigint','bigint','bigint','bigint','jsonb','timestamptz'],
    'fn_create_pending_transfer exists with expected signature'
);

-- Test 1: 建立有效的 pending transfer 並驗證欄位
SELECT economy.fn_create_pending_transfer(
    7000000000000000000::bigint,  -- guild_id
    7000000000000000001::bigint,  -- initiator_id
    7000000000000000002::bigint,  -- target_id
    100::bigint,                  -- amount
    '{"reason": "test"}'::jsonb, -- metadata
    NULL::timestamptz             -- expires_at
);

SELECT ok(
    EXISTS (
        SELECT 1
        FROM economy.pending_transfers
        WHERE guild_id = 7000000000000000000
          AND initiator_id = 7000000000000000001
          AND target_id = 7000000000000000002
          AND amount = 100
          AND retry_count = 0
          AND (metadata->>'reason') = 'test'
    ),
    'valid pending transfer is inserted with expected fields'
);

-- Test 2: 指定 expires_at 會被寫入
SELECT economy.fn_create_pending_transfer(
    7000000000000000000::bigint,
    7000000000000000010::bigint,
    7000000000000000011::bigint,
    50::bigint,
    '{}'::jsonb,
    (timezone('utc', now()) + interval '1 hour')::timestamptz
);

SELECT ok(
    EXISTS (
        SELECT 1 FROM economy.pending_transfers
        WHERE initiator_id = 7000000000000000010
          AND expires_at IS NOT NULL
    ),
    'expires_at is stored when provided'
);

-- Test 3: 無效案例 - initiator 與 target 相同
SELECT throws_like(
    $$ SELECT economy.fn_create_pending_transfer(
        7000000000000000000,
        7000000000000000020,
        7000000000000000020,  -- same as initiator
        100,
        '{}'::jsonb,
        NULL::timestamptz
    ) $$,
    '%distinct%',
    'reject same initiator and target'
);

-- Test 4: 無效案例 - 金額為 0
SELECT throws_like(
    $$ SELECT economy.fn_create_pending_transfer(
        7000000000000000000,
        7000000000000000030,
        7000000000000000031,
        0,
        '{}'::jsonb,
        NULL::timestamptz
    ) $$,
    '%positive whole number%',
    'reject zero amount'
);

SELECT finish();
ROLLBACK;
