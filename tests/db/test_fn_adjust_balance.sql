\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);

SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_schema('economy', 'economy schema exists');

SELECT has_function(
    'economy',
    'fn_adjust_balance',
    ARRAY['bigint','bigint','bigint','bigint','text','jsonb'],
    'fn_adjust_balance exists with expected signature'
);

-- Grant increases balance and records transaction
WITH ids AS (
    SELECT 9100000000000000000::bigint AS guild_id,
           9100000000000000001::bigint AS admin_id,
           9100000000000000002::bigint AS member_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, member_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

WITH ids AS (
    SELECT 9100000000000000000::bigint AS guild_id,
           9100000000000000001::bigint AS admin_id,
           9100000000000000002::bigint AS member_id
),
outcome AS (
    SELECT economy.fn_adjust_balance(
        guild_id,
        admin_id,
        member_id,
        150,
        'Event bonus',
        '{}'::jsonb
    ) AS result
    FROM ids
)
SELECT ok(
    (SELECT (result).target_balance_after = 150 FROM outcome),
    'grant sets target balance correctly'
);

SELECT ok(
    EXISTS (
        SELECT 1
        FROM currency_transactions
        WHERE guild_id = 9100000000000000000
          AND initiator_id = 9100000000000000001
          AND target_id = 9100000000000000002
          AND amount = 150
          AND direction = 'adjustment_grant'
    ),
    'grant is recorded in transactions with adjustment_grant direction'
);

-- Deduct cannot drop below zero
WITH ids AS (
    SELECT 9200000000000000000::bigint AS guild_id,
           9200000000000000001::bigint AS admin_id,
           9200000000000000002::bigint AS member_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, member_id, 40 FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

SELECT throws_like(
    $$ SELECT economy.fn_adjust_balance(
        9200000000000000000,
        9200000000000000001,
        9200000000000000002,
        -100,
        'Penalty',
        '{}'::jsonb
    ) $$,
    '%cannot drop below zero%',
    'deduct that would go negative raises application error'
);

-- Deduct within balance should succeed and record adjustment_deduct
WITH ids AS (
    SELECT 8300000000000000000::bigint AS guild_id,
           8300000000000000001::bigint AS admin_id,
           8300000000000000002::bigint AS member_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, member_id, 200 FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE SET current_balance = EXCLUDED.current_balance;

SELECT ok(
    (
        SELECT (economy.fn_adjust_balance(
            8300000000000000000,
            8300000000000000001,
            8300000000000000002,
            -50,
            'Correction',
            '{}'::jsonb
        )).target_balance_after = 150
    ),
    'deduct within available balance succeeds'
);

SELECT ok(
    EXISTS (
        SELECT 1
        FROM currency_transactions
        WHERE guild_id = 8300000000000000000
          AND initiator_id = 8300000000000000001
          AND target_id = 8300000000000000002
          AND amount = 50
          AND direction = 'adjustment_deduct'
    ),
    'deduct is recorded in transactions with adjustment_deduct direction'
);

SELECT finish();
ROLLBACK;
