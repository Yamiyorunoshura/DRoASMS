\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(15);
SELECT set_config('search_path', 'pgtap, governance, economy, public', false);

-- 全面清空相關資料，避免先前測試或開發資料造成唯一鍵衝突
TRUNCATE governance.companies, governance.business_licenses RESTART IDENTITY CASCADE;

-- Ensure functions exist
SELECT has_function(
    'governance',
    'fn_create_company',
    ARRAY['bigint', 'bigint', 'uuid', 'varchar', 'bigint'],
    'fn_create_company exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_get_company',
    ARRAY['bigint'],
    'fn_get_company exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_get_company_by_account',
    ARRAY['bigint'],
    'fn_get_company_by_account exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_list_user_companies',
    ARRAY['bigint', 'bigint'],
    'fn_list_user_companies exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_list_guild_companies',
    ARRAY['bigint', 'int', 'int'],
    'fn_list_guild_companies exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_get_available_licenses_for_company',
    ARRAY['bigint', 'bigint'],
    'fn_get_available_licenses_for_company exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_check_company_ownership',
    ARRAY['bigint', 'bigint'],
    'fn_check_company_ownership exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_check_company_license_valid',
    ARRAY['bigint'],
    'fn_check_company_license_valid exists with expected signature'
);

SELECT has_function(
    'governance',
    'fn_derive_company_account_id',
    ARRAY['bigint', 'bigint'],
    'fn_derive_company_account_id exists with expected signature'
);

-- Clean up test data
DELETE FROM governance.companies WHERE guild_id = 2091000000000000000;
DELETE FROM governance.business_licenses WHERE guild_id = 2091000000000000000;

-- Create a test license first
DROP TABLE IF EXISTS license_result;
CREATE TEMP TABLE license_result AS
    SELECT * FROM governance.fn_issue_business_license(
        2091000000000000000::bigint,
        2091000000000000001::bigint,
        '一般商業許可',
        2091000000000000099::bigint,
        timezone('utc', now()) + interval '365 days'
    );

-- Test 1: Derive company account ID
SELECT is(
    governance.fn_derive_company_account_id(2091000000000000000::bigint, 1::bigint),
    (9600000000000000 + 1)::bigint,
    'derive_company_account_id calculates correct ID'
);

-- Test 2: Get available licenses for company
SELECT ok(
    (
        SELECT count(*) >= 1 FROM governance.fn_get_available_licenses_for_company(
            2091000000000000000::bigint,
            2091000000000000001::bigint
        )
    ),
    'available licenses returns issued license'
);

-- Test 3: Create company successfully
DROP TABLE IF EXISTS company_result;
CREATE TEMP TABLE company_result AS
    SELECT * FROM governance.fn_create_company(
        2091000000000000000::bigint,
        2091000000000000001::bigint,
        (SELECT license_id FROM license_result),
        '測試公司',
        9600000000000001::bigint
    );

SELECT ok(
    (SELECT id IS NOT NULL FROM company_result),
    'creates company successfully'
);

SELECT is(
    (SELECT name FROM company_result),
    '測試公司',
    'company name is stored correctly'
);

-- Test 4: License no longer available after company creation
SELECT is(
    (
        SELECT count(*)::int FROM governance.fn_get_available_licenses_for_company(
            2091000000000000000::bigint,
            2091000000000000001::bigint
        )
    ),
    0,
    'license no longer available after company creation'
);

-- Test 5: List user companies
SELECT ok(
    (
        SELECT count(*) >= 1 FROM governance.fn_list_user_companies(
            2091000000000000000::bigint,
            2091000000000000001::bigint
        )
    ),
    'list_user_companies returns created company'
);

-- Clean up
DELETE FROM governance.companies WHERE guild_id = 2091000000000000000;
DELETE FROM governance.business_licenses WHERE guild_id = 2091000000000000000;

SELECT finish();
ROLLBACK;
