\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(11);
SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_list_pending_transfers',
    ARRAY['bigint', 'text', 'integer', 'integer'],
    'fn_list_pending_transfers exists with expected signature'
);

-- Setup: Create multiple pending transfers with different statuses
DELETE FROM economy.pending_transfers WHERE guild_id = 8800000000000000000;
WITH ids AS (
    SELECT 8800000000000000000::bigint AS guild_id,
           8800000000000000001::bigint AS initiator_id,
           8800000000000000002::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 10000 FROM ids
UNION ALL
SELECT guild_id, target_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO NOTHING;

-- Create transfers with different statuses
SELECT economy.fn_create_pending_transfer(
    8800000000000000000::bigint,
    8800000000000000001::bigint,
    8800000000000000002::bigint,
    100::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

WITH latest AS (
    SELECT transfer_id
    FROM economy.pending_transfers
    WHERE guild_id = 8800000000000000000 AND initiator_id = 8800000000000000001
    ORDER BY created_at DESC LIMIT 1
)
UPDATE economy.pending_transfers
SET status = 'pending'
WHERE transfer_id = (SELECT transfer_id FROM latest);

SELECT economy.fn_create_pending_transfer(
    8800000000000000000::bigint,
    8800000000000000001::bigint,
    8800000000000000002::bigint,
    200::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

WITH latest AS (
    SELECT transfer_id
    FROM economy.pending_transfers
    WHERE guild_id = 8800000000000000000 AND initiator_id = 8800000000000000001
    ORDER BY created_at DESC LIMIT 1
)
UPDATE economy.pending_transfers
SET status = 'checking'
WHERE transfer_id = (SELECT transfer_id FROM latest);

SELECT economy.fn_create_pending_transfer(
    8800000000000000000::bigint,
    8800000000000000001::bigint,
    8800000000000000002::bigint,
    300::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

WITH latest AS (
    SELECT transfer_id
    FROM economy.pending_transfers
    WHERE guild_id = 8800000000000000000 AND initiator_id = 8800000000000000001
    ORDER BY created_at DESC LIMIT 1
)
UPDATE economy.pending_transfers
SET status = 'approved'
WHERE transfer_id = (SELECT transfer_id FROM latest);

-- Normalize statuses to avoid automatic approvals from trigger logic
UPDATE economy.pending_transfers
SET status = CASE amount
    WHEN 100 THEN 'pending'
    WHEN 200 THEN 'checking'
    WHEN 300 THEN 'approved'
    ELSE status
END
WHERE guild_id = 8800000000000000000
  AND initiator_id = 8800000000000000001;

WITH base AS (
    SELECT timezone('utc', clock_timestamp()) AS now_ts
)
UPDATE economy.pending_transfers
SET created_at = CASE amount
        WHEN 300 THEN (SELECT now_ts FROM base)
        WHEN 200 THEN (SELECT now_ts FROM base) - interval '1 minute'
        WHEN 100 THEN (SELECT now_ts FROM base) - interval '2 minutes'
        ELSE created_at
    END,
    updated_at = CASE amount
        WHEN 300 THEN (SELECT now_ts FROM base)
        WHEN 200 THEN (SELECT now_ts FROM base) - interval '1 minute'
        WHEN 100 THEN (SELECT now_ts FROM base) - interval '2 minutes'
        ELSE updated_at
    END
WHERE guild_id = 8800000000000000000
  AND initiator_id = 8800000000000000001;

-- Test 1: Returns all transfers for guild (no status filter)
SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, NULL, 100, 0)),
    3::bigint,
    'returns all transfers for guild when status is NULL'
);

-- Test 2: Filters by status
SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, 'pending', 100, 0)),
    1::bigint,
    'filters by status correctly'
);

SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, 'checking', 100, 0)),
    1::bigint,
    'filters by checking status correctly'
);

SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, 'approved', 100, 0)),
    1::bigint,
    'filters by approved status correctly'
);

-- Test 3: Limit works correctly
SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, NULL, 2, 0)),
    2::bigint,
    'limit parameter restricts result count'
);

-- Test 4: Offset works correctly
SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, NULL, 100, 1)),
    2::bigint,
    'offset parameter skips first record'
);

-- Test 5: Ordering - newest first
SELECT is(
    (
        SELECT amount
        FROM economy.fn_list_pending_transfers(8800000000000000000, NULL, 1, 0)
    ),
    300::bigint,
    'results ordered by created_at DESC (newest first)'
);

-- Test 6: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8999999999999999999, NULL, 100, 0)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 7: Returns empty result for non-existent status
SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, 'completed', 100, 0)),
    0::bigint,
    'returns empty result for non-existent status'
);

-- Test 8: Default limit (100)
SELECT is(
    (SELECT count(*) FROM economy.fn_list_pending_transfers(8800000000000000000, NULL, NULL, NULL)),
    3::bigint,
    'default limit (100) returns all records'
);

SELECT finish();
ROLLBACK;
