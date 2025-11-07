\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_unvoted_members',
    ARRAY['uuid'],
    'fn_list_unvoted_members exists with expected signature'
);

-- Setup: Create council config and proposal with snapshot
SELECT governance.fn_upsert_council_config(
    1160000000000000000::bigint,
    1160000000000000001::bigint,
    1160000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1160000000000000000::bigint,
        1160000000000000003::bigint,
        1160000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[1160000000000000005::bigint, 1160000000000000006::bigint, 1160000000000000007::bigint],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Returns all snapshot members when no votes
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
unvoted AS (
    SELECT * FROM governance.fn_list_unvoted_members((SELECT proposal_id FROM proposal_id))
)
SELECT is(
    (SELECT count(*) FROM unvoted),
    3::bigint,
    'returns all snapshot members when no votes'
);

-- Test 2: Excludes members who have voted
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
INSERT INTO governance.votes (proposal_id, voter_id, choice)
VALUES ((SELECT proposal_id FROM proposal_id), 1160000000000000005::bigint, 'approve');

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
unvoted AS (
    SELECT * FROM governance.fn_list_unvoted_members((SELECT proposal_id FROM proposal_id))
)
SELECT is(
    (SELECT count(*) FROM unvoted),
    2::bigint,
    'excludes members who have voted'
);

-- Test 3: Returns correct unvoted member IDs
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
unvoted AS (
    SELECT * FROM governance.fn_list_unvoted_members((SELECT proposal_id FROM proposal_id))
)
SELECT ok(
    EXISTS (SELECT 1 FROM unvoted WHERE member_id = 1160000000000000006::bigint) AND
    EXISTS (SELECT 1 FROM unvoted WHERE member_id = 1160000000000000007::bigint) AND
    NOT EXISTS (SELECT 1 FROM unvoted WHERE member_id = 1160000000000000005::bigint),
    'returns correct unvoted member IDs'
);

-- Test 4: Returns empty result when all members have voted
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
INSERT INTO governance.votes (proposal_id, voter_id, choice)
VALUES
    ((SELECT proposal_id FROM proposal_id), 1160000000000000006::bigint, 'reject'),
    ((SELECT proposal_id FROM proposal_id), 1160000000000000007::bigint, 'abstain');

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
unvoted AS (
    SELECT * FROM governance.fn_list_unvoted_members((SELECT proposal_id FROM proposal_id))
)
SELECT is(
    (SELECT count(*) FROM unvoted),
    0::bigint,
    'returns empty result when all members have voted'
);

-- Test 5: Returns empty result for non-existent proposal_id
SELECT is(
    (SELECT count(*) FROM governance.fn_list_unvoted_members('00000000-0000-0000-0000-000000000000'::uuid)),
    0::bigint,
    'returns empty result for non-existent proposal_id'
);

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
