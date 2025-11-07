\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_create_tax_record',
    ARRAY['bigint', 'bigint', 'bigint', 'int', 'bigint', 'text', 'text'],
    'fn_create_tax_record exists with expected signature'
);

DELETE FROM governance.tax_records WHERE guild_id = 2100000000000000000;

-- Test 1: Creates tax record
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
SELECT * FROM governance.fn_create_tax_record(
    2100000000000000000::bigint,
    2100000000000000001::bigint,
    10000::bigint,
    10,
    1000::bigint,
    'income',
    '2025-01'
);

SELECT ok(
    (SELECT tax_id IS NOT NULL FROM result),
    'creates tax record'
);

SELECT is(
    (SELECT tax_amount FROM result),
    1000::bigint,
    'returns correct tax_amount'
);

-- Test 2: All fields are stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
SELECT * FROM governance.fn_create_tax_record(
    2100000000000000000::bigint,
    2100000000000000002::bigint,
    5000::bigint,
    15,
    750::bigint,
    'property',
    '2025-02'
);

SELECT ok(
    (SELECT guild_id = 2100000000000000000::bigint FROM result) AND
    (SELECT taxpayer_id = 2100000000000000002::bigint FROM result) AND
    (SELECT taxable_amount = 5000::bigint FROM result) AND
    (SELECT tax_rate_percent = 15 FROM result) AND
    (SELECT tax_amount = 750::bigint FROM result) AND
    (SELECT tax_type = 'property' FROM result) AND
    (SELECT assessment_period = '2025-02' FROM result) AND
    (SELECT collected_at IS NOT NULL FROM result),
    'all fields are stored correctly'
);

-- Test 3: Collected_at is set automatically
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
SELECT * FROM governance.fn_create_tax_record(
    2100000000000000000::bigint,
    2100000000000000003::bigint,
    3000::bigint,
    5,
    150::bigint,
    'sales',
    '2025-03'
);

SELECT ok(
    (SELECT collected_at <= timezone('utc', now()) + interval '1 second' FROM result) AND
    (SELECT collected_at >= timezone('utc', now()) - interval '1 second' FROM result),
    'collected_at is set automatically'
);

DROP TABLE IF EXISTS result;
SELECT governance.fn_create_tax_record(
    2100000000000000000::bigint,
    2100000000000000004::bigint,
    2000::bigint,
        20,
        400::bigint,
        'luxury',
        '2025-04'
);

SELECT is(
    (
        SELECT count(*) FROM governance.tax_records
        WHERE guild_id = 2100000000000000000
    ),
    4::bigint,
    'multiple tax records can be created'
);

-- Test 5: Tax amount can be zero
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
SELECT * FROM governance.fn_create_tax_record(
    2100000000000000000::bigint,
    2100000000000000005::bigint,
    0::bigint,
    10,
    0::bigint,
    'exempt',
    '2025-05'
);

SELECT is(
    (SELECT tax_amount FROM result),
    0::bigint,
    'tax amount can be zero'
);

SELECT finish();
ROLLBACK;
