\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(8);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_attempt_cancel_proposal',
    ARRAY['uuid'],
    'fn_attempt_cancel_proposal exists with expected signature'
);

-- Setup: Create council config and proposal
SELECT governance.fn_upsert_council_config(
    1060000000000000000::bigint,
    1060000000000000001::bigint,
    1060000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1060000000000000000::bigint,
        1060000000000000003::bigint,
        1060000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Cancels proposal when no votes exist
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    governance.fn_attempt_cancel_proposal((SELECT proposal_id FROM proposal_id)),
    'cancels proposal when no votes exist'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT is(
    (
        SELECT status FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    '已撤案',
    'status is set to 已撤案'
);

-- Test 2: Cannot cancel when votes exist
WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1060000000000000000::bigint,
        1060000000000000003::bigint,
        1060000000000000004::bigint,
        500::bigint,
        'Test proposal 2',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal2 FROM proposal;

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal2
)
INSERT INTO governance.votes (proposal_id, voter_id, choice)
VALUES ((SELECT proposal_id FROM proposal_id), 1060000000000000005::bigint, 'approve');

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal2
)
SELECT ok(
    NOT governance.fn_attempt_cancel_proposal((SELECT proposal_id FROM proposal_id)),
    'cannot cancel proposal when votes exist'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal2
)
SELECT is(
    (
        SELECT status FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    '進行中',
    'status remains 進行中 when votes exist'
);

-- Test 3: Cannot cancel non-active proposal
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
UPDATE governance.proposals
SET status = '已通過'
WHERE proposal_id = (SELECT proposal_id FROM proposal_id);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    NOT governance.fn_attempt_cancel_proposal((SELECT proposal_id FROM proposal_id)),
    'cannot cancel non-active proposal'
);

-- Test 4: Returns false for non-existent proposal_id
SELECT ok(
    NOT governance.fn_attempt_cancel_proposal('00000000-0000-0000-0000-000000000000'::uuid),
    'returns false for non-existent proposal_id'
);

-- Test 5: Updated_at is updated on cancel
WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1060000000000000000::bigint,
        1060000000000000003::bigint,
        1060000000000000004::bigint,
        300::bigint,
        'Test proposal 3',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal3 FROM proposal;

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal3
),
old_updated_at AS (
    SELECT updated_at FROM governance.proposals
    WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
)
SELECT * INTO TEMP TABLE proposal_old_timestamp FROM old_updated_at;

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal3
)
SELECT governance.fn_attempt_cancel_proposal((SELECT proposal_id FROM proposal_id));

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal3
)
SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM proposal_old_timestamp)
        FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    'updated_at is updated on cancel'
);

DROP TABLE test_proposal;
DROP TABLE test_proposal2;
DROP TABLE test_proposal3;

SELECT finish();
ROLLBACK;
