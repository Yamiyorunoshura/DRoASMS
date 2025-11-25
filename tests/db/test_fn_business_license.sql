\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(11);
SELECT set_config('search_path', 'pgtap, governance, public', false);

-- Ensure functions exist
SELECT has_function(
    'governance',
    'fn_issue_business_license',
    ARRAY['bigint', 'bigint', 'text', 'bigint', 'timestamptz'],
    'fn_issue_business_license exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_revoke_business_license',
    ARRAY['uuid', 'bigint', 'text'],
    'fn_revoke_business_license exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_get_business_license',
    ARRAY['uuid'],
    'fn_get_business_license exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_list_business_licenses',
    ARRAY['bigint', 'text', 'text', 'integer', 'integer'],
    'fn_list_business_licenses exists with expected signature'
);

-- Clean up test data
DELETE FROM governance.business_licenses WHERE guild_id = 2090000000000000000;

-- Test 1: Issue business license successfully
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_issue_business_license(
        2090000000000000000::bigint,
        2090000000000000001::bigint,
        '一般商業許可',
        2090000000000000099::bigint,
        timezone('utc', now()) + interval '365 days'
    );

SELECT ok(
    (SELECT license_id IS NOT NULL FROM result),
    'creates business license successfully'
);

SELECT is(
    (SELECT status FROM result),
    'active',
    'new license has active status'
);

-- Test 2: Duplicate active license rejected
SELECT throws_ok(
    $$SELECT * FROM governance.fn_issue_business_license(
        2090000000000000000::bigint,
        2090000000000000001::bigint,
        '一般商業許可',
        2090000000000000099::bigint,
        timezone('utc', now()) + interval '365 days'
    )$$,
    '23505',
    NULL,
    'duplicate active license is rejected'
);

-- Test 3: Different license type can be issued
DROP TABLE IF EXISTS result2;
CREATE TEMP TABLE result2 AS
    SELECT * FROM governance.fn_issue_business_license(
        2090000000000000000::bigint,
        2090000000000000001::bigint,
        '特殊經營許可',
        2090000000000000099::bigint,
        timezone('utc', now()) + interval '180 days'
    );

SELECT ok(
    (SELECT license_id IS NOT NULL FROM result2),
    'different license type can be issued to same user'
);

-- Test 4: Revoke license successfully
DROP TABLE IF EXISTS revoke_result;
CREATE TEMP TABLE revoke_result AS
    SELECT * FROM governance.fn_revoke_business_license(
        (SELECT license_id FROM result),
        2090000000000000099::bigint,
        '違規經營'
    );

SELECT is(
    (SELECT status FROM revoke_result),
    'revoked',
    'license status changed to revoked'
);

SELECT ok(
    (SELECT revoke_reason = '違規經營' FROM revoke_result),
    'revoke reason is recorded'
);

-- Test 5: List business licenses with pagination
SELECT is(
    (
        SELECT count(*) FROM governance.fn_list_business_licenses(
            2090000000000000000::bigint,
            NULL,
            NULL,
            10,
            0
        )
    )::bigint,
    2::bigint,
    'list returns correct count'
);

-- Clean up
DELETE FROM governance.business_licenses WHERE guild_id = 2090000000000000000;

SELECT finish();
ROLLBACK;
