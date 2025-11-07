\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_count_active_proposals',
    ARRAY['bigint'],
    'fn_count_active_proposals exists with expected signature'
);

-- Setup: Create council config
SELECT governance.fn_upsert_council_config(
    1050000000000000000::bigint,
    1050000000000000001::bigint,
    1050000000000000002::bigint
);

-- Test 1: Returns 0 for guild with no proposals
SELECT is(
    governance.fn_count_active_proposals(1050000000000000000::bigint),
    0,
    'returns 0 for guild with no proposals'
);

-- Test 2: Counts active proposals correctly
SELECT governance.fn_create_proposal(
    1050000000000000000::bigint,
    1050000000000000003::bigint,
    1050000000000000004::bigint,
    100::bigint,
    'Test proposal 1',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

SELECT governance.fn_create_proposal(
    1050000000000000000::bigint,
    1050000000000000003::bigint,
    1050000000000000004::bigint,
    200::bigint,
    'Test proposal 2',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

SELECT is(
    governance.fn_count_active_proposals(1050000000000000000::bigint),
    2,
    'counts active proposals correctly'
);

-- Test 3: Does not count non-active proposals
WITH proposal_id AS (
    SELECT proposal_id FROM governance.proposals
    WHERE guild_id = 1050000000000000000
    ORDER BY created_at DESC LIMIT 1
)
UPDATE governance.proposals
SET status = '已通過'
WHERE proposal_id = (SELECT proposal_id FROM proposal_id);

SELECT is(
    governance.fn_count_active_proposals(1050000000000000000::bigint),
    1,
    'does not count non-active proposals'
);

-- Test 4: Returns 0 for non-existent guild
SELECT is(
    governance.fn_count_active_proposals(8999999999999999999::bigint),
    0,
    'returns 0 for non-existent guild'
);

-- Test 5: Returns 0 when all proposals are non-active
WITH proposal_id AS (
    SELECT proposal_id FROM governance.proposals
    WHERE guild_id = 1050000000000000000 AND status = '進行中'
)
UPDATE governance.proposals
SET status = '已撤案'
WHERE proposal_id IN (SELECT proposal_id FROM proposal_id);

SELECT is(
    governance.fn_count_active_proposals(1050000000000000000::bigint),
    0,
    'returns 0 when all proposals are non-active'
);

SELECT finish();
ROLLBACK;
