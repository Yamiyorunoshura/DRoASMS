\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(10);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_fetch_tally',
    ARRAY['uuid'],
    'fn_fetch_tally exists with expected signature'
);

-- Setup: Create council config and proposal
SELECT governance.fn_upsert_council_config(
    1080000000000000000::bigint,
    1080000000000000001::bigint,
    1080000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1080000000000000000::bigint,
        1080000000000000003::bigint,
        1080000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

CREATE OR REPLACE TEMP VIEW tally AS
SELECT * FROM governance.fn_fetch_tally((SELECT proposal_id FROM test_proposal));

SELECT is(
    (SELECT approve FROM tally),
    0,
    'returns 0 approve when no votes exist'
);

SELECT is(
    (SELECT reject FROM tally),
    0,
    'returns 0 reject when no votes exist'
);

SELECT is(
    (SELECT abstain FROM tally),
    0,
    'returns 0 abstain when no votes exist'
);

SELECT is(
    (SELECT total_voted FROM tally),
    0,
    'returns 0 total_voted when no votes exist'
);

DO $$
DECLARE
    pid uuid := (SELECT proposal_id FROM test_proposal);
BEGIN
    PERFORM governance.fn_upsert_vote(pid, 1080000000000000005::bigint, 'approve');
    PERFORM governance.fn_upsert_vote(pid, 1080000000000000006::bigint, 'approve');
    PERFORM governance.fn_upsert_vote(pid, 1080000000000000007::bigint, 'reject');
    PERFORM governance.fn_upsert_vote(pid, 1080000000000000008::bigint, 'abstain');
END $$;

CREATE OR REPLACE TEMP VIEW tally AS
SELECT * FROM governance.fn_fetch_tally((SELECT proposal_id FROM test_proposal));

SELECT is(
    (SELECT approve FROM tally),
    2,
    'counts approve votes correctly'
);

SELECT is(
    (SELECT reject FROM tally),
    1,
    'counts reject votes correctly'
);

SELECT is(
    (SELECT abstain FROM tally),
    1,
    'counts abstain votes correctly'
);

SELECT is(
    (SELECT total_voted FROM tally),
    4,
    'counts total_voted correctly'
);

CREATE OR REPLACE TEMP VIEW tally AS
SELECT * FROM governance.fn_fetch_tally('00000000-0000-0000-0000-000000000000'::uuid);

SELECT is(
    (SELECT total_voted FROM tally),
    0,
    'returns zeros for non-existent proposal_id'
);

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
