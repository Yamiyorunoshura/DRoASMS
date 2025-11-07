\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_get_proposal',
    ARRAY['uuid'],
    'fn_get_proposal exists with expected signature'
);

-- Setup: Create council config and proposal
SELECT governance.fn_upsert_council_config(
    1030000000000000000::bigint,
    1030000000000000001::bigint,
    1030000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1030000000000000000::bigint,
        1030000000000000003::bigint,
        1030000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        'https://example.com/attachment',
        ARRAY[1030000000000000005::bigint],
        72,
        NULL::text
    )
)
SELECT * INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Returns correct proposal data
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT * INTO TEMP TABLE result
FROM governance.fn_get_proposal((SELECT proposal_id FROM proposal_id));

SELECT is(
    (SELECT guild_id FROM result),
    1030000000000000000::bigint,
    'returns correct guild_id'
);

SELECT is(
    (SELECT amount FROM result),
    1000::bigint,
    'returns correct amount'
);

SELECT is(
    (SELECT description FROM result),
    'Test proposal',
    'returns correct description'
);

-- Test 2: Returns empty result for non-existent proposal_id
SELECT is(
    (SELECT count(*) FROM governance.fn_get_proposal('00000000-0000-0000-0000-000000000000'::uuid)),
    0::bigint,
    'returns empty result for non-existent proposal_id'
);

-- Test 3: Returns all expected columns
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT * INTO TEMP TABLE result_all_fields
FROM governance.fn_get_proposal((SELECT proposal_id FROM proposal_id));

SELECT ok(
    (SELECT proposal_id IS NOT NULL FROM result_all_fields) AND
    (SELECT guild_id IS NOT NULL FROM result_all_fields) AND
    (SELECT proposer_id IS NOT NULL FROM result_all_fields) AND
    (SELECT target_id IS NOT NULL FROM result_all_fields) AND
    (SELECT amount IS NOT NULL FROM result_all_fields) AND
    (SELECT description IS NOT NULL FROM result_all_fields) AND
    (SELECT status IS NOT NULL FROM result_all_fields),
    'returns all expected columns'
);

DROP TABLE result_all_fields;
DROP TABLE result;

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
