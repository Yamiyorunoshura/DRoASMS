\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(9);

SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_get_balance',
    ARRAY['bigint', 'bigint'],
    'fn_get_balance exists with expected signature'
);

SELECT has_function(
    'economy',
    'fn_get_history',
    ARRAY['bigint', 'bigint', 'integer', 'timestamptz'],
    'fn_get_history exists with expected signature'
);

WITH snapshot AS (
    SELECT economy.fn_get_balance(8300000000000000000, 8300000000000000001) AS result
)
SELECT is(
    (SELECT (result).balance FROM snapshot),
    0::bigint,
    'missing ledger row initialises with zero balance'
);

SELECT ok(
    EXISTS (
        SELECT 1
        FROM guild_member_balances
        WHERE guild_id = 8300000000000000000
          AND member_id = 8300000000000000001
    ),
    'fn_get_balance upserts guild_member_balances row'
);

INSERT INTO guild_member_balances (guild_id, member_id, current_balance, last_modified_at, created_at)
VALUES (
    8300000000000000000,
    8300000000000000002,
    875,
    timestamptz '2025-10-21 12:30:00+00',
    timestamptz '2025-10-20 12:30:00+00'
)
ON CONFLICT (guild_id, member_id) DO UPDATE
SET current_balance = EXCLUDED.current_balance,
    last_modified_at = EXCLUDED.last_modified_at;

WITH snapshot AS (
    SELECT economy.fn_get_balance(8300000000000000000, 8300000000000000002) AS result
)
SELECT is(
    (SELECT (result).balance FROM snapshot),
    875::bigint,
    'fn_get_balance returns current balance'
);

INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
VALUES
    (8300000000000000000, 8300000000000000003, 0),
    (8300000000000000000, 8300000000000000004, 0),
    (8300000000000000000, 8300000000000000005, 0)
ON CONFLICT (guild_id, member_id) DO NOTHING;

INSERT INTO currency_transactions (
    guild_id,
    initiator_id,
    target_id,
    amount,
    direction,
    reason,
    balance_after_initiator,
    balance_after_target,
    metadata,
    created_at
)
VALUES
    (
        8300000000000000000,
        8300000000000000002,
        8300000000000000003,
        120,
        'transfer',
        'Gift',
        755,
        320,
        '{}'::jsonb,
        timestamptz '2025-10-22 10:00:00+00'
    ),
    (
        8300000000000000000,
        8300000000000000004,
        8300000000000000002,
        90,
        'transfer',
        'Refund',
        400,
        445,
        '{}'::jsonb,
        timestamptz '2025-10-22 09:00:00+00'
    ),
    (
        8300000000000000000,
        8300000000000000002,
        8300000000000000005,
        75,
        'transfer',
        NULL,
        680,
        215,
        '{}'::jsonb,
        timestamptz '2025-10-22 08:00:00+00'
    );

WITH history AS (
    SELECT economy.fn_get_history(8300000000000000000, 8300000000000000002, 2, NULL) AS entry
)
SELECT is(
    (SELECT count(*) FROM history),
    2::bigint,
    'history applies limit argument'
);

SELECT is(
    (
        SELECT max((entry).created_at)
        FROM (
        SELECT economy.fn_get_history(8300000000000000000, 8300000000000000002, 2, NULL) AS entry
        ) h
    ),
    timestamptz '2025-10-22 10:00:00+00',
    'history returns newest record first'
);

SELECT is(
    (
        SELECT count(*)
        FROM economy.fn_get_history(
            8300000000000000000,
            8300000000000000002,
            5,
            timestamptz '2025-10-22 09:00:00+00'
        )
    ),
    1::bigint,
    'cursor omits records at or after supplied timestamp'
);

SELECT is(
    (
        SELECT (entry).reason
        FROM (
            SELECT economy.fn_get_history(8300000000000000000, 8300000000000000002, 1, NULL) AS entry
        ) latest
    ),
    'Gift',
    'history exposes transaction reason text'
);

SELECT finish();
ROLLBACK;
