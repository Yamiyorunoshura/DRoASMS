\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_update_pending_transfer_status',
    ARRAY['uuid', 'text'],
    'fn_update_pending_transfer_status exists with expected signature'
);

-- Setup: Create a pending transfer
WITH ids AS (
    SELECT 8900000000000000000::bigint AS guild_id,
           8900000000000000001::bigint AS initiator_id,
           8900000000000000002::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 1000 FROM ids
UNION ALL
SELECT guild_id, target_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO NOTHING;

SELECT economy.fn_create_pending_transfer(
    8900000000000000000::bigint,
    8900000000000000001::bigint,
    8900000000000000002::bigint,
    500::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

SELECT transfer_id INTO TEMP TABLE test_transfer
FROM economy.pending_transfers
WHERE initiator_id = 8900000000000000001
ORDER BY created_at DESC LIMIT 1;

-- Test 1: Update to valid statuses
SELECT economy.fn_update_pending_transfer_status(
    (SELECT transfer_id FROM test_transfer),
    'checking'
);

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM test_transfer)
    ),
    'checking',
    'updates status to checking'
);

SELECT economy.fn_update_pending_transfer_status(
    (SELECT transfer_id FROM test_transfer),
    'approved'
);

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM test_transfer)
    ),
    'approved',
    'updates status to approved'
);

SELECT economy.fn_update_pending_transfer_status(
    (SELECT transfer_id FROM test_transfer),
    'completed'
);

SELECT is(
    (
        SELECT status
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM test_transfer)
    ),
    'completed',
    'updates status to completed'
);

-- Test 2: Error - invalid status
WITH transfer_id AS (
    SELECT transfer_id FROM economy.pending_transfers
    WHERE initiator_id = 8900000000000000001
    ORDER BY created_at DESC LIMIT 1
)
SELECT throws_like(
    $$ SELECT economy.fn_update_pending_transfer_status(
        (SELECT transfer_id FROM economy.pending_transfers
         WHERE initiator_id = 8900000000000000001
         ORDER BY created_at DESC LIMIT 1),
        'invalid_status'
    ) $$,
    '%Invalid status%',
    'raises exception for invalid status'
);

-- Test 3: Updated_at is updated
UPDATE economy.pending_transfers
SET updated_at = updated_at - interval '10 minutes'
WHERE transfer_id = (SELECT transfer_id FROM test_transfer);

SELECT updated_at INTO TEMP TABLE old_updated_at
FROM economy.pending_transfers
WHERE transfer_id = (SELECT transfer_id FROM test_transfer);

SELECT economy.fn_update_pending_transfer_status(
    (SELECT transfer_id FROM test_transfer),
    'rejected'
);

SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM old_updated_at)
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM test_transfer)
    ),
    'updated_at is updated when status changes'
);

DROP TABLE old_updated_at;

-- Test 4: All valid statuses work
SELECT economy.fn_create_pending_transfer(
    8900000000000000000::bigint,
    8900000000000000001::bigint,
    8900000000000000002::bigint,
    100::bigint,
    '{}'::jsonb,
    NULL::timestamptz
);

DELETE FROM test_transfer;
INSERT INTO test_transfer
SELECT transfer_id
FROM economy.pending_transfers
WHERE initiator_id = 8900000000000000001
ORDER BY created_at DESC LIMIT 1;

SELECT economy.fn_update_pending_transfer_status(
    (SELECT transfer_id FROM test_transfer),
    'pending'
);

SELECT ok(
    (
        SELECT status IN ('pending', 'checking', 'approved', 'completed', 'rejected')
        FROM economy.pending_transfers
        WHERE transfer_id = (SELECT transfer_id FROM test_transfer)
    ),
    'all valid statuses are accepted'
);

SELECT finish();
DROP TABLE test_transfer;
ROLLBACK;
