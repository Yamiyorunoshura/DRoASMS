-- Get a single pending transfer by transfer_id
CREATE OR REPLACE FUNCTION economy.fn_get_pending_transfer(p_transfer_id uuid)
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
    WHERE pt.transfer_id = p_transfer_id;
END;
$$;
