\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(13);
SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_get_history',
    ARRAY['bigint', 'bigint', 'integer', 'timestamptz'],
    'fn_get_history exists with expected signature'
);

-- Setup test data
WITH ids AS (
    SELECT 9100000000000000000::bigint AS guild_id,
           9100000000000000001::bigint AS member_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, member_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO NOTHING;

INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
VALUES (9100000000000000000, 9100000000000000002, 0)
ON CONFLICT (guild_id, member_id) DO NOTHING;

-- Insert multiple transactions for pagination testing
INSERT INTO currency_transactions (
    guild_id, initiator_id, target_id, amount, direction, reason,
    balance_after_initiator, balance_after_target, created_at
)
VALUES
    (9100000000000000000, 9100000000000000001, 9100000000000000002, 100, 'transfer', 'T1', 900, 100, timestamptz '2025-01-01 10:00:00+00'),
    (9100000000000000000, 9100000000000000001, 9100000000000000002, 200, 'transfer', 'T2', 700, 300, timestamptz '2025-01-01 11:00:00+00'),
    (9100000000000000000, 9100000000000000001, 9100000000000000002, 300, 'transfer', 'T3', 400, 600, timestamptz '2025-01-01 12:00:00+00'),
    (9100000000000000000, 9100000000000000002, 9100000000000000001, 50, 'transfer', 'T4', 250, 450, timestamptz '2025-01-01 13:00:00+00'),
    (9100000000000000000, 9100000000000000001, 9100000000000000002, 400, 'transfer', 'T5', 50, 850, timestamptz '2025-01-01 14:00:00+00');

-- Test: Default limit (10) returns all records
SELECT is(
    (SELECT count(*) FROM economy.fn_get_history(9100000000000000000, 9100000000000000001, 10, NULL)),
    5::bigint,
    'default limit returns all matching records'
);

-- Test: Limit works correctly
SELECT is(
    (SELECT count(*) FROM economy.fn_get_history(9100000000000000000, 9100000000000000001, 2, NULL)),
    2::bigint,
    'limit parameter restricts result count'
);

-- Test: Cursor pagination - get records before cursor
SELECT is(
    (SELECT count(*) FROM economy.fn_get_history(
        9100000000000000000,
        9100000000000000001,
        10,
        timestamptz '2025-01-01 12:00:00+00'
    )),
    2::bigint,
    'cursor excludes records at or after cursor timestamp'
);

-- Test: Cursor with limit
SELECT is(
    (SELECT count(*) FROM economy.fn_get_history(
        9100000000000000000,
        9100000000000000001,
        1,
        timestamptz '2025-01-01 12:00:00+00'
    )),
    1::bigint,
    'cursor and limit work together'
);

-- Test: Ordering - newest first
SELECT is(
    (
        SELECT (entry).reason
        FROM (
            SELECT economy.fn_get_history(9100000000000000000, 9100000000000000001, 1, NULL) AS entry
        ) latest
    ),
    'T5',
    'results ordered by created_at DESC (newest first)'
);

-- Test: Boundary - limit = 1
SELECT is(
    (SELECT count(*) FROM economy.fn_get_history(9100000000000000000, 9100000000000000001, 1, NULL)),
    1::bigint,
    'limit = 1 returns single record'
);

-- Test: Boundary - limit = 50 (max allowed)
SELECT ok(
    (SELECT count(*) FROM economy.fn_get_history(9100000000000000000, 9100000000000000001, 50, NULL)) <= 50,
    'limit = 50 (max) works correctly'
);

-- Test: Error - limit = NULL
SELECT throws_like(
    $$ SELECT economy.fn_get_history(9100000000000000000, 9100000000000000001, NULL, NULL) $$,
    '%History limit cannot be null%',
    'NULL limit raises exception'
);

-- Test: Error - limit < 1
SELECT throws_like(
    $$ SELECT economy.fn_get_history(9100000000000000000, 9100000000000000001, 0, NULL) $$,
    '%History limit must be between 1 and 50%',
    'limit < 1 raises exception'
);

-- Test: Error - limit > 50
SELECT throws_like(
    $$ SELECT economy.fn_get_history(9100000000000000000, 9100000000000000001, 51, NULL) $$,
    '%History limit must be between 1 and 50%',
    'limit > 50 raises exception'
);

-- Test: Empty result when no matching transactions
SELECT is(
    (SELECT count(*) FROM economy.fn_get_history(8999999999999999999, 8999999999999999999, 10, NULL)),
    0::bigint,
    'returns empty result for non-existent guild/member'
);

-- Test: Member appears as initiator or target
SELECT is(
    (SELECT count(*) FROM economy.fn_get_history(9100000000000000000, 9100000000000000002, 10, NULL)),
    5::bigint,
    'includes transactions where member is initiator or target'
);

SELECT finish();
ROLLBACK;
