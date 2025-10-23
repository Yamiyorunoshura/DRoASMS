-- Stored function returning recent transactions for a guild member.
CREATE OR REPLACE FUNCTION economy.fn_get_history(
    p_guild_id bigint,
    p_member_id bigint,
    p_limit integer DEFAULT 10,
    p_cursor timestamptz DEFAULT NULL
)
RETURNS TABLE (
    transaction_id uuid,
    guild_id bigint,
    initiator_id bigint,
    target_id bigint,
    amount bigint,
    direction economy.transaction_direction,
    reason text,
    created_at timestamptz,
    metadata jsonb,
    balance_after_initiator bigint,
    balance_after_target bigint
)
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_limit IS NULL THEN
        RAISE EXCEPTION 'History limit cannot be null.'
            USING ERRCODE = '22004';
    END IF;

    IF p_limit < 1 OR p_limit > 50 THEN
        RAISE EXCEPTION 'History limit must be between 1 and 50 inclusive.'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT
        ct.transaction_id,
        ct.guild_id,
        ct.initiator_id,
        ct.target_id,
        ct.amount,
        ct.direction,
        ct.reason,
        ct.created_at,
        ct.metadata,
        ct.balance_after_initiator,
        ct.balance_after_target
    FROM economy.currency_transactions AS ct
    WHERE ct.guild_id = p_guild_id
      AND (
            ct.initiator_id = p_member_id
            OR ct.target_id = p_member_id
      )
      AND (p_cursor IS NULL OR ct.created_at < p_cursor)
    ORDER BY ct.created_at DESC, ct.transaction_id DESC
    LIMIT p_limit;
END;
$$;
