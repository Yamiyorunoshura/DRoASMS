\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(12);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_create_proposal',
    ARRAY['bigint', 'bigint', 'bigint', 'bigint', 'text', 'text', 'bigint[]', 'integer', 'text'],
    'fn_create_proposal exists with expected signature'
);

DELETE FROM governance.proposals WHERE guild_id = 1020000000000000000;

-- Setup: Create council config (required for proposals)
SELECT governance.fn_upsert_council_config(
    1020000000000000000::bigint,
    1020000000000000001::bigint,
    1020000000000000002::bigint
);

-- Test 1: Create proposal with snapshot members
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_proposal(
        1020000000000000000::bigint,
        1020000000000000003::bigint,
        1020000000000000004::bigint,
        1000::bigint,
        'Test proposal',
        'https://example.com/attachment',
        ARRAY[1020000000000000005::bigint, 1020000000000000006::bigint, 1020000000000000007::bigint],
        72,
        NULL::text
    )

;

SELECT ok(
    (SELECT proposal_id IS NOT NULL FROM result),
    'creates proposal with snapshot members'
);

SELECT is(
    (SELECT snapshot_n FROM result),
    3,
    'snapshot_n is set correctly'
);

SELECT is(
    (SELECT threshold_t FROM result),
    2,  -- n/2 + 1 = 3/2 + 1 = 2
    'threshold_t is calculated correctly (n/2 + 1)'
);

SELECT is(
    (SELECT status FROM result),
    '進行中',
    'status is set to 進行中'
);

-- Test 2: Snapshot members are inserted
WITH proposal_id AS (
    SELECT proposal_id FROM governance.proposals
    WHERE guild_id = 1020000000000000000
    ORDER BY created_at DESC LIMIT 1
)
SELECT is(
    (SELECT count(*) FROM governance.proposal_snapshots WHERE proposal_id = (SELECT proposal_id FROM proposal_id)),
    3::bigint,
    'snapshot members are inserted'
);

-- Test 3: Deadline is set correctly (default 72 hours)
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_proposal(
        1020000000000000000::bigint,
        1020000000000000003::bigint,
        1020000000000000004::bigint,
        500::bigint,
        'Test proposal 2',
        NULL::text,
        ARRAY[]::bigint[],
        NULL::integer,
        NULL::text
    )

;

SELECT ok(
    (SELECT deadline_at > timezone('utc', now()) + interval '71 hours' FROM result) AND
    (SELECT deadline_at < timezone('utc', now()) + interval '73 hours' FROM result),
    'deadline is set to approximately 72 hours from now (default)'
);

-- Test 4: Custom deadline_hours
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_proposal(
        1020000000000000000::bigint,
        1020000000000000003::bigint,
        1020000000000000004::bigint,
        500::bigint,
        'Test proposal 3',
        NULL::text,
        ARRAY[]::bigint[],
        24,
        NULL::text
    )

;

SELECT ok(
    (SELECT deadline_at > timezone('utc', now()) + interval '23 hours' FROM result) AND
    (SELECT deadline_at < timezone('utc', now()) + interval '25 hours' FROM result),
    'custom deadline_hours is respected'
);

-- Test 5: Empty snapshot array
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_proposal(
        1020000000000000000::bigint,
        1020000000000000003::bigint,
        1020000000000000004::bigint,
        500::bigint,
        'Test proposal 4',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    )

;

SELECT is(
    (SELECT snapshot_n FROM result),
    0,
    'empty snapshot array results in snapshot_n = 0'
);

-- Test 6: Concurrency limit - max 5 active proposals
-- Reset state before concurrency stress test
DELETE FROM governance.proposals WHERE guild_id = 1020000000000000000;

-- Create 5 active proposals
DO $$
DECLARE
    i integer;
BEGIN
    FOR i IN 1..5 LOOP
        PERFORM governance.fn_create_proposal(
            1020000000000000000::bigint,
            1020000000000000003::bigint,
            1020000000000000004::bigint,
            100::bigint,
            'Test proposal ' || i,
            NULL::text,
            ARRAY[]::bigint[],
            72,
            NULL::text
        );
    END LOOP;
END $$;

SELECT is(
    governance.fn_count_active_proposals(1020000000000000000::bigint),
    5,
    'can create up to 5 active proposals'
);

-- Test 7: Error when trying to create 6th active proposal
SELECT throws_like(
    $$ SELECT governance.fn_create_proposal(
        1020000000000000000::bigint,
        1020000000000000003::bigint,
        1020000000000000004::bigint,
        100::bigint,
        'Test proposal 6',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        NULL::text
    ) $$,
    '%active proposal limit reached%',
    'raises exception when trying to create 6th active proposal'
);

-- Test 8: Target department ID is stored
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_proposal(
        1020000000000000001::bigint,
        1020000000000000003::bigint,
        1020000000000000004::bigint,
        500::bigint,
        'Test proposal with dept',
        NULL::text,
        ARRAY[]::bigint[],
        72,
        'finance'::text
    )

;

SELECT is(
    (SELECT target_department_id FROM result),
    'finance',
    'target_department_id is stored when provided'
);

SELECT finish();
ROLLBACK;
