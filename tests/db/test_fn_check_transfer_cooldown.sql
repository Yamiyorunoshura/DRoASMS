\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_check_transfer_cooldown',
    ARRAY['uuid'],
    'fn_check_transfer_cooldown exists with expected signature'
);

-- Setup: Create balances and pending transfer
WITH ids AS (
    SELECT 8500000000000000000::bigint AS guild_id,
           8500000000000000001::bigint AS initiator_id,
           8500000000000000002::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance, throttled_until)
SELECT guild_id, initiator_id, 1000, NULL::timestamptz FROM ids
UNION ALL
SELECT guild_id, target_id, 0, NULL::timestamptz FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

-- Test 1: No cooldown (throttled_until is NULL)
DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8500000000000000000::bigint,
    8500000000000000001::bigint,
    8500000000000000002::bigint,
    100::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

SELECT economy.fn_check_transfer_cooldown((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT checks->>'cooldown'
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    '1',
    'cooldown check passes when throttled_until is NULL'
);

-- Test 2: Cooldown expired (throttled_until is in the past)
UPDATE guild_member_balances
SET throttled_until = timezone('utc', now()) - interval '1 minute'
WHERE guild_id = 8500000000000000000 AND member_id = 8500000000000000001;

DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8500000000000000000::bigint,
    8500000000000000001::bigint,
    8500000000000000002::bigint,
    100::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

SELECT economy.fn_check_transfer_cooldown((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT checks->>'cooldown'
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    '1',
    'cooldown check passes when throttled_until is expired'
);

-- Test 3: Still on cooldown (throttled_until is in the future)
UPDATE guild_member_balances
SET throttled_until = timezone('utc', now()) + interval '5 minutes'
WHERE guild_id = 8500000000000000000 AND member_id = 8500000000000000001;

DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8500000000000000000::bigint,
    8500000000000000001::bigint,
    8500000000000000002::bigint,
    100::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

SELECT economy.fn_check_transfer_cooldown((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT checks->>'cooldown'
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    '0',
    'cooldown check fails when still throttled'
);

-- Test 4: Government account exemption
INSERT INTO governance.government_accounts (account_id, guild_id, department, balance)
VALUES (8500000000000000003, 8500000000000000000, 'finance', 0)
ON CONFLICT (account_id) DO UPDATE SET department = EXCLUDED.department;

INSERT INTO guild_member_balances (guild_id, member_id, current_balance, throttled_until)
VALUES (8500000000000000000, 8500000000000000003, 1000, timezone('utc', now()) + interval '5 minutes')
ON CONFLICT (guild_id, member_id) DO UPDATE SET throttled_until = EXCLUDED.throttled_until;

DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8500000000000000000::bigint,
    8500000000000000003::bigint,
    8500000000000000002::bigint,
    100::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

SELECT economy.fn_check_transfer_cooldown((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT checks->>'cooldown'
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    '1',
    'government accounts are exempt from cooldown'
);

-- Test 5: Non-existent transfer_id (should return early)
SELECT economy.fn_check_transfer_cooldown('00000000-0000-0000-0000-000000000000'::uuid);

SELECT ok(
    TRUE,
    'function handles non-existent transfer_id gracefully'
);

DROP TABLE IF EXISTS latest_transfer;
CREATE TEMP TABLE latest_transfer AS
SELECT transfer_id
FROM economy.pending_transfers
WHERE initiator_id = 8500000000000000001
ORDER BY created_at DESC LIMIT 1;

-- 回退 updated_at，確保觸發檢查時可偵測到時間差異
UPDATE economy.pending_transfers
SET updated_at = timezone('utc', now()) - interval '10 minutes'
WHERE transfer_id = (SELECT transfer_id FROM latest_transfer);

DROP TABLE IF EXISTS latest_transfer_before;
CREATE TEMP TABLE latest_transfer_before AS
SELECT transfer_id, updated_at
FROM economy.pending_transfers
WHERE transfer_id = (SELECT transfer_id FROM latest_transfer);

SELECT economy.fn_check_transfer_cooldown((SELECT transfer_id FROM latest_transfer));

SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM latest_transfer_before)
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM latest_transfer)
    ),
    'updated_at is updated when cooldown check runs'
);

DROP TABLE latest_transfer_before;
DROP TABLE latest_transfer;

SELECT finish();
ROLLBACK;
