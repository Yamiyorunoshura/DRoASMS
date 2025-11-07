\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(6);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_due_proposals',
    ARRAY[]::text[],
    'fn_list_due_proposals exists with expected signature'
);

-- Setup: Create council config
SELECT governance.fn_upsert_council_config(
    1110000000000000000::bigint,
    1110000000000000001::bigint,
    1110000000000000002::bigint
);

-- Test 1: Returns empty result when no due proposals
SELECT is(
    (SELECT count(*) FROM governance.fn_list_due_proposals()),
    0::bigint,
    'returns empty result when no due proposals'
);

-- Test 2: Returns proposals with deadline <= now
SELECT governance.fn_create_proposal(
    1110000000000000000::bigint,
    1110000000000000003::bigint,
    1110000000000000004::bigint,
    1000::bigint,
    'Due proposal',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

-- Set deadline to past
UPDATE governance.proposals
SET deadline_at = timezone('utc', now()) - interval '1 hour'
WHERE guild_id = 1110000000000000000 AND status = '進行中';

SELECT is(
    (SELECT count(*) FROM governance.fn_list_due_proposals()),
    1::bigint,
    'returns proposals with deadline <= now'
);

-- Test 3: Only returns active proposals
UPDATE governance.proposals
SET status = '已通過'
WHERE guild_id = 1110000000000000000 AND deadline_at < timezone('utc', now());

SELECT is(
    (SELECT count(*) FROM governance.fn_list_due_proposals()),
    0::bigint,
    'only returns active proposals'
);

-- Test 4: Does not return proposals with future deadline
SELECT governance.fn_create_proposal(
    1110000000000000000::bigint,
    1110000000000000003::bigint,
    1110000000000000004::bigint,
    500::bigint,
    'Future proposal',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

SELECT is(
    (SELECT count(*) FROM governance.fn_list_due_proposals()),
    0::bigint,
    'does not return proposals with future deadline'
);

-- Test 5: Returns correct proposal data
UPDATE governance.proposals
SET deadline_at = timezone('utc', now()) - interval '1 hour',
    status = '進行中'
WHERE guild_id = 1110000000000000000 AND description = 'Future proposal';

WITH due AS (
    SELECT * FROM governance.fn_list_due_proposals()
)
SELECT ok(
    EXISTS (
        SELECT 1 FROM due
        WHERE description = 'Future proposal'
          AND status = '進行中'
    ),
    'returns correct proposal data'
);

SELECT finish();
ROLLBACK;
