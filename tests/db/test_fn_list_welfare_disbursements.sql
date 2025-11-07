\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_welfare_disbursements',
    ARRAY['bigint', 'int', 'int'],
    'fn_list_welfare_disbursements exists with expected signature'
);

-- Setup: Create welfare disbursements
SELECT governance.fn_create_welfare_disbursement(
    2090000000000000000::bigint,
    2090000000000000001::bigint,
    500::bigint,
    'monthly',
    'REF001'
);

SELECT governance.fn_create_welfare_disbursement(
    2090000000000000000::bigint,
    2090000000000000002::bigint,
    1000::bigint,
    'one-time',
    'REF002'
);

SELECT governance.fn_create_welfare_disbursement(
    2090000000000000000::bigint,
    2090000000000000003::bigint,
    750::bigint,
    'emergency',
    'REF003'
);

-- Test 1: Returns all disbursements for guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_welfare_disbursements(2090000000000000000::bigint, 100, 0)),
    3::bigint,
    'returns all disbursements for guild'
);

-- Test 2: Limit works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_welfare_disbursements(2090000000000000000::bigint, 2, 0)),
    2::bigint,
    'limit parameter restricts result count'
);

-- Test 3: Offset works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_welfare_disbursements(2090000000000000000::bigint, 100, 1)),
    2::bigint,
    'offset parameter skips first record'
);

-- Test 4: Ordered by disbursed_at DESC
WITH disbursements AS (
    SELECT * FROM governance.fn_list_welfare_disbursements(2090000000000000000::bigint, 1, 0)
)
SELECT ok(
    (
        SELECT disbursed_at >= (
            SELECT disbursed_at FROM governance.fn_list_welfare_disbursements(2090000000000000000::bigint, 1, 1)
        )
        FROM disbursements
    ),
    'ordered by disbursed_at DESC (newest first)'
);

-- Test 5: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_welfare_disbursements(8999999999999999999::bigint, 100, 0)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 6: Returns all expected columns
WITH disbursements AS (
    SELECT * FROM governance.fn_list_welfare_disbursements(2090000000000000000::bigint, 1, 0)
)
SELECT ok(
    (SELECT disbursement_id IS NOT NULL FROM disbursements) AND
    (SELECT guild_id IS NOT NULL FROM disbursements) AND
    (SELECT recipient_id IS NOT NULL FROM disbursements) AND
    (SELECT amount IS NOT NULL FROM disbursements) AND
    (SELECT disbursement_type IS NOT NULL FROM disbursements) AND
    (SELECT reference_id IS NOT NULL FROM disbursements) AND
    (SELECT disbursed_at IS NOT NULL FROM disbursements),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
