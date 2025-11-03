-- Stored procedures implementing economy transfer logic and throttling.
CREATE OR REPLACE FUNCTION economy.fn_record_throttle(
    p_guild_id bigint,
    p_member_id bigint,
    p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS timestamptz
LANGUAGE plpgsql
AS $$
DECLARE
    v_now timestamptz := timezone('utc', now());
    v_until timestamptz := v_now + interval '300 seconds';
    v_metadata jsonb := coalesce(p_metadata, '{}'::jsonb);
    v_balance bigint;
BEGIN
    INSERT INTO economy.guild_member_balances (
        guild_id,
        member_id,
        current_balance,
        last_modified_at,
        throttled_until,
        created_at
    )
    VALUES (p_guild_id, p_member_id, 0, v_now, v_until, v_now)
    ON CONFLICT (guild_id, member_id)
    DO UPDATE
        SET throttled_until = v_until,
            last_modified_at = v_now
        RETURNING economy.guild_member_balances.current_balance
        INTO v_balance;

    INSERT INTO economy.currency_transactions (
        guild_id,
        initiator_id,
        target_id,
        amount,
        direction,
        reason,
        balance_after_initiator,
        balance_after_target,
        metadata
    )
    VALUES (
        p_guild_id,
        p_member_id,
        NULL,
        0,
        'throttle_block',
        'Transfer throttled',
        v_balance,
        NULL,
        jsonb_strip_nulls(
            coalesce(v_metadata, '{}'::jsonb)
            || jsonb_build_object(
                'throttle_until',
                v_until,
                'triggered_at',
                v_now
            )
        )
    );

    PERFORM pg_notify(
        'economy_events',
        jsonb_build_object(
            'event_type',
            'transaction_denied',
            'reason',
            'throttle_block',
            'guild_id',
            p_guild_id,
            'initiator_id',
            p_member_id,
            'metadata',
            jsonb_strip_nulls(
                coalesce(v_metadata, '{}'::jsonb)
                || jsonb_build_object(
                    'throttle_until',
                    v_until
                )
            )
        )::text
    );

    RETURN v_until;
END;
$$;

CREATE OR REPLACE FUNCTION economy.fn_transfer_currency(
    p_guild_id bigint,
    p_initiator_id bigint,
    p_target_id bigint,
    p_amount bigint,
    p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS economy.transfer_result
LANGUAGE plpgsql
AS $$
DECLARE
    v_now timestamptz := timezone('utc', now());
    v_metadata jsonb := coalesce(p_metadata, '{}'::jsonb);
    v_initiator_balance bigint;
    v_target_balance bigint;
    v_throttled_until timestamptz;
    v_total_today bigint;
    v_transaction_id uuid;
    v_created_at timestamptz;
    v_reason text := nullif(v_metadata->>'reason', '');
    -- 以連線層 GUC 控制每日上限；未設定或 <= 0 視為「無上限」
    v_daily_limit_text text := current_setting('app.transfer_daily_limit', true);
    v_daily_limit bigint;
    v_is_government boolean := false;
BEGIN
    IF p_initiator_id = p_target_id THEN
        RAISE EXCEPTION 'Initiator and target must be distinct members for transfers.'
            USING ERRCODE = '22023';
    END IF;

    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be a positive whole number.'
            USING ERRCODE = '22023';
    END IF;

    -- Ensure ledger rows exist
    INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance, last_modified_at, created_at)
    VALUES (p_guild_id, p_initiator_id, 0, v_now, v_now)
    ON CONFLICT (guild_id, member_id) DO NOTHING;

    INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance, last_modified_at, created_at)
    VALUES (p_guild_id, p_target_id, 0, v_now, v_now)
    ON CONFLICT (guild_id, member_id) DO NOTHING;

    -- 判斷是否為政府部門帳戶（免除每日上限與冷卻限制）
    SELECT EXISTS (
               SELECT 1
               FROM governance.government_accounts ga
               WHERE ga.account_id = p_initiator_id AND ga.guild_id = p_guild_id
           )
    INTO v_is_government;

    SELECT current_balance, throttled_until
    INTO v_initiator_balance, v_throttled_until
    FROM economy.guild_member_balances
    WHERE guild_id = p_guild_id AND member_id = p_initiator_id
    FOR UPDATE;

    -- 政府帳戶不受冷卻限制
    IF (NOT v_is_government) AND v_throttled_until IS NOT NULL AND v_throttled_until > v_now THEN
        RAISE EXCEPTION 'Transfer throttled: member is on cooldown until %.', v_throttled_until
            USING ERRCODE = 'P0001';
    END IF;

    -- 非政府帳戶才檢查每日上限；未設定 GUC 或 <= 0 則跳過檢查（視為無上限）
    IF NOT v_is_government THEN
        IF v_daily_limit_text IS NOT NULL AND NULLIF(v_daily_limit_text, '') IS NOT NULL THEN
            v_daily_limit := v_daily_limit_text::bigint;
            IF v_daily_limit > 0 THEN
                SELECT coalesce(SUM(amount), 0)
                INTO v_total_today
                FROM economy.currency_transactions
                WHERE guild_id = p_guild_id
                  AND initiator_id = p_initiator_id
                  AND direction = 'transfer'
                  AND created_at >= date_trunc('day', v_now);

                IF v_total_today + p_amount > v_daily_limit THEN
                    PERFORM economy.fn_record_throttle(
                        p_guild_id,
                        p_initiator_id,
                        jsonb_build_object(
                            'reason', 'daily_limit_exceeded',
                            'limit', v_daily_limit,
                            'attempted_amount', p_amount,
                            'total_today', v_total_today
                        )
                    );

                    RAISE EXCEPTION 'Transfer throttled: daily limit of % exceeded.', v_daily_limit
                        USING ERRCODE = 'P0001';
                END IF;
            END IF;
        END IF;
    END IF;

    IF v_initiator_balance < p_amount THEN
        RAISE EXCEPTION 'Transfer denied: insufficient funds. Balance available: %.', v_initiator_balance
            USING ERRCODE = 'P0001';
    END IF;

    UPDATE economy.guild_member_balances
    SET current_balance = current_balance - p_amount,
        last_modified_at = v_now,
        throttled_until = NULL
    WHERE guild_id = p_guild_id AND member_id = p_initiator_id
    RETURNING current_balance
    INTO v_initiator_balance;

    UPDATE economy.guild_member_balances
    SET current_balance = current_balance + p_amount,
        last_modified_at = v_now
    WHERE guild_id = p_guild_id AND member_id = p_target_id
    RETURNING current_balance
    INTO v_target_balance;

    INSERT INTO economy.currency_transactions (
        guild_id,
        initiator_id,
        target_id,
        amount,
        direction,
        reason,
        balance_after_initiator,
        balance_after_target,
        metadata
    )
    VALUES (
        p_guild_id,
        p_initiator_id,
        p_target_id,
        p_amount,
        'transfer',
        v_reason,
        v_initiator_balance,
        v_target_balance,
        jsonb_strip_nulls(v_metadata)
    )
    RETURNING transaction_id, created_at
    INTO v_transaction_id, v_created_at;

    PERFORM pg_notify(
        'economy_events',
        jsonb_build_object(
            'event_type',
            'transaction_success',
            'transaction_id',
            v_transaction_id,
            'guild_id',
            p_guild_id,
            'initiator_id',
            p_initiator_id,
            'target_id',
            p_target_id,
            'amount',
            p_amount,
            'metadata',
            jsonb_strip_nulls(v_metadata)
        )::text
    );

    RETURN (
        v_transaction_id,
        p_guild_id,
        p_initiator_id,
        p_target_id,
        p_amount,
        'transfer'::economy.transaction_direction,
        v_created_at,
        v_initiator_balance,
        v_target_balance,
        NULL::timestamptz,
        jsonb_strip_nulls(v_metadata)
    );
END;
$$;
