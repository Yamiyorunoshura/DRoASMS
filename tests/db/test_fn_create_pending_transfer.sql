-- Test fn_create_pending_transfer
BEGIN;

-- Test 1: Create a valid pending transfer
SELECT economy.fn_create_pending_transfer(
    123456789::bigint,  -- guild_id
    111111111::bigint,  -- initiator_id
    222222222::bigint,  -- target_id
    100::bigint,        -- amount
    '{"reason": "test"}'::jsonb,  -- metadata
    NULL::timestamptz   -- expires_at
) AS transfer_id_1;

-- Verify the record was created
SELECT
    transfer_id,
    guild_id,
    initiator_id,
    target_id,
    amount,
    status,
    checks,
    retry_count,
    expires_at,
    metadata->>'reason' AS reason
FROM economy.pending_transfers
WHERE initiator_id = 111111111;

-- Test 2: Create with expires_at
SELECT economy.fn_create_pending_transfer(
    123456789::bigint,
    333333333::bigint,
    444444444::bigint,
    50::bigint,
    '{}'::jsonb,
    (timezone('utc', now()) + interval '1 hour')::timestamptz
) AS transfer_id_2;

-- Test 3: Invalid - same initiator and target (should raise error)
DO $$
DECLARE
    v_error_occurred boolean := false;
BEGIN
    BEGIN
        PERFORM economy.fn_create_pending_transfer(
            123456789::bigint,
            555555555::bigint,
            555555555::bigint,  -- Same as initiator
            100::bigint,
            '{}'::jsonb,
            NULL::timestamptz
        );
        RAISE EXCEPTION 'Expected error for same initiator and target, but function succeeded';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%Initiator and target must be distinct%' THEN
                v_error_occurred := true;
            ELSE
                RAISE;
            END IF;
    END;

    IF NOT v_error_occurred THEN
        RAISE EXCEPTION 'Expected error was not raised';
    END IF;
END $$;

-- Test 4: Invalid - zero amount (should raise error)
DO $$
DECLARE
    v_error_occurred boolean := false;
BEGIN
    BEGIN
        PERFORM economy.fn_create_pending_transfer(
            123456789::bigint,
            666666666::bigint,
            777777777::bigint,
            0::bigint,  -- Invalid amount
            '{}'::jsonb,
            NULL::timestamptz
        );
        RAISE EXCEPTION 'Expected error for zero amount, but function succeeded';
    EXCEPTION
        WHEN OTHERS THEN
            IF SQLERRM LIKE '%Transfer amount must be a positive whole number%' THEN
                v_error_occurred := true;
            ELSE
                RAISE;
            END IF;
    END;

    IF NOT v_error_occurred THEN
        RAISE EXCEPTION 'Expected error was not raised';
    END IF;
END $$;

ROLLBACK;
