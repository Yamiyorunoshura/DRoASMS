-- Stored function returning a member's current balance snapshot.
CREATE OR REPLACE FUNCTION economy.fn_get_balance(
    p_guild_id bigint,
    p_member_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    member_id bigint,
    balance bigint,
    last_modified_at timestamptz,
    throttled_until timestamptz
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_now timestamptz := timezone('utc', clock_timestamp());
BEGIN
    INSERT INTO economy.guild_member_balances (
        guild_id,
        member_id,
        current_balance,
        last_modified_at,
        created_at
    )
    VALUES (p_guild_id, p_member_id, 0, v_now, v_now)
    ON CONFLICT ON CONSTRAINT pk_guild_member_balances DO NOTHING;

    RETURN QUERY
    SELECT
        gb.guild_id,
        gb.member_id,
        gb.current_balance,
        gb.last_modified_at,
        gb.throttled_until
    FROM economy.guild_member_balances AS gb
    WHERE gb.guild_id = p_guild_id AND gb.member_id = p_member_id;
END;
$$;
