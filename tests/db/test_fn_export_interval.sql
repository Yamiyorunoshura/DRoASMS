\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_export_interval',
    ARRAY['bigint', 'timestamptz', 'timestamptz'],
    'fn_export_interval exists with expected signature'
);

-- Setup: Create council config
SELECT governance.fn_upsert_council_config(
    1150000000000000000::bigint,
    1150000000000000001::bigint,
    1150000000000000002::bigint
);

-- Test 1: Returns empty result when no proposals in interval
SELECT is(
    (
        SELECT count(*) FROM governance.fn_export_interval(
            1150000000000000000::bigint,
            timezone('utc', now()) - interval '1 day',
            timezone('utc', now())
        )
    ),
    0::bigint,
    'returns empty result when no proposals in interval'
);

-- Test 2: Returns proposals within interval
SELECT governance.fn_create_proposal(
    1150000000000000000::bigint,
    1150000000000000003::bigint,
    1150000000000000004::bigint,
    1000::bigint,
    'Proposal in interval',
    NULL::text,
    ARRAY[1150000000000000005::bigint],
    72,
    NULL::text
);

SELECT is(
    (
        SELECT count(*) FROM governance.fn_export_interval(
            1150000000000000000::bigint,
            timezone('utc', now()) - interval '1 day',
            timezone('utc', now()) + interval '1 day'
        )
    ),
    1::bigint,
    'returns proposals within interval'
);

-- Test 3: Does not return proposals outside interval
SELECT governance.fn_create_proposal(
    1150000000000000000::bigint,
    1150000000000000003::bigint,
    1150000000000000004::bigint,
    500::bigint,
    'Proposal outside interval',
    NULL::text,
    ARRAY[]::bigint[],
    72,
    NULL::text
);

-- Set created_at to past
UPDATE governance.proposals
SET created_at = timezone('utc', now()) - interval '2 days'
WHERE description = 'Proposal outside interval';

SELECT is(
    (
        SELECT count(*) FROM governance.fn_export_interval(
            1150000000000000000::bigint,
            timezone('utc', now()) - interval '1 day',
            timezone('utc', now()) + interval '1 day'
        )
    ),
    1::bigint,
    'does not return proposals outside interval'
);

-- Test 4: Includes votes JSON
WITH proposal_id AS (
    SELECT proposal_id FROM governance.proposals
    WHERE guild_id = 1150000000000000000 AND description = 'Proposal in interval'
)
INSERT INTO governance.votes (proposal_id, voter_id, choice)
VALUES ((SELECT proposal_id FROM proposal_id), 1150000000000000006::bigint, 'approve');

WITH export AS (
    SELECT * FROM governance.fn_export_interval(
        1150000000000000000::bigint,
        timezone('utc', now()) - interval '1 day',
        timezone('utc', now()) + interval '1 day'
    )
    WHERE description = 'Proposal in interval'
)
SELECT ok(
    (SELECT votes IS NOT NULL FROM export) AND
    (SELECT json_array_length(votes) = 1 FROM export),
    'includes votes JSON'
);

-- Test 5: Includes snapshot JSON
WITH export AS (
    SELECT * FROM governance.fn_export_interval(
        1150000000000000000::bigint,
        timezone('utc', now()) - interval '1 day',
        timezone('utc', now()) + interval '1 day'
    )
    WHERE description = 'Proposal in interval'
)
SELECT ok(
    (SELECT snapshot IS NOT NULL FROM export) AND
    (SELECT json_array_length(snapshot) = 1 FROM export),
    'includes snapshot JSON'
);

-- Test 6: Ordered by created_at
WITH export AS (
    SELECT * FROM governance.fn_export_interval(
        1150000000000000000::bigint,
        timezone('utc', now()) - interval '2 days',
        timezone('utc', now()) + interval '1 day'
    )
)
SELECT ok(
    (
        SELECT array_agg(description ORDER BY created_at) = ARRAY['Proposal outside interval', 'Proposal in interval']
        FROM export
    ),
    'ordered by created_at'
);

SELECT finish();
ROLLBACK;
