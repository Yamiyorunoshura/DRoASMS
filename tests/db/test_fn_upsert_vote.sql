\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_upsert_vote',
    ARRAY['uuid', 'bigint', 'text'],
    'fn_upsert_vote exists with expected signature'
);

-- Setup: Create council config and proposal
SELECT governance.fn_upsert_council_config(
    1070000000000000000::bigint,
    1070000000000000001::bigint,
    1070000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1070000000000000000::bigint,
        1070000000000000003::bigint,
        1070000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Insert new vote
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000005::bigint,
    'approve'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    EXISTS (
        SELECT 1 FROM governance.votes
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
          AND voter_id = 1070000000000000005::bigint
          AND choice = 'approve'
    ),
    'inserts new vote'
);

-- Test 2: Update existing vote
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000005::bigint,
    'reject'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT is(
    (
        SELECT choice FROM governance.votes
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
          AND voter_id = 1070000000000000005::bigint
    ),
    'reject',
    'updates existing vote'
);

-- Test 3: Multiple voters can vote
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000006::bigint,
    'approve'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000007::bigint,
    'abstain'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT is(
    (
        SELECT count(*) FROM governance.votes
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    3::bigint,
    'multiple voters can vote'
);

-- Test 4: Updated_at is updated on vote update
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT updated_at INTO TEMP TABLE old_updated_at
FROM governance.votes
WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
  AND voter_id = 1070000000000000005::bigint;

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000005::bigint,
    'approve'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM old_updated_at)
        FROM governance.votes
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
          AND voter_id = 1070000000000000005::bigint
    ),
    'updated_at is updated on vote update'
);

DROP TABLE old_updated_at;

-- Test 5: All vote choices work
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000008::bigint,
    'approve'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000009::bigint,
    'reject'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_upsert_vote(
    (SELECT proposal_id FROM proposal_id),
    1070000000000000010::bigint,
    'abstain'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    EXISTS (SELECT 1 FROM governance.votes WHERE proposal_id = (SELECT proposal_id FROM proposal_id) AND choice = 'approve') AND
    EXISTS (SELECT 1 FROM governance.votes WHERE proposal_id = (SELECT proposal_id FROM proposal_id) AND choice = 'reject') AND
    EXISTS (SELECT 1 FROM governance.votes WHERE proposal_id = (SELECT proposal_id FROM proposal_id) AND choice = 'abstain'),
    'all vote choices (approve, reject, abstain) work'
);

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
