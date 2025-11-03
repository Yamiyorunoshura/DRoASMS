-- List pending transfers with filtering and pagination
CREATE OR REPLACE FUNCTION economy.fn_list_pending_transfers(
    p_guild_id bigint,
    p_status text DEFAULT NULL,
    p_limit integer DEFAULT 100,
    p_offset integer DEFAULT 0
)
RETURNS TABLE (
    transfer_id uuid,
    guild_id bigint,
    initiator_id bigint,
    target_id bigint,
    amount bigint,
    status text,
    checks jsonb,
    retry_count integer,
    expires_at timestamptz,
    metadata jsonb,
    created_at timestamptz,
    updated_at timestamptz
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        pt.transfer_id,
        pt.guild_id,
        pt.initiator_id,
        pt.target_id,
        pt.amount,
        pt.status::text AS status,  -- cast to text to match RETURNS TABLE
        pt.checks,
        pt.retry_count,
        pt.expires_at,
        pt.metadata,
        pt.created_at,
        pt.updated_at
    FROM economy.pending_transfers pt
    WHERE pt.guild_id = p_guild_id
      AND (p_status IS NULL OR pt.status = p_status)
    ORDER BY pt.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END;
$$;
