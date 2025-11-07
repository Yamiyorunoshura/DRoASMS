\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_sum_monthly_issuance',
    ARRAY['bigint', 'text'],
    'fn_sum_monthly_issuance exists with expected signature'
);

-- Setup: Create currency issuances
SELECT governance.fn_create_currency_issuance(
    2160000000000000000::bigint,
    10000::bigint,
    'January issuance 1',
    2160000000000000001::bigint,
    '2025-01'
);

SELECT governance.fn_create_currency_issuance(
    2160000000000000000::bigint,
    5000::bigint,
    'January issuance 2',
    2160000000000000002::bigint,
    '2025-01'
);

SELECT governance.fn_create_currency_issuance(
    2160000000000000000::bigint,
    3000::bigint,
    'February issuance',
    2160000000000000003::bigint,
    '2025-02'
);

-- Test 1: Sums issuances for specific month
SELECT is(
    governance.fn_sum_monthly_issuance(2160000000000000000::bigint, '2025-01'),
    15000::bigint,
    'sums issuances for specific month'
);

-- Test 2: Returns 0 for non-existent month
SELECT is(
    governance.fn_sum_monthly_issuance(2160000000000000000::bigint, '2025-12'),
    0::bigint,
    'returns 0 for non-existent month'
);

-- Test 3: Returns 0 for non-existent guild
SELECT is(
    governance.fn_sum_monthly_issuance(8999999999999999999::bigint, '2025-01'),
    0::bigint,
    'returns 0 for non-existent guild'
);

-- Test 4: Only counts issuances for specified month
SELECT is(
    governance.fn_sum_monthly_issuance(2160000000000000000::bigint, '2025-02'),
    3000::bigint,
    'only counts issuances for specified month'
);

-- Test 5: Handles zero amount issuances
SELECT governance.fn_create_currency_issuance(
    2160000000000000000::bigint,
    0::bigint,
    'Zero issuance',
    2160000000000000004::bigint,
    '2025-01'
);

SELECT is(
    governance.fn_sum_monthly_issuance(2160000000000000000::bigint, '2025-01'),
    15000::bigint,
    'handles zero amount issuances correctly'
);

SELECT finish();
ROLLBACK;
