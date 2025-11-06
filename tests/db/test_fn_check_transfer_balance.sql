\set ON_ERROR_STOP 1

BEGIN;

-- 使用 pgTAP 規劃並設定 search_path
SELECT plan(4);
SELECT set_config('search_path', 'pgtap, economy, public', false);

-- 基本存在性檢查
SELECT has_schema('economy', 'economy schema exists');
SELECT has_function(
    'economy',
    'fn_check_transfer_balance',
    ARRAY['uuid'],
    'fn_check_transfer_balance exists with expected signature'
);

-- Test 1: 餘額足夠時寫入 checks.balance = 1
INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
VALUES (7100000000000000000, 7100000000000000001, 500)
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

SELECT economy.fn_create_pending_transfer(
    7100000000000000000::bigint,
    7100000000000000001::bigint,
    7100000000000000002::bigint,
    200::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_balance(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 7100000000000000001
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'balance'
        FROM economy.pending_transfers
        WHERE initiator_id = 7100000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    '1',
    'balance check result is 1 when sufficient'
);

-- Test 2: 餘額不足時寫入 checks.balance = 0
INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
VALUES (7100000000000000000, 7100000000000000010, 50)
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

SELECT economy.fn_create_pending_transfer(
    7100000000000000000::bigint,
    7100000000000000010::bigint,
    7100000000000000011::bigint,
    200::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_balance(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 7100000000000000010
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'balance'
        FROM economy.pending_transfers
        WHERE initiator_id = 7100000000000000010
        ORDER BY created_at DESC LIMIT 1
    ),
    '0',
    'balance check result is 0 when insufficient'
);

SELECT finish();
ROLLBACK;
