\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(5);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_mark_reminded',
    ARRAY['uuid'],
    'fn_mark_reminded exists with expected signature'
);

-- Setup: Create council config and proposal
SELECT governance.fn_upsert_council_config(
    1140000000000000000::bigint,
    1140000000000000001::bigint,
    1140000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1140000000000000000::bigint,
        1140000000000000003::bigint,
        1140000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Sets reminder_sent to true
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_mark_reminded((SELECT proposal_id FROM proposal_id));

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    (
        SELECT reminder_sent FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    'sets reminder_sent to true'
);

DROP TABLE IF EXISTS old_updated_at;
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT updated_at INTO TEMP TABLE old_updated_at
FROM governance.proposals
WHERE proposal_id = (SELECT proposal_id FROM proposal_id);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_mark_reminded((SELECT proposal_id FROM proposal_id));

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM old_updated_at)
        FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    'updated_at is updated'
);

DROP TABLE old_updated_at;

-- Test 3: Can be called multiple times (idempotent)
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_mark_reminded((SELECT proposal_id FROM proposal_id));

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    (
        SELECT reminder_sent FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    'can be called multiple times (idempotent)'
);

-- Test 4: Works with non-existent proposal_id (no error)
SELECT governance.fn_mark_reminded('00000000-0000-0000-0000-000000000000'::uuid);

SELECT ok(
    TRUE,
    'handles non-existent proposal_id gracefully'
);

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
