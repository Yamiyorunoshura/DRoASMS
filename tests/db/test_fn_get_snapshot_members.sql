\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(5);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_get_snapshot_members',
    ARRAY['uuid'],
    'fn_get_snapshot_members exists with expected signature'
);

-- Setup: Create council config and proposal with snapshot
SELECT governance.fn_upsert_council_config(
    1040000000000000000::bigint,
    1040000000000000001::bigint,
    1040000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1040000000000000000::bigint,
        1040000000000000003::bigint,
        1040000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[1040000000000000005::bigint, 1040000000000000006::bigint, 1040000000000000007::bigint],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Returns snapshot member IDs
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
members AS (
    SELECT * FROM governance.fn_get_snapshot_members((SELECT proposal_id FROM proposal_id))
)
SELECT is(
    (SELECT count(*) FROM members),
    3::bigint,
    'returns all snapshot member IDs'
);

-- Test 2: Returns correct member IDs
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
members AS (
    SELECT * FROM governance.fn_get_snapshot_members((SELECT proposal_id FROM proposal_id))
)
SELECT ok(
    EXISTS (SELECT 1 FROM members WHERE member_id = 1040000000000000005::bigint) AND
    EXISTS (SELECT 1 FROM members WHERE member_id = 1040000000000000006::bigint) AND
    EXISTS (SELECT 1 FROM members WHERE member_id = 1040000000000000007::bigint),
    'returns correct snapshot member IDs'
);

-- Test 3: Returns empty result for proposal with no snapshot
WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1040000000000000000::bigint,
        1040000000000000003::bigint,
        1040000000000000004::bigint,
        500::bigint,
        'Test proposal no snapshot',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
),
members AS (
    SELECT * FROM governance.fn_get_snapshot_members((SELECT proposal_id FROM proposal))
)
SELECT is(
    (SELECT count(*) FROM members),
    0::bigint,
    'returns empty result for proposal with no snapshot'
);

-- Test 4: Returns empty result for non-existent proposal_id
SELECT is(
    (SELECT count(*) FROM governance.fn_get_snapshot_members('00000000-0000-0000-0000-000000000000'::uuid)),
    0::bigint,
    'returns empty result for non-existent proposal_id'
);

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
