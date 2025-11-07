\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(9);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_currency_issuances',
    ARRAY['bigint', 'text', 'int', 'int'],
    'fn_list_currency_issuances exists with expected signature'
);

-- Setup: Create currency issuances
SELECT governance.fn_create_currency_issuance(
    2150000000000000000::bigint,
    10000::bigint,
    'January issuance',
    2150000000000000001::bigint,
    '2025-01'
);

SELECT governance.fn_create_currency_issuance(
    2150000000000000000::bigint,
    5000::bigint,
    'February issuance',
    2150000000000000002::bigint,
    '2025-02'
);

SELECT governance.fn_create_currency_issuance(
    2150000000000000000::bigint,
    3000::bigint,
    'January second issuance',
    2150000000000000003::bigint,
    '2025-01'
);

-- Test 1: Returns all issuances for guild when month_period is NULL
SELECT is(
    (SELECT count(*) FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, NULL::text, 100, 0)),
    3::bigint,
    'returns all issuances for guild when month_period is NULL'
);

-- Test 2: Filters by month_period
SELECT is(
    (SELECT count(*) FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, '2025-01', 100, 0)),
    2::bigint,
    'filters by month_period correctly'
);

-- Test 3: Limit works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, NULL::text, 2, 0)),
    2::bigint,
    'limit parameter restricts result count'
);

-- Test 4: Offset works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, NULL::text, 100, 1)),
    2::bigint,
    'offset parameter skips first record'
);

-- Test 5: Ordered by issued_at DESC
WITH issuances AS (
    SELECT * FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, NULL::text, 1, 0)
)
SELECT ok(
    (
        SELECT issued_at >= (
            SELECT issued_at FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, NULL::text, 1, 1)
        )
        FROM issuances
    ),
    'ordered by issued_at DESC (newest first)'
);

-- Test 6: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_currency_issuances(8999999999999999999::bigint, NULL::text, 100, 0)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 7: Returns empty result for non-existent month_period
SELECT is(
    (SELECT count(*) FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, '2025-12', 100, 0)),
    0::bigint,
    'returns empty result for non-existent month_period'
);

-- Test 8: Returns all expected columns
WITH issuances AS (
    SELECT * FROM governance.fn_list_currency_issuances(2150000000000000000::bigint, NULL::text, 1, 0)
)
SELECT ok(
    (SELECT issuance_id IS NOT NULL FROM issuances) AND
    (SELECT guild_id IS NOT NULL FROM issuances) AND
    (SELECT amount IS NOT NULL FROM issuances) AND
    (SELECT reason IS NOT NULL FROM issuances) AND
    (SELECT performed_by IS NOT NULL FROM issuances) AND
    (SELECT month_period IS NOT NULL FROM issuances) AND
    (SELECT issued_at IS NOT NULL FROM issuances),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
