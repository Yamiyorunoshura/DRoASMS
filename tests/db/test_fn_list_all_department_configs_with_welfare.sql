\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_all_department_configs_with_welfare',
    ARRAY[]::text[],
    'fn_list_all_department_configs_with_welfare exists with expected signature'
);

-- Setup: Create department configs
SELECT governance.fn_upsert_department_config(
    2190000000000000000::bigint,
    'finance',
    2190000000000000001::bigint,
    1000::bigint,  -- welfare_amount > 0
    24,            -- welfare_interval_hours > 0
    5000::bigint,
    10,
    10000::bigint
);

SELECT governance.fn_upsert_department_config(
    2190000000000000000::bigint,
    'security',
    2190000000000000002::bigint,
    0::bigint,     -- welfare_amount = 0
    24,            -- keep interval positive to satisfy constraint
    3000::bigint,
    5,
    5000::bigint
);

SELECT governance.fn_upsert_department_config(
    2190000000000000001::bigint,
    'internal_affairs',
    2190000000000000003::bigint,
    500::bigint,   -- welfare_amount > 0
    12,            -- welfare_interval_hours > 0
    2000::bigint,
    8,
    8000::bigint
);

-- Test 1: Returns only departments with welfare
SELECT is(
    (SELECT count(*) FROM governance.fn_list_all_department_configs_with_welfare()),
    2::bigint,
    'returns only departments with welfare'
);

-- Test 2: Returns correct departments
WITH configs AS (
    SELECT * FROM governance.fn_list_all_department_configs_with_welfare()
)
SELECT ok(
    EXISTS (SELECT 1 FROM configs WHERE department = 'finance') AND
    EXISTS (SELECT 1 FROM configs WHERE department = 'internal_affairs') AND
    NOT EXISTS (SELECT 1 FROM configs WHERE department = 'security'),
    'returns correct departments'
);

-- Test 3: Returns correct welfare data
WITH configs AS (
    SELECT * FROM governance.fn_list_all_department_configs_with_welfare()
    WHERE department = 'finance'
)
SELECT ok(
    (SELECT welfare_amount = 1000::bigint FROM configs) AND
    (SELECT welfare_interval_hours = 24 FROM configs),
    'returns correct welfare data'
);

-- Test 4: Returns all expected columns
WITH configs AS (
    SELECT * FROM governance.fn_list_all_department_configs_with_welfare()
    LIMIT 1
)
SELECT ok(
    (SELECT guild_id IS NOT NULL FROM configs) AND
    (SELECT department IS NOT NULL FROM configs) AND
    (SELECT welfare_amount IS NOT NULL FROM configs) AND
    (SELECT welfare_interval_hours IS NOT NULL FROM configs),
    'returns all expected columns'
);

-- Test 5: Returns empty result when no departments have welfare
DELETE FROM governance.department_configs WHERE welfare_amount > 0 AND welfare_interval_hours > 0;

SELECT is(
    (SELECT count(*) FROM governance.fn_list_all_department_configs_with_welfare()),
    0::bigint,
    'returns empty result when no departments have welfare'
);

SELECT finish();
ROLLBACK;
