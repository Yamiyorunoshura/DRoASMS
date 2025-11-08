-- Supreme Assembly helpers and config functions.
-- Schema: governance

-- Deterministic account id: 9.2e18 + guild_id
CREATE OR REPLACE FUNCTION governance.fn_sa_account_id(p_guild_id bigint)
RETURNS bigint LANGUAGE SQL IMMUTABLE PARALLEL SAFE AS $$
    -- 將 guild_id 的低 9 位嵌入至 9.2e18 後綴，避免超出 bigint 範圍
    SELECT 9200000000000000000::bigint + (p_guild_id % 1000000000)::bigint
$$;

-- Validate if an account id belongs to Supreme Assembly range
CREATE OR REPLACE FUNCTION governance.fn_is_sa_account(p_account_id bigint)
RETURNS boolean LANGUAGE SQL IMMUTABLE PARALLEL SAFE AS $$
    -- 落在 [BASE, BASE + 999,999,999] 範圍內；避免使用超出 bigint 的常數
    WITH base(val) AS (SELECT 9200000000000000000::bigint)
    SELECT p_account_id >= base.val
           AND (p_account_id - base.val) BETWEEN 0::bigint AND 999999999::bigint
    FROM base
$$;

-- Upsert Supreme Assembly configuration (speaker/member roles)
CREATE OR REPLACE FUNCTION governance.fn_upsert_supreme_assembly_config(
    p_guild_id bigint,
    p_speaker_role_id bigint,
    p_member_role_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    speaker_role_id bigint,
    member_role_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.supreme_assembly_configurations AS c (
        guild_id, speaker_role_id, member_role_id
    ) VALUES (p_guild_id, p_speaker_role_id, p_member_role_id)
    ON CONFLICT ON CONSTRAINT supreme_assembly_configurations_pkey
    DO UPDATE SET speaker_role_id = EXCLUDED.speaker_role_id,
                  member_role_id = EXCLUDED.member_role_id,
                  updated_at = timezone('utc', clock_timestamp())
    RETURNING c.guild_id, c.speaker_role_id, c.member_role_id, c.created_at, c.updated_at;
END; $$;

-- Get Supreme Assembly configuration for a guild
CREATE OR REPLACE FUNCTION governance.fn_get_supreme_assembly_config(
    p_guild_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    speaker_role_id bigint,
    member_role_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT c.guild_id, c.speaker_role_id, c.member_role_id, c.created_at, c.updated_at
    FROM governance.supreme_assembly_configurations AS c
    WHERE c.guild_id = p_guild_id;
END; $$;
