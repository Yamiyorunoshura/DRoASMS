\set ON_ERROR_STOP 1

BEGIN;

SELECT plan(9);
SELECT set_config('search_path', 'pgtap, economy, public', false);

SELECT has_function(
    'economy',
    'fn_record_throttle',
    ARRAY['bigint', 'bigint', 'jsonb'],
    'fn_record_throttle exists with expected signature'
);

-- Test: Creates throttled_until timestamp (5 minutes from now)
WITH ids AS (
    SELECT 8300000000000000000::bigint AS guild_id,
           8300000000000000001::bigint AS member_id
)
SELECT economy.fn_record_throttle(guild_id, member_id, '{}'::jsonb) AS throttled_until
INTO TEMP TABLE throttle_result
FROM ids;

SELECT ok(
    (SELECT throttled_until FROM throttle_result) > timezone('utc', now()),
    'returns throttled_until timestamp in the future'
);

SELECT ok(
    (SELECT throttled_until FROM throttle_result) <= timezone('utc', now()) + interval '310 seconds',
    'throttled_until is approximately 5 minutes from now'
);

DROP TABLE throttle_result;

-- Test: Updates existing balance record with throttled_until
WITH ids AS (
    SELECT 8300000000000000000::bigint AS guild_id,
           8300000000000000001::bigint AS member_id
)
INSERT INTO guild_member_balances (guild_id, member_id, current_balance, throttled_until)
SELECT guild_id, member_id, 1000, NULL FROM ids
ON CONFLICT (guild_id, member_id) DO UPDATE
    SET current_balance = EXCLUDED.current_balance,
        throttled_until = EXCLUDED.throttled_until;

SELECT ok(
    (SELECT throttled_until FROM guild_member_balances WHERE guild_id = 8300000000000000000 AND member_id = 8300000000000000001) IS NULL,
    'throttled_until is NULL before throttle'
);

SELECT economy.fn_record_throttle(8300000000000000000, 8300000000000000001, '{}'::jsonb);

SELECT ok(
    (SELECT throttled_until FROM guild_member_balances WHERE guild_id = 8300000000000000000 AND member_id = 8300000000000000001) IS NOT NULL,
    'throttled_until is set after throttle'
);

-- Test: Creates throttle_block transaction record
SELECT ok(
    EXISTS (
        SELECT 1
        FROM currency_transactions
        WHERE guild_id = 8300000000000000000
          AND initiator_id = 8300000000000000001
          AND direction = 'throttle_block'
          AND amount = 0
    ),
    'creates throttle_block transaction record'
);

-- Test: Metadata is included in transaction
SELECT ok(
    EXISTS (
        SELECT 1
        FROM currency_transactions
        WHERE guild_id = 8300000000000000000
          AND initiator_id = 8300000000000000001
          AND direction = 'throttle_block'
          AND metadata ? 'throttle_until'
          AND metadata ? 'triggered_at'
    ),
    'transaction metadata includes throttle_until and triggered_at'
);

-- Test: Custom metadata is merged
WITH ids AS (
    SELECT 8300000000000000000::bigint AS guild_id,
           8300000000000000002::bigint AS member_id
)
SELECT economy.fn_record_throttle(
    guild_id,
    member_id,
    '{"custom_key": "custom_value"}'::jsonb
)
FROM ids;

SELECT ok(
    EXISTS (
        SELECT 1
        FROM currency_transactions
        WHERE guild_id = 8300000000000000000
          AND initiator_id = 8300000000000000002
          AND direction = 'throttle_block'
          AND metadata->>'custom_key' = 'custom_value'
    ),
    'custom metadata is merged into transaction metadata'
);

-- Test: Creates new balance record if doesn't exist
SELECT economy.fn_record_throttle(8300000000000000000, 8300000000000000003, '{}'::jsonb);

SELECT ok(
    EXISTS (
        SELECT 1
        FROM guild_member_balances
        WHERE guild_id = 8300000000000000000
          AND member_id = 8300000000000000003
          AND current_balance = 0
    ),
    'creates new balance record with zero balance if not exists'
);

SELECT finish();
ROLLBACK;
