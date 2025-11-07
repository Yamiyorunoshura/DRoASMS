\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(5);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_get_council_config',
    ARRAY['bigint'],
    'fn_get_council_config exists with expected signature'
);

-- Setup: Create council config
SELECT governance.fn_upsert_council_config(
    1010000000000000000::bigint,
    1010000000000000001::bigint,
    1010000000000000002::bigint
);

-- Test 1: Returns existing config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_get_council_config(1010000000000000000::bigint)

;

SELECT is(
    (SELECT council_role_id FROM result),
    1010000000000000001::bigint,
    'returns existing council config'
);

SELECT is(
    (SELECT council_account_member_id FROM result),
    1010000000000000002::bigint,
    'returns correct council_account_member_id'
);

-- Test 2: Returns empty result for non-existent guild
SELECT is(
    (SELECT count(*) FROM governance.fn_get_council_config(8999999999999999999::bigint)),
    0::bigint,
    'returns empty result for non-existent guild'
);

-- Test 3: Returns all expected columns
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_get_council_config(1010000000000000000::bigint)

;

SELECT ok(
    (SELECT guild_id IS NOT NULL FROM result) AND
    (SELECT council_role_id IS NOT NULL FROM result) AND
    (SELECT council_account_member_id IS NOT NULL FROM result) AND
    (SELECT created_at IS NOT NULL FROM result) AND
    (SELECT updated_at IS NOT NULL FROM result),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
