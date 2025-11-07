-- Check if initiator has sufficient balance
CREATE OR REPLACE FUNCTION economy.fn_check_transfer_balance(p_transfer_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_guild_id bigint;
    v_initiator_id bigint;
    v_amount bigint;
    v_balance bigint;
    v_check_result int;
BEGIN
    SELECT guild_id, initiator_id, amount
    INTO v_guild_id, v_initiator_id, v_amount
    FROM economy.pending_transfers
    WHERE transfer_id = p_transfer_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Ensure ledger row exists
    INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance, last_modified_at, created_at)
    VALUES (v_guild_id, v_initiator_id, 0, timezone('utc', clock_timestamp()), timezone('utc', clock_timestamp()))
    ON CONFLICT (guild_id, member_id) DO NOTHING;

    -- Get current balance
    SELECT current_balance
    INTO v_balance
    FROM economy.guild_member_balances
    WHERE guild_id = v_guild_id AND member_id = v_initiator_id;

    -- Set check result: 1 if sufficient, 0 if insufficient
    v_check_result := CASE WHEN v_balance >= v_amount THEN 1 ELSE 0 END;

    -- Update checks JSONB
    UPDATE economy.pending_transfers
    SET checks = jsonb_set(
        coalesce(checks, '{}'::jsonb),
        '{balance}',
        to_jsonb(v_check_result)
    ),
    updated_at = timezone('utc', clock_timestamp())
    WHERE transfer_id = p_transfer_id;

    -- Send NOTIFY event
    PERFORM pg_notify(
        'economy_events',
        jsonb_build_object(
            'event_type',
            'transfer_check_result',
            'transfer_id',
            p_transfer_id,
            'check_type',
            'balance',
            'result',
            v_check_result,
            'guild_id',
            v_guild_id,
            'initiator_id',
            v_initiator_id,
            'balance',
            v_balance,
            'required',
            v_amount
        )::text
    );

    -- Check if all checks are complete and passed
    PERFORM economy._check_and_approve_transfer(p_transfer_id);
END;
$$;
