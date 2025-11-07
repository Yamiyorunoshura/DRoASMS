\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_create_currency_issuance',
    ARRAY['bigint', 'bigint', 'text', 'bigint', 'text'],
    'fn_create_currency_issuance exists with expected signature'
);

DELETE FROM governance.currency_issuances WHERE guild_id = 2140000000000000000;

-- Test 1: Creates currency issuance
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_currency_issuance(
        2140000000000000000::bigint,
        10000::bigint,
        'Monthly issuance',
        2140000000000000001::bigint,
        '2025-01'
    )

;

SELECT ok(
    (SELECT issuance_id IS NOT NULL FROM result),
    'creates currency issuance'
);

SELECT is(
    (SELECT amount FROM result),
    10000::bigint,
    'returns correct amount'
);

-- Test 2: All fields are stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_currency_issuance(
        2140000000000000000::bigint,
        5000::bigint,
        'Emergency issuance',
        2140000000000000002::bigint,
        '2025-02'
    )

;

SELECT ok(
    (SELECT guild_id = 2140000000000000000::bigint FROM result) AND
    (SELECT amount = 5000::bigint FROM result) AND
    (SELECT reason = 'Emergency issuance' FROM result) AND
    (SELECT performed_by = 2140000000000000002::bigint FROM result) AND
    (SELECT month_period = '2025-02' FROM result) AND
    (SELECT issued_at IS NOT NULL FROM result),
    'all fields are stored correctly'
);

-- Test 3: Issued_at is set automatically
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_currency_issuance(
        2140000000000000000::bigint,
        3000::bigint,
        'Test issuance',
        2140000000000000003::bigint,
        '2025-03'
    )

;

SELECT ok(
    (SELECT issued_at <= timezone('utc', now()) + interval '1 second' FROM result) AND
    (SELECT issued_at >= timezone('utc', now()) - interval '1 second' FROM result),
    'issued_at is set automatically'
);

-- Test 4: Multiple issuances can be created
SELECT governance.fn_create_currency_issuance(
    2140000000000000000::bigint,
    2000::bigint,
    'Another issuance',
    2140000000000000004::bigint,
    '2025-04'
);

SELECT is(
    (
        SELECT count(*) FROM governance.currency_issuances
        WHERE guild_id = 2140000000000000000
    ),
    4::bigint,
    'multiple issuances can be created'
);

-- Test 5: Amount can be zero
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_currency_issuance(
        2140000000000000000::bigint,
        0::bigint,
        'Zero issuance',
        2140000000000000005::bigint,
        '2025-05'
    )

;

SELECT is(
    (SELECT amount FROM result),
    0::bigint,
    'amount can be zero'
);

SELECT finish();
ROLLBACK;
