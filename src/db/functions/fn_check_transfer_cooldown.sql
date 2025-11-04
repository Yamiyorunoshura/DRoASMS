-- Check if initiator is on cooldown
CREATE OR REPLACE FUNCTION economy.fn_check_transfer_cooldown(p_transfer_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_guild_id bigint;
    v_initiator_id bigint;
    v_throttled_until timestamptz;
    v_now timestamptz := timezone('utc', now());
    v_check_result int;
    v_is_government boolean := false;
BEGIN
    SELECT guild_id, initiator_id
    INTO v_guild_id, v_initiator_id
    FROM economy.pending_transfers
    WHERE transfer_id = p_transfer_id;

    IF NOT FOUND THEN
        RETURN;
    END IF;

    -- Check if initiator is a government account
    SELECT EXISTS (
        SELECT 1
        FROM governance.government_accounts ga
        WHERE ga.account_id = v_initiator_id AND ga.guild_id = v_guild_id
    )
    INTO v_is_government;

    -- Exempt government accounts from cooldown
    IF v_is_government THEN
        v_check_result := 1;
    ELSE
        -- Get throttled_until
        SELECT throttled_until
        INTO v_throttled_until
        FROM economy.guild_member_balances
        WHERE guild_id = v_guild_id AND member_id = v_initiator_id;

        -- Set check result: 1 if not throttled or expired, 0 if still throttled
        v_check_result := CASE
            WHEN v_throttled_until IS NULL THEN 1
            WHEN v_throttled_until <= v_now THEN 1
            ELSE 0
        END;
    END IF;

    -- Update checks JSONB
    UPDATE economy.pending_transfers
    SET checks = jsonb_set(
        coalesce(checks, '{}'::jsonb),
        '{cooldown}',
        to_jsonb(v_check_result)
    ),
    updated_at = timezone('utc', now())
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
            'cooldown',
            'result',
            v_check_result,
            'guild_id',
            v_guild_id,
            'initiator_id',
            v_initiator_id,
            'throttled_until',
            v_throttled_until
        )::text
    );

    -- Check if all checks are complete and passed
    PERFORM economy._check_and_approve_transfer(p_transfer_id);
END;
$$;
