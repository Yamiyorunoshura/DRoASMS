\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_list_reminder_candidates',
    ARRAY[]::text[],
    'fn_list_reminder_candidates exists with expected signature'
);

-- Setup: Create council config
SELECT governance.fn_upsert_council_config(
    1120000000000000000::bigint,
    1120000000000000001::bigint,
    1120000000000000002::bigint
);

-- Test 1: Returns empty result when no candidates
SELECT is(
    (SELECT count(*) FROM governance.fn_list_reminder_candidates()),
    0::bigint,
    'returns empty result when no candidates'
);

-- Test 2: Returns proposals within 24h of deadline and not reminded
SELECT governance.fn_create_proposal(
    1120000000000000000::bigint,
    1120000000000000003::bigint,
    1120000000000000004::bigint,
    1000::bigint,
    'Reminder candidate',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

-- Set deadline to 23 hours from now (within 24h window)
UPDATE governance.proposals
SET deadline_at = timezone('utc', now()) + interval '23 hours',
    reminder_sent = false
WHERE guild_id = 1120000000000000000 AND status = '進行中';

SELECT is(
    (SELECT count(*) FROM governance.fn_list_reminder_candidates()),
    1::bigint,
    'returns proposals within 24h of deadline and not reminded'
);

-- Test 3: Does not return already reminded proposals
UPDATE governance.proposals
SET reminder_sent = true
WHERE guild_id = 1120000000000000000 AND deadline_at = timezone('utc', now()) + interval '23 hours';

SELECT is(
    (SELECT count(*) FROM governance.fn_list_reminder_candidates()),
    0::bigint,
    'does not return already reminded proposals'
);

-- Test 4: Does not return proposals beyond 24h window
SELECT governance.fn_create_proposal(
    1120000000000000000::bigint,
    1120000000000000003::bigint,
    1120000000000000004::bigint,
    500::bigint,
    'Far future proposal',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

UPDATE governance.proposals
SET deadline_at = timezone('utc', now()) + interval '25 hours',
    reminder_sent = false
WHERE guild_id = 1120000000000000000 AND description = 'Far future proposal';

SELECT is(
    (SELECT count(*) FROM governance.fn_list_reminder_candidates()),
    0::bigint,
    'does not return proposals beyond 24h window'
);

-- Test 5: Only returns active proposals
UPDATE governance.proposals
SET deadline_at = timezone('utc', now()) + interval '23 hours',
    reminder_sent = false,
    status = '已通過'
WHERE guild_id = 1120000000000000000 AND description = 'Far future proposal';

SELECT is(
    (SELECT count(*) FROM governance.fn_list_reminder_candidates()),
    0::bigint,
    'only returns active proposals'
);

-- Test 6: Returns proposals exactly at 24h boundary
SELECT governance.fn_create_proposal(
    1120000000000000000::bigint,
    1120000000000000003::bigint,
    1120000000000000004::bigint,
    300::bigint,
    'Boundary proposal',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

UPDATE governance.proposals
SET deadline_at = timezone('utc', now()) + interval '24 hours',
    reminder_sent = false
WHERE guild_id = 1120000000000000000 AND description = 'Boundary proposal';

SELECT is(
    (SELECT count(*) FROM governance.fn_list_reminder_candidates()),
    1::bigint,
    'returns proposals exactly at 24h boundary'
);

SELECT finish();
ROLLBACK;
