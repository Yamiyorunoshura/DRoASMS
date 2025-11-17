\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(9);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_create_identity_record',
    ARRAY['bigint', 'bigint', 'text', 'text', 'bigint'],
    'fn_create_identity_record exists with expected signature'
);

DELETE FROM governance.identity_records WHERE guild_id = 2120000000000000000;

-- Test 1: Creates identity record
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_identity_record(
        2120000000000000000::bigint,
        2120000000000000001::bigint,
        'register',
        'New member registration',
        2120000000000000002::bigint
    )

;

SELECT ok(
    (SELECT record_id IS NOT NULL FROM result),
    'creates identity record'
);

SELECT is(
    (SELECT action FROM result),
    'register',
    'returns correct action'
);

-- Test 2: All fields are stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_identity_record(
        2120000000000000000::bigint,
        2120000000000000003::bigint,
        'verify',
        'Identity verification',
        2120000000000000004::bigint
    )

;

SELECT ok(
    (SELECT guild_id = 2120000000000000000::bigint FROM result) AND
    (SELECT target_id = 2120000000000000003::bigint FROM result) AND
    (SELECT action = 'verify' FROM result) AND
    (SELECT reason = 'Identity verification' FROM result) AND
    (SELECT performed_by = 2120000000000000004::bigint FROM result) AND
    (SELECT performed_at IS NOT NULL FROM result),
    'all fields are stored correctly'
);

-- Test 3: Performed_at is set automatically
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_identity_record(
        2120000000000000000::bigint,
        2120000000000000005::bigint,
        'update',
        'Profile update',
        2120000000000000006::bigint
    )

;

SELECT ok(
    (SELECT performed_at <= timezone('utc', now()) + interval '1 second' FROM result) AND
    (SELECT performed_at >= timezone('utc', now()) - interval '1 second' FROM result),
    'performed_at is set automatically'
);

-- Test 4: Reason can be NULL
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_identity_record(
        2120000000000000000::bigint,
        2120000000000000007::bigint,
        'delete',
        NULL::text,
        2120000000000000008::bigint
    )

;

SELECT ok(
    (SELECT reason IS NULL FROM result),
    'reason can be NULL'
);

-- Test 5: Multiple records can be created
SELECT governance.fn_create_identity_record(
    2120000000000000000::bigint,
    2120000000000000009::bigint,
    'suspend',
    'Violation of rules',
    2120000000000000010::bigint
);

SELECT is(
    (
        SELECT count(*) FROM governance.identity_records
        WHERE guild_id = 2120000000000000000
    ),
    5::bigint,
    'multiple records can be created'
);

-- Test 6: Supports Chinese charge action
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_identity_record(
        2120000000000000000::bigint,
        2120000000000000011::bigint,
        '起訴嫌犯',
        '測試起訴',
        2120000000000000012::bigint
    )

;

SELECT is(
    (SELECT action FROM result),
    '起訴嫌犯',
    'supports charge suspect action'
);

-- Test 7: Supports Chinese revoke charge action
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_create_identity_record(
        2120000000000000000::bigint,
        2120000000000000013::bigint,
        '撤銷起訴',
        '測試撤銷起訴',
        2120000000000000014::bigint
    )

;

SELECT is(
    (SELECT action FROM result),
    '撤銷起訴',
    'supports revoke charge action'
);

SELECT finish();
ROLLBACK;
