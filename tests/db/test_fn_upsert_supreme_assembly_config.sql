\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_upsert_supreme_assembly_config',
    ARRAY['bigint', 'bigint', 'bigint'],
    'fn_upsert_supreme_assembly_config exists with expected signature'
);

-- Test 1: Insert new config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_supreme_assembly_config(
        3010000000000000000::bigint,
        3010000000000000001::bigint,
        3010000000000000002::bigint
    )
;

SELECT is(
    (SELECT speaker_role_id FROM result),
    3010000000000000001::bigint,
    'inserts new config with correct speaker_role_id'
);

SELECT is(
    (SELECT member_role_id FROM result),
    3010000000000000002::bigint,
    'inserts new config with correct member_role_id'
);

-- Test 2: Update existing config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_supreme_assembly_config(
        3010000000000000000::bigint,
        3010000000000000003::bigint,
        3010000000000000004::bigint
    )
;

SELECT is(
    (SELECT speaker_role_id FROM result),
    3010000000000000003::bigint,
    'updates existing config with new speaker_role_id'
);

SELECT is(
    (SELECT member_role_id FROM result),
    3010000000000000004::bigint,
    'updates existing config with new member_role_id'
);

-- Test 3: Returns all expected columns
SELECT ok(
    (SELECT guild_id IS NOT NULL FROM result) AND
    (SELECT speaker_role_id IS NOT NULL FROM result) AND
    (SELECT member_role_id IS NOT NULL FROM result) AND
    (SELECT created_at IS NOT NULL FROM result) AND
    (SELECT updated_at IS NOT NULL FROM result),
    'returns all expected columns'
);

SELECT finish();
ROLLBACK;
