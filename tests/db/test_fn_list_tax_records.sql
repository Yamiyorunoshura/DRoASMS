\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_tax_records',
    ARRAY['bigint', 'int', 'int'],
    'fn_list_tax_records exists with expected signature'
);

-- Setup: Create tax records
SELECT governance.fn_create_tax_record(
    2110000000000000000::bigint,
    2110000000000000001::bigint,
    10000::bigint,
    10,
    1000::bigint,
    'income',
    '2025-01'
);

SELECT governance.fn_create_tax_record(
    2110000000000000000::bigint,
    2110000000000000002::bigint,
    5000::bigint,
    15,
    750::bigint,
    'property',
    '2025-02'
);

SELECT governance.fn_create_tax_record(
    2110000000000000000::bigint,
    2110000000000000003::bigint,
    3000::bigint,
    5,
    150::bigint,
    'sales',
    '2025-03'
);

-- Test 1: Returns all tax records for guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_tax_records(2110000000000000000::bigint, 100, 0)),
    3::bigint,
    'returns all tax records for guild'
);

-- Test 2: Limit works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_tax_records(2110000000000000000::bigint, 2, 0)),
    2::bigint,
    'limit parameter restricts result count'
);

-- Test 3: Offset works correctly
SELECT is(
    (SELECT count(*) FROM governance.fn_list_tax_records(2110000000000000000::bigint, 100, 1)),
    2::bigint,
    'offset parameter skips first record'
);

-- Test 4: Ordered by collected_at DESC
WITH records AS (
    SELECT * FROM governance.fn_list_tax_records(2110000000000000000::bigint, 1, 0)
)
SELECT ok(
    (
        SELECT collected_at >= (
            SELECT collected_at FROM governance.fn_list_tax_records(2110000000000000000::bigint, 1, 1)
        )
        FROM records
    ),
    'ordered by collected_at DESC (newest first)'
);

-- Test 5: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_tax_records(8999999999999999999::bigint, 100, 0)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 6: Returns all expected columns
WITH records AS (
    SELECT * FROM governance.fn_list_tax_records(2110000000000000000::bigint, 1, 0)
)
SELECT ok(
    (SELECT tax_id IS NOT NULL FROM records) AND
    (SELECT guild_id IS NOT NULL FROM records) AND
    (SELECT taxpayer_id IS NOT NULL FROM records) AND
    (SELECT taxable_amount IS NOT NULL FROM records) AND
    (SELECT tax_rate_percent IS NOT NULL FROM records) AND
    (SELECT tax_amount IS NOT NULL FROM records) AND
    (SELECT tax_type IS NOT NULL FROM records) AND
    (SELECT assessment_period IS NOT NULL FROM records) AND
    (SELECT collected_at IS NOT NULL FROM records),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
