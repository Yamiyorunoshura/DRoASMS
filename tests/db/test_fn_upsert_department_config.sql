\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(8);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_upsert_department_config',
    ARRAY['bigint', 'text', 'bigint', 'bigint', 'integer', 'bigint', 'integer', 'bigint'],
    'fn_upsert_department_config exists with expected signature'
);

-- Test 1: Insert new department config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_department_config(
        2020000000000000000::bigint,
        'finance',
        2020000000000000001::bigint,
        1000::bigint,
        24,
        5000::bigint,
        10,
        10000::bigint
    )

;

SELECT is(
    (SELECT department FROM result),
    'finance',
    'inserts new department config'
);

SELECT is(
    (SELECT welfare_amount FROM result),
    1000::bigint,
    'returns correct welfare_amount'
);

-- Test 2: Update existing config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_department_config(
        2020000000000000000::bigint,
        'finance',
        2020000000000000002::bigint,
        2000::bigint,
        48,
        6000::bigint,
        15,
        20000::bigint
    )

;

SELECT is(
    (SELECT welfare_amount FROM result),
    2000::bigint,
    'updates existing department config'
);

SELECT is(
    (SELECT tax_rate_percent FROM result),
    15,
    'updates tax_rate_percent'
);

DROP TABLE IF EXISTS dept_prev;
CREATE TEMP TABLE dept_prev AS
SELECT updated_at FROM governance.department_configs
WHERE guild_id = 2020000000000000000 AND department = 'finance';

SELECT governance.fn_upsert_department_config(
    2020000000000000000::bigint,
    'finance',
    2020000000000000002::bigint,
    2000::bigint,
    48,
    6000::bigint,
    15,
    20000::bigint
);

SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM dept_prev)
        FROM governance.department_configs
        WHERE guild_id = 2020000000000000000 AND department = 'finance'
    ),
    'updated_at is updated on upsert'
);

DROP TABLE dept_prev;

-- Test 4: Created_at is preserved on update
WITH old_created_at AS (
    SELECT created_at FROM governance.department_configs
    WHERE guild_id = 2020000000000000000 AND department = 'finance'
)
SELECT governance.fn_upsert_department_config(
    2020000000000000000::bigint,
    'finance',
    2020000000000000003::bigint,
    3000::bigint,
    72,
    7000::bigint,
    20,
    30000::bigint
);

SELECT ok(
    (
        SELECT created_at = (
            SELECT created_at FROM governance.department_configs
            WHERE guild_id = 2020000000000000000 AND department = 'finance'
        )
        FROM governance.department_configs
        WHERE guild_id = 2020000000000000000 AND department = 'finance'
    ),
    'created_at is preserved on update'
);

-- Test 5: All fields are stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_department_config(
        2020000000000000001::bigint,
        'security',
        2020000000000000004::bigint,
        500::bigint,
        12,
        3000::bigint,
        5,
        5000::bigint
    )

;

SELECT ok(
    (SELECT role_id = 2020000000000000004::bigint FROM result) AND
    (SELECT welfare_amount = 500::bigint FROM result) AND
    (SELECT welfare_interval_hours = 12 FROM result) AND
    (SELECT tax_rate_basis = 3000::bigint FROM result) AND
    (SELECT tax_rate_percent = 5 FROM result) AND
    (SELECT max_issuance_per_month = 5000::bigint FROM result),
    'all fields are stored correctly'
);

SELECT finish();
ROLLBACK;
