\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(8);

SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    '_check_and_approve_transfer',
    ARRAY['uuid'],
    '_check_and_approve_transfer exists with expected signature'
);

-- Setup: Create balances
WITH ids AS (
    SELECT 8910000000000000000::bigint AS guild_id,
           8910000000000000001::bigint AS initiator_id,
           8910000000000000002::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 1000 FROM ids
UNION ALL
SELECT guild_id, target_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

-- Test 1: All checks pass - transfer is approved
DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8910000000000000000::bigint,
    8910000000000000001::bigint,
    8910000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

UPDATE economy.pending_transfers
SET status = 'checking',
    checks = '{"balance": 1, "cooldown": 1, "daily_limit": 1}'::jsonb
WHERE transfer_id = (SELECT transfer_id FROM last_transfer);

SELECT economy._check_and_approve_transfer((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    'approved',
    'approves transfer when all checks pass'
);

-- Test 2: Missing balance check - not approved
DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8910000000000000000::bigint,
    8910000000000000001::bigint,
    8910000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

UPDATE economy.pending_transfers
SET status = 'checking',
    checks = '{"cooldown": 1, "daily_limit": 1}'::jsonb
WHERE transfer_id = (SELECT transfer_id FROM last_transfer);

SELECT economy._check_and_approve_transfer((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    'checking',
    'does not approve when balance check is missing'
);

-- Test 3: Balance check fails - not approved
DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8910000000000000000::bigint,
    8910000000000000001::bigint,
    8910000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

UPDATE economy.pending_transfers
SET status = 'checking',
    checks = '{"balance": 0, "cooldown": 1, "daily_limit": 1}'::jsonb
WHERE transfer_id = (SELECT transfer_id FROM last_transfer);

SELECT economy._check_and_approve_transfer((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    'checking',
    'does not approve when balance check fails'
);

-- Test 4: Cooldown check fails - not approved
DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8910000000000000000::bigint,
    8910000000000000001::bigint,
    8910000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

UPDATE economy.pending_transfers
SET status = 'checking',
    checks = '{"balance": 1, "cooldown": 0, "daily_limit": 1}'::jsonb
WHERE transfer_id = (SELECT transfer_id FROM last_transfer);

SELECT economy._check_and_approve_transfer((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    'checking',
    'does not approve when cooldown check fails'
);

-- Test 5: Daily limit check fails - not approved
DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8910000000000000000::bigint,
    8910000000000000001::bigint,
    8910000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

UPDATE economy.pending_transfers
SET status = 'checking',
    checks = '{"balance": 1, "cooldown": 1, "daily_limit": 0}'::jsonb
WHERE transfer_id = (SELECT transfer_id FROM last_transfer);

SELECT economy._check_and_approve_transfer((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    'checking',
    'does not approve when daily limit check fails'
);

-- Test 6: Status is not checking - not approved
DROP TABLE IF EXISTS last_transfer;
CREATE TEMP TABLE last_transfer AS
SELECT economy.fn_create_pending_transfer(
    8910000000000000000::bigint,
    8910000000000000001::bigint,
    8910000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

UPDATE economy.pending_transfers
SET status = 'pending',
    checks = '{"balance": 1, "cooldown": 1, "daily_limit": 1}'::jsonb
WHERE transfer_id = (SELECT transfer_id FROM last_transfer);

SELECT economy._check_and_approve_transfer((SELECT transfer_id FROM last_transfer));

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM last_transfer)
    ),
    'pending',
    'does not approve when status is not checking'
);

-- Test 7: Non-existent transfer_id (should return early)
SELECT economy._check_and_approve_transfer('00000000-0000-0000-0000-000000000000'::uuid);

SELECT ok(
    TRUE,
    'function handles non-existent transfer_id gracefully'
);

SELECT finish();
ROLLBACK;
