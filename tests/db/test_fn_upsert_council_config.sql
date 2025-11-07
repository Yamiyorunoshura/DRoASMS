\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_upsert_council_config',
    ARRAY['bigint', 'bigint', 'bigint'],
    'fn_upsert_council_config exists with expected signature'
);

-- Test 1: Insert new config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_council_config(
        1000000000000000000::bigint,
        1000000000000000001::bigint,
        1000000000000000002::bigint
    )

;

SELECT is(
    (SELECT council_role_id FROM result),
    1000000000000000001::bigint,
    'inserts new council config'
);

SELECT is(
    (SELECT council_account_member_id FROM result),
    1000000000000000002::bigint,
    'returns correct council_account_member_id'
);

-- Test 2: Update existing config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_council_config(
        1000000000000000000::bigint,
        1000000000000000003::bigint,
        1000000000000000004::bigint
    )

;

SELECT is(
    (SELECT council_role_id FROM result),
    1000000000000000003::bigint,
    'updates existing council config'
);

SELECT is(
    (SELECT council_account_member_id FROM result),
    1000000000000000004::bigint,
    'updates council_account_member_id'
);

DROP TABLE IF EXISTS council_prev;
CREATE TEMP TABLE council_prev AS
SELECT updated_at FROM governance.council_config
WHERE guild_id = 1000000000000000000;

SELECT governance.fn_upsert_council_config(
    1000000000000000000::bigint,
    1000000000000000003::bigint,
    1000000000000000004::bigint
);

SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM council_prev)
        FROM governance.council_config
        WHERE guild_id = 1000000000000000000
    ),
    'updated_at is updated on upsert'
);

DROP TABLE council_prev;

-- Test 4: Created_at is preserved on update
WITH old_created_at AS (
    SELECT created_at FROM governance.council_config
    WHERE guild_id = 1000000000000000000
)
SELECT governance.fn_upsert_council_config(
    1000000000000000000::bigint,
    1000000000000000005::bigint,
    1000000000000000006::bigint
);

SELECT ok(
    (
        SELECT created_at = (
            SELECT created_at FROM governance.council_config
            WHERE guild_id = 1000000000000000000
        )
        FROM governance.council_config
        WHERE guild_id = 1000000000000000000
    ),
    'created_at is preserved on update'
);

SELECT finish();
ROLLBACK;
