\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_votes_detail',
    ARRAY['uuid'],
    'fn_list_votes_detail exists with expected signature'
);

-- Setup: Create council config and proposal
SELECT governance.fn_upsert_council_config(
    1090000000000000000::bigint,
    1090000000000000001::bigint,
    1090000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1090000000000000000::bigint,
        1090000000000000003::bigint,
        1090000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Returns empty result when no votes exist
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
votes AS (
    SELECT * FROM governance.fn_list_votes_detail((SELECT proposal_id FROM proposal_id))
)
SELECT is(
    (SELECT count(*) FROM votes),
    0::bigint,
    'returns empty result when no votes exist'
);

-- Test 2: Returns all votes
DO $$
DECLARE
    pid uuid;
BEGIN
    SELECT proposal_id INTO pid FROM test_proposal;
    PERFORM governance.fn_upsert_vote(pid, 1090000000000000005::bigint, 'approve');
    PERFORM governance.fn_upsert_vote(pid, 1090000000000000006::bigint, 'reject');
    PERFORM governance.fn_upsert_vote(pid, 1090000000000000007::bigint, 'abstain');
END $$;

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
votes AS (
    SELECT * FROM governance.fn_list_votes_detail((SELECT proposal_id FROM proposal_id))
)
SELECT is(
    (SELECT count(*) FROM votes),
    3::bigint,
    'returns all votes'
);

-- Test 3: Returns correct voter_id and choice
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
votes AS (
    SELECT * FROM governance.fn_list_votes_detail((SELECT proposal_id FROM proposal_id))
)
SELECT ok(
    EXISTS (SELECT 1 FROM votes WHERE voter_id = 1090000000000000005::bigint AND choice = 'approve') AND
    EXISTS (SELECT 1 FROM votes WHERE voter_id = 1090000000000000006::bigint AND choice = 'reject') AND
    EXISTS (SELECT 1 FROM votes WHERE voter_id = 1090000000000000007::bigint AND choice = 'abstain'),
    'returns correct voter_id and choice'
);

-- Test 4: Ordered by updated_at
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
votes AS (
    SELECT * FROM governance.fn_list_votes_detail((SELECT proposal_id FROM proposal_id))
)
SELECT ok(
    (
        SELECT array_agg(voter_id ORDER BY voter_id) = ARRAY[1090000000000000005::bigint, 1090000000000000006::bigint, 1090000000000000007::bigint]
        FROM votes
    ),
    'votes are ordered by updated_at'
);

-- Test 5: Returns empty result for non-existent proposal_id
WITH votes AS (
    SELECT * FROM governance.fn_list_votes_detail('00000000-0000-0000-0000-000000000000'::uuid)
)
SELECT is(
    (SELECT count(*) FROM votes),
    0::bigint,
    'returns empty result for non-existent proposal_id'
);

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
