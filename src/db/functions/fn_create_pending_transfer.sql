-- Create a pending transfer record
CREATE OR REPLACE FUNCTION economy.fn_create_pending_transfer(
    p_guild_id bigint,
    p_initiator_id bigint,
    p_target_id bigint,
    p_amount bigint,
    p_metadata jsonb DEFAULT '{}'::jsonb,
    p_expires_at timestamptz DEFAULT NULL
)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
    v_transfer_id uuid;
    v_now timestamptz := timezone('utc', now());
BEGIN
    IF p_initiator_id = p_target_id THEN
        RAISE EXCEPTION 'Initiator and target must be distinct members for transfers.'
            USING ERRCODE = '22023';
    END IF;

    IF p_amount <= 0 THEN
        RAISE EXCEPTION 'Transfer amount must be a positive whole number.'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO economy.pending_transfers (
        guild_id,
        initiator_id,
        target_id,
        amount,
        status,
        checks,
        retry_count,
        expires_at,
        metadata,
        created_at,
        updated_at
    )
    VALUES (
        p_guild_id,
        p_initiator_id,
        p_target_id,
        p_amount,
        'pending',
        '{}'::jsonb,
        0,
        p_expires_at,
        coalesce(p_metadata, '{}'::jsonb),
        v_now,
        v_now
    )
    RETURNING transfer_id
    INTO v_transfer_id;

    RETURN v_transfer_id;
END;
$$;
