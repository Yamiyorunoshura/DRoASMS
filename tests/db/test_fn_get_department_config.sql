\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_get_department_config',
    ARRAY['bigint', 'text'],
    'fn_get_department_config exists with expected signature'
);

-- Setup: Create department config
SELECT governance.fn_upsert_department_config(
    2040000000000000000::bigint,
    'finance',
    2040000000000000001::bigint,
    1000::bigint,
    24,
    5000::bigint,
    10,
    10000::bigint
);

-- Test 1: Returns existing config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_get_department_config(2040000000000000000::bigint, 'finance')

;

SELECT is(
    (SELECT department FROM result),
    'finance',
    'returns existing department config'
);

SELECT is(
    (SELECT welfare_amount FROM result),
    1000::bigint,
    'returns correct welfare_amount'
);

-- Test 2: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_get_department_config(8999999999999999999::bigint, 'finance')),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 3: Returns empty result for non-existent department
SELECT is(
    (SELECT count(*) FROM governance.fn_get_department_config(2040000000000000000::bigint, 'nonexistent')),
    0::bigint,
    'returns empty result for non-existent department'
);

-- Test 4: Returns all expected columns
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_get_department_config(2040000000000000000::bigint, 'finance')

;

SELECT ok(
    (SELECT id IS NOT NULL FROM result) AND
    (SELECT guild_id IS NOT NULL FROM result) AND
    (SELECT department IS NOT NULL FROM result) AND
    (SELECT role_id IS NOT NULL FROM result) AND
    (SELECT welfare_amount IS NOT NULL FROM result) AND
    (SELECT welfare_interval_hours IS NOT NULL FROM result) AND
    (SELECT tax_rate_basis IS NOT NULL FROM result) AND
    (SELECT tax_rate_percent IS NOT NULL FROM result) AND
    (SELECT max_issuance_per_month IS NOT NULL FROM result) AND
    (SELECT created_at IS NOT NULL FROM result) AND
    (SELECT updated_at IS NOT NULL FROM result),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
