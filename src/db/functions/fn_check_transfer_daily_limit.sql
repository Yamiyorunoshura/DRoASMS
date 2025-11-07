-- Check if initiator has exceeded daily transfer limit
CREATE OR REPLACE FUNCTION economy.fn_check_transfer_daily_limit(p_transfer_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_guild_id bigint;
    v_initiator_id bigint;
    v_amount bigint;
    v_total_today bigint;
    -- 讀取應用層連線 GUC；未設定或 <= 0 視為「無上限」
    v_daily_limit_text text := current_setting('app.transfer_daily_limit', true);
    v_daily_limit bigint;
    v_check_result int;
    v_now timestamptz := timezone('utc', clock_timestamp());
    v_is_government boolean := false;
BEGIN
    SELECT guild_id, initiator_id, amount
    INTO v_guild_id, v_initiator_id, v_amount
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

    -- Exempt government accounts from daily limit
    IF v_is_government THEN
        v_check_result := 1;
    ELSE
        -- 若未提供 GUC 或提供空字串／非正數，則視為「無上限」直接通過
        IF v_daily_limit_text IS NULL OR NULLIF(v_daily_limit_text, '') IS NULL THEN
            v_check_result := 1;
        ELSE
            v_daily_limit := v_daily_limit_text::bigint;
            IF v_daily_limit <= 0 THEN
                v_check_result := 1;
            ELSE
                -- Calculate total transfers today
                SELECT coalesce(SUM(amount), 0)
                INTO v_total_today
                FROM economy.currency_transactions
                WHERE guild_id = v_guild_id
                  AND initiator_id = v_initiator_id
                  AND direction = 'transfer'
                  AND created_at >= date_trunc('day', v_now);

                -- Set check result: 1 if within limit, 0 if exceeded
                v_check_result := CASE
                    WHEN v_total_today + v_amount <= v_daily_limit THEN 1
                    ELSE 0
                END;
            END IF;
        END IF;
    END IF;

    -- Update checks JSONB
    UPDATE economy.pending_transfers
    SET checks = jsonb_set(
        coalesce(checks, '{}'::jsonb),
        '{daily_limit}',
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
            'daily_limit',
            'result',
            v_check_result,
            'guild_id',
            v_guild_id,
            'initiator_id',
            v_initiator_id,
            'total_today',
            v_total_today,
            'attempted_amount',
            v_amount,
            'limit',
            v_daily_limit
        )::text
    );

    -- Check if all checks are complete and passed
    PERFORM economy._check_and_approve_transfer(p_transfer_id);
END;
$$;
