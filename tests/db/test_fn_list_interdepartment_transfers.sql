\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_interdepartment_transfers',
    ARRAY['bigint', 'int', 'int'],
    'fn_list_interdepartment_transfers exists with expected signature'
);

-- Setup: Create interdepartment transfers
SELECT governance.fn_create_interdepartment_transfer(
    2180000000000000000::bigint,
    'finance',
    'security',
    5000::bigint,
    'Transfer 1',
    2180000000000000001::bigint
);

SELECT governance.fn_create_interdepartment_transfer(
    2180000000000000000::bigint,
    'security',
    'finance',
    3000::bigint,
    'Transfer 2',
    2180000000000000002::bigint
);

SELECT governance.fn_create_interdepartment_transfer(
    2180000000000000000::bigint,
    'finance',
    'security',
    1000::bigint,
    'Transfer 3',
    2180000000000000003::bigint
);

-- Test 1: Returns all transfers for guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_interdepartment_transfers(2180000000000000000::bigint, 100, 0)),
    3::bigint,
    'returns all transfers for guild'
);

-- Test 2: Limit works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_interdepartment_transfers(2180000000000000000::bigint, 2, 0)),
    2::bigint,
    'limit parameter restricts result count'
);

-- Test 3: Offset works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_interdepartment_transfers(2180000000000000000::bigint, 100, 1)),
    2::bigint,
    'offset parameter skips first record'
);

-- Test 4: Ordered by transferred_at DESC
WITH transfers AS (
    SELECT * FROM governance.fn_list_interdepartment_transfers(2180000000000000000::bigint, 1, 0)
)
SELECT ok(
    (
        SELECT transferred_at >= (
            SELECT transferred_at FROM governance.fn_list_interdepartment_transfers(2180000000000000000::bigint, 1, 1)
        )
        FROM transfers
    ),
    'ordered by transferred_at DESC (newest first)'
);

-- Test 5: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_interdepartment_transfers(8999999999999999999::bigint, 100, 0)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 6: Returns all expected columns
WITH transfers AS (
    SELECT * FROM governance.fn_list_interdepartment_transfers(2180000000000000000::bigint, 1, 0)
)
SELECT ok(
    (SELECT transfer_id IS NOT NULL FROM transfers) AND
    (SELECT guild_id IS NOT NULL FROM transfers) AND
    (SELECT from_department IS NOT NULL FROM transfers) AND
    (SELECT to_department IS NOT NULL FROM transfers) AND
    (SELECT amount IS NOT NULL FROM transfers) AND
    (SELECT reason IS NOT NULL FROM transfers) AND
    (SELECT performed_by IS NOT NULL FROM transfers) AND
    (SELECT transferred_at IS NOT NULL FROM transfers),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
