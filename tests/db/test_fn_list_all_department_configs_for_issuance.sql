\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_all_department_configs_for_issuance',
    ARRAY[]::text[],
    'fn_list_all_department_configs_for_issuance exists with expected signature'
);

-- Setup: Create department configs
SELECT governance.fn_upsert_department_config(
    2200000000000000000::bigint,
    'finance',
    2200000000000000001::bigint,
    1000::bigint,
    24,
    5000::bigint,
    10,
    10000::bigint  -- max_issuance_per_month > 0
);

SELECT governance.fn_upsert_department_config(
    2200000000000000000::bigint,
    'security',
    2200000000000000002::bigint,
    500::bigint,
    12,
    3000::bigint,
    5,
    0::bigint  -- max_issuance_per_month = 0
);

SELECT governance.fn_upsert_department_config(
    2200000000000000001::bigint,
    'central_bank',
    2200000000000000003::bigint,
    750::bigint,
    48,
    2000::bigint,
    8,
    5000::bigint  -- max_issuance_per_month > 0
);

-- Test 1: Returns only departments with max_issuance_per_month > 0
SELECT is(
    (SELECT count(*) FROM governance.fn_list_all_department_configs_for_issuance()),
    2::bigint,
    'returns only departments with max_issuance_per_month > 0'
);

-- Test 2: Returns correct departments
WITH configs AS (
    SELECT * FROM governance.fn_list_all_department_configs_for_issuance()
)
SELECT ok(
    EXISTS (SELECT 1 FROM configs WHERE department = 'finance') AND
    EXISTS (SELECT 1 FROM configs WHERE department = 'central_bank') AND
    NOT EXISTS (SELECT 1 FROM configs WHERE department = 'security'),
    'returns correct departments'
);

-- Test 3: Returns correct issuance data
WITH configs AS (
    SELECT * FROM governance.fn_list_all_department_configs_for_issuance()
    WHERE department = 'finance'
)
SELECT ok(
    (SELECT max_issuance_per_month = 10000::bigint FROM configs),
    'returns correct issuance data'
);

-- Test 4: Returns all expected columns
WITH configs AS (
    SELECT * FROM governance.fn_list_all_department_configs_for_issuance()
    LIMIT 1
)
SELECT ok(
    (SELECT guild_id IS NOT NULL FROM configs) AND
    (SELECT department IS NOT NULL FROM configs) AND
    (SELECT max_issuance_per_month IS NOT NULL FROM configs),
    'returns all expected columns'
);

-- Test 5: Returns empty result when no departments have issuance limit
DELETE FROM governance.department_configs WHERE max_issuance_per_month > 0;

SELECT is(
    (SELECT count(*) FROM governance.fn_list_all_department_configs_for_issuance()),
    0::bigint,
    'returns empty result when no departments have issuance limit'
);

SELECT finish();
ROLLBACK;
