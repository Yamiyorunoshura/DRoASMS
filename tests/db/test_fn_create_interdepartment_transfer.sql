\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_create_interdepartment_transfer',
    ARRAY['bigint', 'text', 'text', 'bigint', 'text', 'bigint'],
    'fn_create_interdepartment_transfer exists with expected signature'
);

DELETE FROM governance.interdepartment_transfers WHERE guild_id = 2170000000000000000;

-- Test 1: Creates interdepartment transfer
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_interdepartment_transfer(
        2170000000000000000::bigint,
        'finance',
        'security',
        5000::bigint,
        'Budget allocation',
        2170000000000000001::bigint
    )

;

SELECT ok(
    (SELECT transfer_id IS NOT NULL FROM result),
    'creates interdepartment transfer'
);

SELECT is(
    (SELECT amount FROM result),
    5000::bigint,
    'returns correct amount'
);

-- Test 2: All fields are stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_interdepartment_transfer(
        2170000000000000000::bigint,
        'security',
        'finance',
        3000::bigint,
        'Refund',
        2170000000000000002::bigint
    )

;

SELECT ok(
    (SELECT guild_id = 2170000000000000000::bigint FROM result) AND
    (SELECT from_department = 'security' FROM result) AND
    (SELECT to_department = 'finance' FROM result) AND
    (SELECT amount = 3000::bigint FROM result) AND
    (SELECT reason = 'Refund' FROM result) AND
    (SELECT performed_by = 2170000000000000002::bigint FROM result) AND
    (SELECT transferred_at IS NOT NULL FROM result),
    'all fields are stored correctly'
);

-- Test 3: Transferred_at is set automatically
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_interdepartment_transfer(
        2170000000000000000::bigint,
        'finance',
        'security',
        1000::bigint,
        'Test transfer',
        2170000000000000003::bigint
    )

;

SELECT ok(
    (SELECT transferred_at <= timezone('utc', now()) + interval '1 second' FROM result) AND
    (SELECT transferred_at >= timezone('utc', now()) - interval '1 second' FROM result),
    'transferred_at is set automatically'
);

-- Test 4: Multiple transfers can be created
SELECT governance.fn_create_interdepartment_transfer(
    2170000000000000000::bigint,
    'security',
    'finance',
    2000::bigint,
    'Another transfer',
    2170000000000000004::bigint
);

SELECT is(
    (
        SELECT count(*) FROM governance.interdepartment_transfers
        WHERE guild_id = 2170000000000000000
    ),
    4::bigint,
    'multiple transfers can be created'
);

-- Test 5: Amount can be zero
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_interdepartment_transfer(
        2170000000000000000::bigint,
        'finance',
        'security',
        0::bigint,
        'Zero transfer',
        2170000000000000005::bigint
    )

;

SELECT is(
    (SELECT amount FROM result),
    0::bigint,
    'amount can be zero'
);

SELECT finish();
ROLLBACK;
