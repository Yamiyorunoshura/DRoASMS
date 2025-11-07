-- Stored procedure implementing administrative adjustments (grant/deduct) with audit.
-- Returns a compact result payload for application consumption.

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE t.typname = 'adjustment_result' AND n.nspname = 'economy'
    ) THEN
        CREATE TYPE economy.adjustment_result AS (
            transaction_id uuid,
            guild_id bigint,
            admin_id bigint,
            target_id bigint,
            amount bigint,
            direction economy.transaction_direction,
            created_at timestamptz,
            target_balance_after bigint,
            metadata jsonb
        );
    END IF;
END$$;

CREATE OR REPLACE FUNCTION economy.fn_adjust_balance(
    p_guild_id bigint,
    p_admin_id bigint,
    p_target_id bigint,
    p_amount bigint,
    p_reason text,
    p_metadata jsonb DEFAULT '{}'::jsonb
)
RETURNS economy.adjustment_result
LANGUAGE plpgsql
AS $$
DECLARE
    v_now timestamptz := timezone('utc', clock_timestamp());
    v_metadata jsonb := coalesce(p_metadata, '{}'::jsonb);
    v_reason text := nullif(p_reason, '');
    v_target_balance bigint;
    v_direction economy.transaction_direction;
    v_amount_abs bigint := abs(p_amount);
    v_tx uuid;
    v_created timestamptz;
BEGIN
    IF v_reason IS NULL THEN
        RAISE EXCEPTION 'Adjustment reason is required.' USING ERRCODE = '22023';
    END IF;

    IF p_amount = 0 THEN
        RAISE EXCEPTION 'Adjustment amount must be non-zero.' USING ERRCODE = '22023';
    END IF;

    -- Ensure ledger rows exist (FKs require both initiator/admin and target)
    INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance, last_modified_at, created_at)
    VALUES (p_guild_id, p_admin_id, 0, v_now, v_now)
    ON CONFLICT (guild_id, member_id) DO NOTHING;

    -- Ensure target ledger row exists
    INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance, last_modified_at, created_at)
    VALUES (p_guild_id, p_target_id, 0, v_now, v_now)
    ON CONFLICT (guild_id, member_id) DO NOTHING;

    IF p_amount > 0 THEN
        v_direction := 'adjustment_grant';
        UPDATE economy.guild_member_balances
        SET current_balance = current_balance + p_amount,
            last_modified_at = v_now
        WHERE guild_id = p_guild_id AND member_id = p_target_id
        RETURNING current_balance INTO v_target_balance;
    ELSE
        v_direction := 'adjustment_deduct';
        -- lock row and validate will not go below zero
        SELECT current_balance INTO v_target_balance
        FROM economy.guild_member_balances
        WHERE guild_id = p_guild_id AND member_id = p_target_id
        FOR UPDATE;

        IF v_target_balance + p_amount < 0 THEN
            RAISE EXCEPTION 'Adjustment denied: balance cannot drop below zero.' USING ERRCODE = 'P0001';
        END IF;

        UPDATE economy.guild_member_balances
        SET current_balance = current_balance + p_amount,
            last_modified_at = v_now
        WHERE guild_id = p_guild_id AND member_id = p_target_id
        RETURNING current_balance INTO v_target_balance;
    END IF;

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
        p_admin_id,
        p_target_id,
        v_amount_abs,
        v_direction,
        v_reason,
        v_target_balance,
        v_target_balance,
        jsonb_strip_nulls(v_metadata)
    )
    RETURNING transaction_id, created_at INTO v_tx, v_created;

    RETURN (
        v_tx,
        p_guild_id,
        p_admin_id,
        p_target_id,
        v_amount_abs,
        v_direction,
        v_created,
        v_target_balance,
        jsonb_strip_nulls(v_metadata)
    );
END;
$$;
