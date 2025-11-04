-- Return whether more history rows exist before a given timestamp for a member in a guild
CREATE OR REPLACE FUNCTION economy.fn_has_more_history(
    p_guild_id bigint,
    p_member_id bigint,
    p_created_before timestamptz
) RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE v_exists boolean; BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM economy.currency_transactions
        WHERE guild_id = p_guild_id
          AND (initiator_id = p_member_id OR target_id = p_member_id)
          AND created_at < p_created_before
    ) INTO v_exists;
    RETURN COALESCE(v_exists, false);
END; $$;
