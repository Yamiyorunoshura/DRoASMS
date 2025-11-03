\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(10);

SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_schema('economy', 'economy schema exists');

SELECT has_function(
    'economy',
    'fn_transfer_currency',
    ARRAY['bigint', 'bigint', 'bigint', 'bigint', 'jsonb'],
    'fn_transfer_currency exists with expected signature'
);

SELECT has_function(
    'economy',
    'fn_record_throttle',
    ARRAY['bigint', 'bigint', 'jsonb'],
    'fn_record_throttle exists with expected signature'
);

-- isolate identifiers for this test run
WITH ids AS (
    SELECT
        8400000000000000000::bigint AS guild_id,
        8500000000000000000::bigint AS initiator_id,
        8600000000000000000::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 600
FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE
SET current_balance = EXCLUDED.current_balance,
    throttled_until = NULL,
    last_modified_at = now();

WITH ids AS (
    SELECT
        8400000000000000000::bigint AS guild_id,
        8500000000000000000::bigint AS initiator_id,
        8600000000000000000::bigint AS target_id
),
result AS (
    SELECT economy.fn_transfer_currency(
        guild_id,
        initiator_id,
        target_id,
        200,
        jsonb_build_object('reason', 'Test transfer')
    ) AS outcome
    FROM ids
)
SELECT ok(
    (SELECT (outcome).initiator_balance = 400 AND (outcome).target_balance = 200 FROM result),
    'transfer reduces initiator balance and credits target'
);

SELECT ok(
    EXISTS (
        SELECT 1
        FROM currency_transactions
        WHERE guild_id = 8400000000000000000
          AND initiator_id = 8500000000000000000
          AND target_id = 8600000000000000000
          AND amount = 200
          AND direction = 'transfer'
    ),
    'transfer records transaction'
);

WITH insufficient AS (
    SELECT
        8450000000000000000::bigint AS guild_id,
        8550000000000000000::bigint AS initiator_id,
        8650000000000000000::bigint AS target_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, initiator_id, 75 FROM insufficient
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

SELECT throws_like(
    $$ SELECT economy.fn_transfer_currency(
        8450000000000000000,
        8550000000000000000,
        8650000000000000000,
        200,
        '{}'::jsonb
    ) $$,
    '%insufficient%',
    'insufficient funds raise application error'
);

SELECT throws_like(
    $$ SELECT economy.fn_transfer_currency(
        8400000000000000000,
        8500000000000000000,
        8500000000000000000,
        10,
        '{}'::jsonb
    ) $$,
    '%distinct%',
    'self transfer rejected'
);

-- exceed the daily limit (explicitly set via GUC to 500)
SELECT set_config('app.transfer_daily_limit', '500', false);
SELECT ok(
    (
        SELECT (economy.fn_transfer_currency(
            8400000000000000000,
            8500000000000000000,
            8800000000000000000,
            300,
            '{}'::jsonb
        )).amount
    ) = 300,
    'daily limit setup transfer succeeds'
);

SELECT throws_like(
    $$ SELECT economy.fn_transfer_currency(
        8400000000000000000,
        8500000000000000000,
        8800000000000000000,
        250,
        '{}'::jsonb
    ) $$,
    '%throttled%',
    'daily cap triggers throttle error'
);

SELECT ok(
    economy.fn_record_throttle(
        8900000000000000000,
        8950000000000000000,
        '{}'::jsonb
    ) IS NOT NULL,
    'throttle utility returns throttled_until timestamp'
);

SELECT finish();
ROLLBACK;
