\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(7);
SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_has_more_history',
    ARRAY['bigint', 'bigint', 'timestamptz'],
    'fn_has_more_history exists with expected signature'
);

-- Setup test data
WITH ids AS (
    SELECT 9200000000000000000::bigint AS guild_id,
           9200000000000000001::bigint AS member_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
SELECT guild_id, member_id, 0 FROM ids
ON CONFLICT (guild_id, member_id) DO NOTHING;

INSERT INTO guild_member_balances (guild_id, member_id, current_balance)
VALUES (9200000000000000000, 9200000000000000002, 0)
ON CONFLICT (guild_id, member_id) DO NOTHING;

-- Insert transactions at different timestamps
INSERT INTO currency_transactions (
    guild_id, initiator_id, target_id, amount, direction, reason,
    balance_after_initiator, balance_after_target, created_at
)
VALUES
    (9200000000000000000, 9200000000000000001, 9200000000000000002, 100, 'transfer', 'T1', 900, 100, timestamptz '2025-01-01 10:00:00+00'),
    (9200000000000000000, 9200000000000000001, 9200000000000000002, 200, 'transfer', 'T2', 700, 300, timestamptz '2025-01-01 11:00:00+00'),
    (9200000000000000000, 9200000000000000001, 9200000000000000002, 300, 'transfer', 'T3', 400, 600, timestamptz '2025-01-01 12:00:00+00');

-- Test: Returns true when more history exists before cursor
SELECT ok(
    economy.fn_has_more_history(
        9200000000000000000,
        9200000000000000001,
        timestamptz '2025-01-01 12:00:00+00'
    ),
    'returns true when more history exists before cursor'
);

-- Test: Returns false when no more history exists
SELECT ok(
    NOT economy.fn_has_more_history(
        9200000000000000000,
        9200000000000000001,
        timestamptz '2025-01-01 09:00:00+00'
    ),
    'returns false when no more history exists before cursor'
);

-- Test: Returns false when cursor is at oldest record
SELECT ok(
    NOT economy.fn_has_more_history(
        9200000000000000000,
        9200000000000000001,
        timestamptz '2025-01-01 10:00:00+00'
    ),
    'returns false when cursor is at oldest record'
);

-- Test: Returns false for non-existent guild/member
SELECT ok(
    NOT economy.fn_has_more_history(
        8999999999999999999,
        8999999999999999999,
        timestamptz '2025-01-01 12:00:00+00'
    ),
    'returns false for non-existent guild/member'
);

-- Test: Member appears as initiator or target
INSERT INTO currency_transactions (
    guild_id, initiator_id, target_id, amount, direction, reason,
    balance_after_initiator, balance_after_target, created_at
)
VALUES
    (9200000000000000000, 9200000000000000002, 9200000000000000001, 50, 'transfer', 'T4', 250, 450, timestamptz '2025-01-01 09:00:00+00');

SELECT ok(
    economy.fn_has_more_history(
        9200000000000000000,
        9200000000000000001,
        timestamptz '2025-01-01 12:00:00+00'
    ),
    'includes transactions where member is initiator or target'
);

-- Test: Edge case - cursor at exact timestamp boundary
SELECT ok(
    economy.fn_has_more_history(
        9200000000000000000,
        9200000000000000001,
        timestamptz '2025-01-01 11:00:00+00'
    ),
    'cursor at exact timestamp boundary works correctly'
);

SELECT finish();
ROLLBACK;
