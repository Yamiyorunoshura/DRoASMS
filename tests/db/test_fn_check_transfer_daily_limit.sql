\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(9);

SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_check_transfer_daily_limit',
    ARRAY['uuid'],
    'fn_check_transfer_daily_limit exists with expected signature'
);

-- Setup: Create balances and pending transfer
WITH ids AS (
    SELECT 8600000000000000000::bigint AS guild_id,
           8600000000000000001::bigint AS initiator_id,
           8600000000000000002::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 10000 FROM ids
UNION ALL
SELECT guild_id, target_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

-- Test 1: No daily limit set (GUC not set) - should pass
DELETE FROM economy.pending_transfers WHERE initiator_id = 8600000000000000001;
SELECT economy.fn_create_pending_transfer(
    8600000000000000000::bigint,
    8600000000000000001::bigint,
    8600000000000000002::bigint,
    1000::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_daily_limit(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 8600000000000000001
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'daily_limit'
        FROM economy.pending_transfers
        WHERE initiator_id = 8600000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    '1',
    'daily limit check passes when GUC is not set'
);

-- Test 2: Daily limit set and within limit
SET app.transfer_daily_limit = '5000';

DELETE FROM economy.pending_transfers WHERE initiator_id = 8600000000000000001;

SELECT economy.fn_create_pending_transfer(
    8600000000000000000::bigint,
    8600000000000000001::bigint,
    8600000000000000002::bigint,
    1000::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_daily_limit(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 8600000000000000001
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'daily_limit'
        FROM economy.pending_transfers
        WHERE initiator_id = 8600000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    '1',
    'daily limit check passes when within limit'
);

-- Limit smaller than transfer amount to force failure
SET app.transfer_daily_limit = '2000';

DELETE FROM economy.pending_transfers WHERE initiator_id = 8600000000000000001;

SELECT economy.fn_create_pending_transfer(
    8600000000000000000::bigint,
    8600000000000000001::bigint,
    8600000000000000002::bigint,
    2500::bigint,  -- exceeds temporary 2000 limit
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_daily_limit(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 8600000000000000001
     ORDER BY created_at DESC LIMIT 1)
);


SELECT is(
    (
        SELECT checks->>'daily_limit'
        FROM economy.pending_transfers
        WHERE initiator_id = 8600000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    '0',
    'daily limit check fails when limit exceeded'
);

SET app.transfer_daily_limit = '5000';

-- Reset history before testing exact-limit behaviour
DELETE FROM currency_transactions WHERE guild_id = 8600000000000000000;
DELETE FROM economy.pending_transfers WHERE initiator_id IN (8600000000000000001, 8600000000000000003);

SELECT economy.fn_transfer_currency(
    8600000000000000000::bigint,
    8600000000000000001::bigint,
    8600000000000000002::bigint,
    4000::bigint,
    jsonb_build_object('reason', 'Previous transfer 2')
);

SELECT economy.fn_create_pending_transfer(
    8600000000000000000::bigint,
    8600000000000000001::bigint,
    8600000000000000002::bigint,
    1000::bigint,  -- 4000 + 1000 = 5000 (at limit)
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_daily_limit(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 8600000000000000001
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'daily_limit'
        FROM economy.pending_transfers
        WHERE initiator_id = 8600000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    '1',
    'daily limit check passes when exactly at limit'
);

-- Test 5: Daily limit = 0 (treated as unlimited)
SET app.transfer_daily_limit = '0';

DELETE FROM economy.pending_transfers WHERE initiator_id = 8600000000000000001;

SELECT economy.fn_create_pending_transfer(
    8600000000000000000::bigint,
    8600000000000000001::bigint,
    8600000000000000002::bigint,
    1000::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_daily_limit(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 8600000000000000001
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'daily_limit'
        FROM economy.pending_transfers
        WHERE initiator_id = 8600000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    '1',
    'daily limit = 0 is treated as unlimited'
);

-- Test 6: Government account exemption
INSERT INTO governance.government_accounts (account_id, guild_id, department, balance)
VALUES (8600000000000000003, 8600000000000000000, 'finance', 10000)
ON CONFLICT (account_id) DO UPDATE SET department = EXCLUDED.department;

INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
VALUES (8600000000000000000, 8600000000000000003, 10000)
ON CONFLICT (guild_id, member_id) DO NOTHING;

SET app.transfer_daily_limit = '100';

DELETE FROM economy.pending_transfers WHERE initiator_id = 8600000000000000003;

SELECT economy.fn_create_pending_transfer(
    8600000000000000000::bigint,
    8600000000000000003::bigint,
    8600000000000000002::bigint,
    10000::bigint,  -- Way over limit
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_daily_limit(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 8600000000000000003
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'daily_limit'
        FROM economy.pending_transfers
        WHERE initiator_id = 8600000000000000003
        ORDER BY created_at DESC LIMIT 1
    ),
    '1',
    'government accounts are exempt from daily limit'
);

-- Test 7: Only counts transfers from today
DELETE FROM currency_transactions WHERE guild_id = 8600000000000000000;
DELETE FROM economy.pending_transfers WHERE initiator_id IN (8600000000000000001, 8600000000000000003);

INSERT INTO currency_transactions (
    guild_id, initiator_id, target_id, amount, direction, reason,
    balance_after_initiator, balance_after_target, created_at
)
VALUES (
    8600000000000000000,
    8600000000000000001,
    8600000000000000002,
    10000,
    'transfer',
    'Yesterday transfer',
    0,
    10000,
    date_trunc('day', timezone('utc', now())) - interval '1 day'
);

SET app.transfer_daily_limit = '5000';

SELECT economy.fn_create_pending_transfer(
    8600000000000000000::bigint,
    8600000000000000001::bigint,
    8600000000000000002::bigint,
    1000::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT economy.fn_check_transfer_daily_limit(
    (SELECT transfer_id FROM economy.pending_transfers
     WHERE initiator_id = 8600000000000000001
     ORDER BY created_at DESC LIMIT 1)
);

SELECT is(
    (
        SELECT checks->>'daily_limit'
        FROM economy.pending_transfers
        WHERE initiator_id = 8600000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    '1',
    'only counts transfers from today, not yesterday'
);

-- Clean up before finishing
DELETE FROM currency_transactions WHERE guild_id = 8600000000000000000;
DELETE FROM economy.pending_transfers WHERE initiator_id IN (8600000000000000001, 8600000000000000003);

-- Test 8: Non-existent transfer_id (should return early)
SELECT economy.fn_check_transfer_daily_limit('00000000-0000-0000-0000-000000000000'::uuid);

SELECT ok(
    TRUE,
    'function handles non-existent transfer_id gracefully'
);

SELECT finish();
ROLLBACK;
