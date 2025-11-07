\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'trigger_pending_transfer_check',
    ARRAY[]::text[],
    'trigger_pending_transfer_check exists (trigger function)'
);

-- Test: Trigger exists
SELECT ok(
    EXISTS (
        SELECT 1
        FROM pg_trigger t
        JOIN pg_class c ON t.tgrelid = c.oid
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'economy'
          AND c.relname = 'pending_transfers'
          AND t.tgname = 'trigger_pending_transfer_check'
    ),
    'trigger_pending_transfer_check trigger exists on pending_transfers table'
);

-- Setup: Create balances
WITH ids AS (
    SELECT 8920000000000000000::bigint AS guild_id,
           8920000000000000001::bigint AS initiator_id,
           8920000000000000002::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 100 FROM ids
UNION ALL
SELECT guild_id, target_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

-- Test 1: Trigger fires on INSERT and updates status to checking
SELECT economy.fn_create_pending_transfer(
    8920000000000000000::bigint,
    8920000000000000001::bigint,
    8920000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT ok(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE initiator_id = 8920000000000000001
        ORDER BY created_at DESC LIMIT 1
    ) = 'checking',
    'trigger updates status to checking on INSERT'
);

-- Test 2: Trigger calls balance check function
SELECT ok(
    (
        SELECT checks->>'balance' IS NOT NULL
        FROM economy.pending_transfers
        WHERE initiator_id = 8920000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    'trigger calls fn_check_transfer_balance'
);

-- Test 3: Trigger calls cooldown check function
SELECT ok(
    (
        SELECT checks->>'cooldown' IS NOT NULL
        FROM economy.pending_transfers
        WHERE initiator_id = 8920000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    'trigger calls fn_check_transfer_cooldown'
);

-- Test 4: Trigger calls daily limit check function
SELECT ok(
    (
        SELECT checks->>'daily_limit' IS NOT NULL
        FROM economy.pending_transfers
        WHERE initiator_id = 8920000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    'trigger calls fn_check_transfer_daily_limit'
);

-- Test 5: Updated_at is updated
SELECT ok(
    (
        SELECT updated_at >= created_at
        FROM economy.pending_transfers
        WHERE initiator_id = 8920000000000000001
        ORDER BY created_at DESC LIMIT 1
    ),
    'updated_at is refreshed when trigger fires'
);

SELECT finish();
ROLLBACK;
