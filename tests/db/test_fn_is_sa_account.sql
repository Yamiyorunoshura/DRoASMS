\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_is_sa_account',
    ARRAY['bigint'],
    'fn_is_sa_account exists with expected signature'
);

-- Test 1: Returns true for valid Supreme Assembly account ID
SELECT ok(
    governance.fn_is_sa_account(9200000000123456789::bigint),
    'returns true for valid SA account ID'
);

-- Test 2: Returns true for minimum SA account ID
SELECT ok(
    governance.fn_is_sa_account(9200000000000000000::bigint),
    'returns true for minimum SA account ID'
);

-- 上限為 9.200000000e18 + 9 位後綴（0~999,999,999），即 9200000000999999999
SELECT ok(
    governance.fn_is_sa_account(9200000000999999999::bigint),
    'returns true for maximum SA account ID'
);

-- Test 4: Returns false for account ID below range
SELECT ok(
    NOT governance.fn_is_sa_account(9199999999999999999::bigint),
    'returns false for account ID below range'
);

SELECT ok(
    NOT governance.fn_is_sa_account(9200000001000000000::bigint),
    'returns false for account ID above range'
);

SELECT finish();
ROLLBACK;
