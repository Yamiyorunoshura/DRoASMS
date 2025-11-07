\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_identity_records',
    ARRAY['bigint', 'int', 'int'],
    'fn_list_identity_records exists with expected signature'
);

-- Setup: Create identity records
SELECT governance.fn_create_identity_record(
    2130000000000000000::bigint,
    2130000000000000001::bigint,
    'register',
    'New member',
    2130000000000000002::bigint
);

SELECT governance.fn_create_identity_record(
    2130000000000000000::bigint,
    2130000000000000003::bigint,
    'verify',
    'Verification',
    2130000000000000004::bigint
);

SELECT governance.fn_create_identity_record(
    2130000000000000000::bigint,
    2130000000000000005::bigint,
    'update',
    'Profile update',
    2130000000000000006::bigint
);

-- Test 1: Returns all records for guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_identity_records(2130000000000000000::bigint, 100, 0)),
    3::bigint,
    'returns all records for guild'
);

-- Test 2: Limit works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_identity_records(2130000000000000000::bigint, 2, 0)),
    2::bigint,
    'limit parameter restricts result count'
);

-- Test 3: Offset works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_identity_records(2130000000000000000::bigint, 100, 1)),
    2::bigint,
    'offset parameter skips first record'
);

-- Test 4: Ordered by performed_at DESC
WITH records AS (
    SELECT * FROM governance.fn_list_identity_records(2130000000000000000::bigint, 1, 0)
)
SELECT ok(
    (
        SELECT performed_at >= (
            SELECT performed_at FROM governance.fn_list_identity_records(2130000000000000000::bigint, 1, 1)
        )
        FROM records
    ),
    'ordered by performed_at DESC (newest first)'
);

-- Test 5: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_identity_records(8999999999999999999::bigint, 100, 0)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 6: Returns all expected columns
WITH records AS (
    SELECT * FROM governance.fn_list_identity_records(2130000000000000000::bigint, 1, 0)
)
SELECT ok(
    (SELECT record_id IS NOT NULL FROM records) AND
    (SELECT guild_id IS NOT NULL FROM records) AND
    (SELECT target_id IS NOT NULL FROM records) AND
    (SELECT action IS NOT NULL FROM records) AND
    (SELECT reason IS NOT NULL FROM records) AND
    (SELECT performed_by IS NOT NULL FROM records) AND
    (SELECT performed_at IS NOT NULL FROM records),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
