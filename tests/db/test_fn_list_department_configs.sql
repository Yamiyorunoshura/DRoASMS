\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_department_configs',
    ARRAY['bigint'],
    'fn_list_department_configs exists with expected signature'
);

-- Setup: Create department configs
SELECT governance.fn_upsert_department_config(
    2030000000000000000::bigint,
    'finance',
    2030000000000000001::bigint,
    1000::bigint,
    24,
    5000::bigint,
    10,
    10000::bigint
);

SELECT governance.fn_upsert_department_config(
    2030000000000000000::bigint,
    'security',
    2030000000000000002::bigint,
    500::bigint,
    12,
    3000::bigint,
    5,
    5000::bigint
);

-- Test 1: Returns all department configs for guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_department_configs(2030000000000000000::bigint)),
    2::bigint,
    'returns all department configs for guild'
);

-- Test 2: Ordered by department
WITH configs AS (
    SELECT * FROM governance.fn_list_department_configs(2030000000000000000::bigint)
)
SELECT ok(
    (
        SELECT array_agg(department ORDER BY department) = ARRAY['finance', 'security']
        FROM configs
    ),
    'ordered by department'
);

-- Test 3: Returns correct data
WITH configs AS (
    SELECT * FROM governance.fn_list_department_configs(2030000000000000000::bigint)
    WHERE department = 'finance'
)
SELECT is(
    (SELECT welfare_amount FROM configs),
    1000::bigint,
    'returns correct data'
);

-- Test 4: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_department_configs(8999999999999999999::bigint)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 5: Returns all expected columns
WITH configs AS (
    SELECT * FROM governance.fn_list_department_configs(2030000000000000000::bigint)
    LIMIT 1
)
SELECT ok(
    (SELECT id IS NOT NULL FROM configs) AND
    (SELECT guild_id IS NOT NULL FROM configs) AND
    (SELECT department IS NOT NULL FROM configs) AND
    (SELECT role_id IS NOT NULL FROM configs) AND
    (SELECT welfare_amount IS NOT NULL FROM configs) AND
    (SELECT welfare_interval_hours IS NOT NULL FROM configs) AND
    (SELECT tax_rate_basis IS NOT NULL FROM configs) AND
    (SELECT tax_rate_percent IS NOT NULL FROM configs) AND
    (SELECT max_issuance_per_month IS NOT NULL FROM configs) AND
    (SELECT created_at IS NOT NULL FROM configs) AND
    (SELECT updated_at IS NOT NULL FROM configs),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
