\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_create_welfare_disbursement',
    ARRAY['bigint', 'bigint', 'bigint', 'text', 'text'],
    'fn_create_welfare_disbursement exists with expected signature'
);

DELETE FROM governance.welfare_disbursements WHERE guild_id = 2080000000000000000;

-- Test 1: Creates welfare disbursement
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_welfare_disbursement(
        2080000000000000000::bigint,
        2080000000000000001::bigint,
        500::bigint,
        'monthly',
        'REF001'
    )

;

SELECT ok(
    (SELECT disbursement_id IS NOT NULL FROM result),
    'creates welfare disbursement'
);

SELECT is(
    (SELECT amount FROM result),
    500::bigint,
    'returns correct amount'
);

-- Test 2: All fields are stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_welfare_disbursement(
        2080000000000000000::bigint,
        2080000000000000002::bigint,
        1000::bigint,
        'one-time',
        'REF002'
    )

;

SELECT ok(
    (SELECT guild_id = 2080000000000000000::bigint FROM result) AND
    (SELECT recipient_id = 2080000000000000002::bigint FROM result) AND
    (SELECT amount = 1000::bigint FROM result) AND
    (SELECT disbursement_type = 'one-time' FROM result) AND
    (SELECT reference_id = 'REF002' FROM result) AND
    (SELECT disbursed_at IS NOT NULL FROM result),
    'all fields are stored correctly'
);

-- Test 3: Disbursed_at is set automatically
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_welfare_disbursement(
        2080000000000000000::bigint,
        2080000000000000003::bigint,
        750::bigint,
        'emergency',
        'REF003'
    )

;

SELECT ok(
    (SELECT disbursed_at <= timezone('utc', now()) + interval '1 second' FROM result) AND
    (SELECT disbursed_at >= timezone('utc', now()) - interval '1 second' FROM result),
    'disbursed_at is set automatically'
);

-- Test 4: Reference_id can be NULL
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_welfare_disbursement(
        2080000000000000000::bigint,
        2080000000000000004::bigint,
        300::bigint,
        'bonus',
        NULL::text
    )

;

SELECT ok(
    (SELECT reference_id IS NULL FROM result),
    'reference_id can be NULL'
);

-- Test 5: Multiple disbursements can be created
SELECT governance.fn_create_welfare_disbursement(
    2080000000000000000::bigint,
    2080000000000000005::bigint,
    200::bigint,
    'monthly',
    'REF004'
);

SELECT is(
    (
        SELECT count(*) FROM governance.welfare_disbursements
        WHERE guild_id = 2080000000000000000
    ),
    5::bigint,
    'multiple disbursements can be created'
);

SELECT finish();
ROLLBACK;
