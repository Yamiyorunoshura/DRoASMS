\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(5);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_update_government_account_balance',
    ARRAY['bigint', 'bigint'],
    'fn_update_government_account_balance exists with expected signature'
);

-- Setup: Create government account
SELECT governance.fn_upsert_government_account(
    2070000000000000001::bigint,
    2070000000000000000::bigint,
    'finance',
    10000::bigint
);

-- Test 1: Updates balance
SELECT governance.fn_update_government_account_balance(
    2070000000000000001::bigint,
    20000::bigint
);

SELECT is(
    (
        SELECT balance FROM governance.government_accounts
        WHERE account_id = 2070000000000000001
    ),
    20000::bigint,
    'updates balance correctly'
);

DROP TABLE IF EXISTS gov_account_prev;
CREATE TEMP TABLE gov_account_prev AS
SELECT updated_at FROM governance.government_accounts
WHERE account_id = 2070000000000000001;

SELECT governance.fn_update_government_account_balance(
    2070000000000000001::bigint,
    15000::bigint
);

SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM gov_account_prev)
        FROM governance.government_accounts
        WHERE account_id = 2070000000000000001
    ),
    'updated_at is updated'
);

DROP TABLE gov_account_prev;

-- Test 3: Can update to zero
SELECT governance.fn_update_government_account_balance(
    2070000000000000001::bigint,
    0::bigint
);

SELECT is(
    (
        SELECT balance FROM governance.government_accounts
        WHERE account_id = 2070000000000000001
    ),
    0::bigint,
    'can update to zero'
);

-- Test 4: Works with non-existent account_id (no error)
SELECT governance.fn_update_government_account_balance(
    8999999999999999999::bigint,
    1000::bigint
);

SELECT ok(
    TRUE,
    'handles non-existent account_id gracefully'
);

SELECT finish();
ROLLBACK;
