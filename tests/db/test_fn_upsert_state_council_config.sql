\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, governance, public', false);

SELECT has_function(
    'governance',
    'fn_upsert_state_council_config',
    ARRAY['bigint', 'bigint', 'bigint', 'bigint', 'bigint', 'bigint', 'bigint'],
    'fn_upsert_state_council_config exists with expected signature'
);

-- Test 1: Insert new config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_state_council_config(
        2000000000000000000::bigint,
        2000000000000000001::bigint,
        2000000000000000002::bigint,
        2000000000000000003::bigint,
        2000000000000000004::bigint,
        2000000000000000005::bigint,
        2000000000000000006::bigint
    )

;

SELECT is(
    (SELECT leader_id FROM result),
    2000000000000000001::bigint,
    'inserts new state council config'
);

SELECT is(
    (SELECT central_bank_account_id FROM result),
    2000000000000000006::bigint,
    'returns correct central_bank_account_id'
);

-- Test 2: Update existing config
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_state_council_config(
        2000000000000000000::bigint,
        2000000000000000007::bigint,
        2000000000000000008::bigint,
        2000000000000000009::bigint,
        2000000000000000010::bigint,
        2000000000000000011::bigint,
        2000000000000000012::bigint
    )

;

SELECT is(
    (SELECT leader_id FROM result),
    2000000000000000007::bigint,
    'updates existing state council config'
);

DROP TABLE IF EXISTS state_council_prev;
CREATE TEMP TABLE state_council_prev AS
SELECT updated_at FROM governance.state_council_config
WHERE guild_id = 2000000000000000000;

SELECT governance.fn_upsert_state_council_config(
    2000000000000000000::bigint,
    2000000000000000007::bigint,
    2000000000000000008::bigint,
    2000000000000000009::bigint,
    2000000000000000010::bigint,
    2000000000000000011::bigint,
    2000000000000000012::bigint
);

SELECT ok(
    (
        SELECT updated_at > (SELECT updated_at FROM state_council_prev)
        FROM governance.state_council_config
        WHERE guild_id = 2000000000000000000
    ),
    'updated_at is updated on upsert'
);

DROP TABLE state_council_prev;

-- Test 4: Created_at is preserved on update
WITH old_created_at AS (
    SELECT created_at FROM governance.state_council_config
    WHERE guild_id = 2000000000000000000
)
SELECT governance.fn_upsert_state_council_config(
    2000000000000000000::bigint,
    2000000000000000013::bigint,
    2000000000000000014::bigint,
    2000000000000000015::bigint,
    2000000000000000016::bigint,
    2000000000000000017::bigint,
    2000000000000000018::bigint
);

SELECT ok(
    (
        SELECT created_at = (
            SELECT created_at FROM governance.state_council_config
            WHERE guild_id = 2000000000000000000
        )
        FROM governance.state_council_config
        WHERE guild_id = 2000000000000000000
    ),
    'created_at is preserved on update'
);

-- Test 5: All account IDs are stored correctly
DROP TABLE IF EXISTS result;
CREATE TEMP TABLE result AS
    SELECT * FROM governance.fn_upsert_state_council_config(
        2000000000000000001::bigint,
        2000000000000000020::bigint,
        2000000000000000021::bigint,
        2000000000000000022::bigint,
        2000000000000000023::bigint,
        2000000000000000024::bigint,
        2000000000000000025::bigint
    )

;

SELECT ok(
    (SELECT internal_affairs_account_id = 2000000000000000022::bigint FROM result) AND
    (SELECT finance_account_id = 2000000000000000023::bigint FROM result) AND
    (SELECT security_account_id = 2000000000000000024::bigint FROM result) AND
    (SELECT central_bank_account_id = 2000000000000000025::bigint FROM result),
    'all account IDs are stored correctly'
);

SELECT finish();
ROLLBACK;
