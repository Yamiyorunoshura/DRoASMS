\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_active_proposals',
    ARRAY[]::text[],
    'fn_list_active_proposals exists with expected signature'
);

-- Setup: Create council config
SELECT governance.fn_upsert_council_config(
    1130000000000000000::bigint,
    1130000000000000001::bigint,
    1130000000000000002::bigint
);

-- Test 1: Returns empty result when no active proposals
SELECT is(
    (SELECT count(*) FROM governance.fn_list_active_proposals()),
    0::bigint,
    'returns empty result when no active proposals'
);

-- Test 2: Returns all active proposals
SELECT governance.fn_create_proposal(
    1130000000000000000::bigint,
    1130000000000000003::bigint,
    1130000000000000004::bigint,
    1000::bigint,
    'Active proposal 1',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

SELECT governance.fn_create_proposal(
    1130000000000000000::bigint,
    1130000000000000003::bigint,
    1130000000000000004::bigint,
    500::bigint,
    'Active proposal 2',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

SELECT is(
    (SELECT count(*) FROM governance.fn_list_active_proposals()),
    2::bigint,
    'returns all active proposals'
);

-- Test 3: Does not return non-active proposals
WITH proposal_id AS (
    SELECT proposal_id FROM governance.proposals
    WHERE guild_id = 1130000000000000000 AND description = 'Active proposal 1'
)
UPDATE governance.proposals
SET status = '已通過'
WHERE proposal_id = (SELECT proposal_id FROM proposal_id);

SELECT is(
    (SELECT count(*) FROM governance.fn_list_active_proposals()),
    1::bigint,
    'does not return non-active proposals'
);

-- Test 4: Ordered by created_at
WITH active AS (
    SELECT * FROM governance.fn_list_active_proposals()
)
SELECT ok(
    (
        SELECT array_agg(description ORDER BY created_at) = ARRAY['Active proposal 2']
        FROM active
    ),
    'ordered by created_at'
);

-- Test 5: Returns proposals from all guilds
SELECT governance.fn_upsert_council_config(
    1130000000000000001::bigint,
    1130000000000000001::bigint,
    1130000000000000002::bigint
);

SELECT governance.fn_create_proposal(
    1130000000000000001::bigint,
    1130000000000000003::bigint,
    1130000000000000004::bigint,
    300::bigint,
    'Active proposal 3',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

SELECT is(
    (SELECT count(*) FROM governance.fn_list_active_proposals()),
    2::bigint,
    'returns proposals from all guilds'
);

SELECT finish();
ROLLBACK;
