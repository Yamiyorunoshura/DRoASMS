\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_government_accounts',
    ARRAY['bigint'],
    'fn_list_government_accounts exists with expected signature'
);

-- Setup: Create government accounts
SELECT governance.fn_upsert_government_account(
    2060000000000000001::bigint,
    2060000000000000000::bigint,
    'finance',
    10000::bigint
);

SELECT governance.fn_upsert_government_account(
    2060000000000000002::bigint,
    2060000000000000000::bigint,
    'security',
    5000::bigint
);

-- Test 1: Returns all accounts for guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_government_accounts(2060000000000000000::bigint)),
    2::bigint,
    'returns all accounts for guild'
);

-- Test 2: Ordered by department
WITH accounts AS (
    SELECT * FROM governance.fn_list_government_accounts(2060000000000000000::bigint)
)
SELECT ok(
    (
        SELECT array_agg(department ORDER BY department) = ARRAY['finance', 'security']
        FROM accounts
    ),
    'ordered by department'
);

-- Test 3: Returns correct data
WITH accounts AS (
    SELECT * FROM governance.fn_list_government_accounts(2060000000000000000::bigint)
    WHERE department = 'finance'
)
SELECT is(
    (SELECT balance FROM accounts),
    10000::bigint,
    'returns correct data'
);

-- Test 4: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_list_government_accounts(8999999999999999999::bigint)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 5: Returns all expected columns
WITH accounts AS (
    SELECT * FROM governance.fn_list_government_accounts(2060000000000000000::bigint)
    LIMIT 1
)
SELECT ok(
    (SELECT account_id IS NOT NULL FROM accounts) AND
    (SELECT guild_id IS NOT NULL FROM accounts) AND
    (SELECT department IS NOT NULL FROM accounts) AND
    (SELECT balance IS NOT NULL FROM accounts) AND
    (SELECT created_at IS NOT NULL FROM accounts) AND
    (SELECT updated_at IS NOT NULL FROM accounts),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
