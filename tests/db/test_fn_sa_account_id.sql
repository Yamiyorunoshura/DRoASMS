\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(4);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_sa_account_id',
    ARRAY['bigint'],
    'fn_sa_account_id exists with expected signature'
);

-- Test 1: Returns correct account ID for given guild_id
SELECT is(
    governance.fn_sa_account_id(123456789::bigint),
    9200000000123456789::bigint,
    'returns correct account ID: 9.2e15 + guild_id'
);

-- Test 2: Returns correct account ID for zero guild_id
SELECT is(
    governance.fn_sa_account_id(0::bigint),
    9200000000000000000::bigint,
    'returns correct account ID for zero guild_id'
);

-- Test 3: Returns correct account ID for large guild_id
SELECT is(
    governance.fn_sa_account_id(999999999999999999::bigint),
    9200000000999999999::bigint,
    'returns correct account ID for large guild_id'
);

SELECT finish();
ROLLBACK;
