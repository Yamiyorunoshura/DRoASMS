\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(8);
SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_get_pending_transfer',
    ARRAY['uuid'],
    'fn_get_pending_transfer exists with expected signature'
);

-- Setup: Create a pending transfer
WITH ids AS (
    SELECT 8700000000000000000::bigint AS guild_id,
           8700000000000000001::bigint AS initiator_id,
           8700000000000000002::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 1000 FROM ids
UNION ALL
SELECT guild_id, target_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO NOTHING;

SELECT economy.fn_create_pending_transfer(
    8700000000000000000::bigint,
    8700000000000000001::bigint,
    8700000000000000002::bigint,
    500::bigint,
    '{"reason": "test"}'::jsonb,
    (timezone('utc', now()) + interval '1 hour')::timestamptz
);

-- Test 1: Returns correct transfer data
WITH transfer_id AS (
    SELECT transfer_id FROM economy.pending_transfers
    WHERE initiator_id = 8700000000000000001
    ORDER BY created_at DESC LIMIT 1
)
SELECT * INTO TEMP TABLE result
FROM economy.fn_get_pending_transfer((SELECT transfer_id FROM transfer_id));

SELECT is(
    (SELECT guild_id FROM result),
    8700000000000000000::bigint,
    'returns correct guild_id'
);

SELECT is(
    (SELECT initiator_id FROM result),
    8700000000000000001::bigint,
    'returns correct initiator_id'
);

SELECT is(
    (SELECT target_id FROM result),
    8700000000000000002::bigint,
    'returns correct target_id'
);

SELECT is(
    (SELECT amount FROM result),
    500::bigint,
    'returns correct amount'
);

SELECT is(
    (SELECT metadata->>'reason' FROM result),
    'test',
    'returns correct metadata'
);

-- Test 2: Returns empty result for non-existent transfer_id
SELECT is(
    (SELECT count(*) FROM economy.fn_get_pending_transfer('00000000-0000-0000-0000-000000000000'::uuid)),
    0::bigint,
    'returns empty result for non-existent transfer_id'
);

DROP TABLE IF EXISTS result;

-- Test 3: Status is cast to text
WITH transfer_id AS (
    SELECT transfer_id FROM economy.pending_transfers
    WHERE initiator_id = 8700000000000000001
    ORDER BY created_at DESC LIMIT 1
)
SELECT * INTO TEMP TABLE result
FROM economy.fn_get_pending_transfer((SELECT transfer_id FROM transfer_id));

SELECT ok(
    (SELECT status FROM result) IS NOT NULL,
    'status is returned as text'
);

DROP TABLE result;

SELECT finish();
ROLLBACK;
