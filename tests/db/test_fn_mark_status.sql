\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_mark_status',
    ARRAY['uuid', 'text', 'uuid', 'text'],
    'fn_mark_status exists with expected signature'
);

-- Setup: Create council config and proposal
SELECT governance.fn_upsert_council_config(
    1100000000000000000::bigint,
    1100000000000000001::bigint,
    1100000000000000002::bigint
);

WITH proposal AS (
    SELECT * FROM governance.fn_create_proposal(
        1100000000000000000::bigint,
        1100000000000000003::bigint,
        1100000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )
)
SELECT proposal_id INTO TEMP TABLE test_proposal FROM proposal;

-- Test 1: Updates status
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_mark_status(
    (SELECT proposal_id FROM proposal_id),
    '已通過',
    NULL::uuid,
    NULL::text
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT is(
    (
        SELECT status FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    '已通過',
    'updates status correctly'
);

-- Test 2: Sets execution_tx_id
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
tx_id AS (
    SELECT '11111111-1111-1111-1111-111111111111'::uuid AS id
)
SELECT governance.fn_mark_status(
    (SELECT proposal_id FROM proposal_id),
    '已執行',
    (SELECT id FROM tx_id),
    NULL::text
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT is(
    (
        SELECT execution_tx_id FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    '11111111-1111-1111-1111-111111111111'::uuid,
    'sets execution_tx_id'
);

-- Test 3: Sets execution_error
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT governance.fn_mark_status(
    (SELECT proposal_id FROM proposal_id),
    '執行失敗',
    NULL::uuid,
    'Transfer failed'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT is(
    (
        SELECT execution_error FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    'Transfer failed',
    'sets execution_error'
);

-- Test 4: Can set both execution_tx_id and execution_error
WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
),
tx_id AS (
    SELECT '22222222-2222-2222-2222-222222222222'::uuid AS id
)
SELECT governance.fn_mark_status(
    (SELECT proposal_id FROM proposal_id),
    '已執行',
    (SELECT id FROM tx_id),
    'Success'
);

WITH proposal_id AS (
    SELECT proposal_id FROM test_proposal
)
SELECT ok(
    (
        SELECT execution_tx_id IS NOT NULL AND execution_error IS NOT NULL
        FROM governance.proposals
        WHERE proposal_id = (SELECT proposal_id FROM proposal_id)
    ),
    'can set both execution_tx_id and execution_error'
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
SELECT governance.fn_mark_status(
    (SELECT proposal_id FROM proposal_id),
    '已撤案',
    NULL::uuid,
    NULL::text
);

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

-- Test 6: Works with non-existent proposal_id (no error)
SELECT governance.fn_mark_status(
    '00000000-0000-0000-0000-000000000000'::uuid,
    '已通過',
    NULL::uuid,
    NULL::text
);

SELECT ok(
    TRUE,
    'handles non-existent proposal_id gracefully'
);

DROP TABLE test_proposal;

SELECT finish();
ROLLBACK;
