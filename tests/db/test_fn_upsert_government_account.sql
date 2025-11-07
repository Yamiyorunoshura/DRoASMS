\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_upsert_government_account',
    ARRAY['bigint', 'bigint', 'text', 'bigint'],
    'fn_upsert_government_account exists with expected signature'
);

-- Test 1: Insert new government account
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_government_account(
        2050000000000000001::bigint,
        2050000000000000000::bigint,
        'finance',
        10000::bigint
    )

;

SELECT is(
    (SELECT account_id FROM result),
    2050000000000000001::bigint,
    'inserts new government account'
);

SELECT is(
    (SELECT balance FROM result),
    10000::bigint,
    'returns correct balance'
);

-- Test 2: Update existing account
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_government_account(
        2050000000000000001::bigint,
        2050000000000000000::bigint,
        'finance',
        20000::bigint
    )

;

SELECT is(
    (SELECT balance FROM result),
    20000::bigint,
    'updates existing government account balance'
);

DROP TABLE IF EXISTS gov_account_prev;
CREATE TEMP TABLE gov_account_prev AS
SELECT updated_at FROM governance.government_accounts
WHERE account_id = 2050000000000000001;

SELECT governance.fn_upsert_government_account(
    2050000000000000001::bigint,
    2050000000000000000::bigint,
    'finance',
    20000::bigint
);

SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM gov_account_prev)
        FROM governance.government_accounts
        WHERE account_id = 2050000000000000001
    ),
    'updated_at is updated on upsert'
);

DROP TABLE gov_account_prev;

-- Test 4: Created_at is preserved on update
WITH old_created_at AS (
    SELECT created_at FROM governance.government_accounts
    WHERE account_id = 2050000000000000001
)
SELECT governance.fn_upsert_government_account(
    2050000000000000001::bigint,
    2050000000000000000::bigint,
    'finance',
    30000::bigint
);

SELECT ok(
    (
        SELECT created_at = (
            SELECT created_at FROM governance.government_accounts
            WHERE account_id = 2050000000000000001
        )
        FROM governance.government_accounts
        WHERE account_id = 2050000000000000001
    ),
    'created_at is preserved on update'
);

-- Test 5: Department is stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_government_account(
        2050000000000000002::bigint,
        2050000000000000000::bigint,
        'security',
        5000::bigint
    )

;

SELECT is(
    (SELECT department FROM result),
    'security',
    'department is stored correctly'
);

SELECT finish();
ROLLBACK;
