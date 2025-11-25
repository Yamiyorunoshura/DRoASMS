-- Schema: governance
-- Business License Management Functions for Interior Affairs

-- ============================================================================
-- fn_issue_business_license: 發放商業許可
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_issue_business_license(
    bigint, bigint, text, bigint, timestamptz
);

CREATE OR REPLACE FUNCTION governance.fn_issue_business_license(
    p_guild_id bigint,
    p_user_id bigint,
    p_license_type text,
    p_issued_by bigint,
    p_expires_at timestamptz
)
RETURNS TABLE (
    license_id uuid,
    guild_id bigint,
    user_id bigint,
    license_type text,
    issued_by bigint,
    issued_at timestamptz,
    expires_at timestamptz,
    status text,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
DECLARE
    v_existing_count integer;
BEGIN
    -- Check for existing active license of the same type
    SELECT COUNT(*) INTO v_existing_count
    FROM governance.business_licenses AS bl
    WHERE bl.guild_id = p_guild_id
      AND bl.user_id = p_user_id
      AND bl.license_type = p_license_type
      AND bl.status = 'active';

    IF v_existing_count > 0 THEN
        RAISE EXCEPTION 'User already has an active license of type %', p_license_type
            USING ERRCODE = 'unique_violation';
    END IF;

    RETURN QUERY
    INSERT INTO governance.business_licenses AS bl (
        guild_id, user_id, license_type, issued_by, expires_at
    ) VALUES (
        p_guild_id, p_user_id, p_license_type, p_issued_by, p_expires_at
    )
    RETURNING
        bl.license_id, bl.guild_id, bl.user_id, bl.license_type,
        bl.issued_by, bl.issued_at, bl.expires_at, bl.status,
        bl.created_at, bl.updated_at;
END; $$;

-- ============================================================================
-- fn_revoke_business_license: 撤銷商業許可
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_revoke_business_license(
    uuid, bigint, text
);

CREATE OR REPLACE FUNCTION governance.fn_revoke_business_license(
    p_license_id uuid,
    p_revoked_by bigint,
    p_revoke_reason text
)
RETURNS TABLE (
    license_id uuid,
    guild_id bigint,
    user_id bigint,
    license_type text,
    issued_by bigint,
    issued_at timestamptz,
    expires_at timestamptz,
    status text,
    revoked_by bigint,
    revoked_at timestamptz,
    revoke_reason text,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
DECLARE
    v_license_row RECORD;
BEGIN
    -- Get and lock the license
    SELECT * INTO v_license_row
    FROM governance.business_licenses AS bl
    WHERE bl.license_id = p_license_id
    FOR UPDATE;

    IF v_license_row IS NULL THEN
        RAISE EXCEPTION 'License not found: %', p_license_id
            USING ERRCODE = 'no_data_found';
    END IF;

    IF v_license_row.status != 'active' THEN
        RAISE EXCEPTION 'Cannot revoke license with status %', v_license_row.status
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    RETURN QUERY
    UPDATE governance.business_licenses AS bl
    SET status = 'revoked',
        revoked_by = p_revoked_by,
        revoked_at = timezone('utc', clock_timestamp()),
        revoke_reason = p_revoke_reason,
        updated_at = timezone('utc', clock_timestamp())
    WHERE bl.license_id = p_license_id
    RETURNING
        bl.license_id, bl.guild_id, bl.user_id, bl.license_type,
        bl.issued_by, bl.issued_at, bl.expires_at, bl.status,
        bl.revoked_by, bl.revoked_at, bl.revoke_reason,
        bl.created_at, bl.updated_at;
END; $$;

-- ============================================================================
-- fn_get_business_license: 取得單一許可詳情
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_get_business_license(uuid);

CREATE OR REPLACE FUNCTION governance.fn_get_business_license(
    p_license_id uuid
)
RETURNS TABLE (
    license_id uuid,
    guild_id bigint,
    user_id bigint,
    license_type text,
    issued_by bigint,
    issued_at timestamptz,
    expires_at timestamptz,
    status text,
    revoked_by bigint,
    revoked_at timestamptz,
    revoke_reason text,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        bl.license_id, bl.guild_id, bl.user_id, bl.license_type,
        bl.issued_by, bl.issued_at, bl.expires_at, bl.status,
        bl.revoked_by, bl.revoked_at, bl.revoke_reason,
        bl.created_at, bl.updated_at
    FROM governance.business_licenses AS bl
    WHERE bl.license_id = p_license_id;
END; $$;

-- ============================================================================
-- fn_list_business_licenses: 列出許可（支援篩選與分頁）
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_list_business_licenses(
    bigint, text, text, integer, integer
);

CREATE OR REPLACE FUNCTION governance.fn_list_business_licenses(
    p_guild_id bigint,
    p_status text DEFAULT NULL,
    p_license_type text DEFAULT NULL,
    p_limit integer DEFAULT 10,
    p_offset integer DEFAULT 0
)
RETURNS TABLE (
    license_id uuid,
    guild_id bigint,
    user_id bigint,
    license_type text,
    issued_by bigint,
    issued_at timestamptz,
    expires_at timestamptz,
    status text,
    revoked_by bigint,
    revoked_at timestamptz,
    revoke_reason text,
    created_at timestamptz,
    updated_at timestamptz,
    total_count bigint
) LANGUAGE plpgsql AS $$
DECLARE
    v_total_count bigint;
BEGIN
    -- Get total count for pagination
    SELECT COUNT(*) INTO v_total_count
    FROM governance.business_licenses AS bl
    WHERE bl.guild_id = p_guild_id
      AND (p_status IS NULL OR bl.status = p_status)
      AND (p_license_type IS NULL OR bl.license_type = p_license_type);

    RETURN QUERY
    SELECT
        bl.license_id, bl.guild_id, bl.user_id, bl.license_type,
        bl.issued_by, bl.issued_at, bl.expires_at, bl.status,
        bl.revoked_by, bl.revoked_at, bl.revoke_reason,
        bl.created_at, bl.updated_at,
        v_total_count
    FROM governance.business_licenses AS bl
    WHERE bl.guild_id = p_guild_id
      AND (p_status IS NULL OR bl.status = p_status)
      AND (p_license_type IS NULL OR bl.license_type = p_license_type)
    ORDER BY bl.issued_at DESC
    LIMIT p_limit OFFSET p_offset;
END; $$;

-- ============================================================================
-- fn_get_user_licenses: 取得特定用戶的所有許可
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_get_user_licenses(bigint, bigint);

CREATE OR REPLACE FUNCTION governance.fn_get_user_licenses(
    p_guild_id bigint,
    p_user_id bigint
)
RETURNS TABLE (
    license_id uuid,
    guild_id bigint,
    user_id bigint,
    license_type text,
    issued_by bigint,
    issued_at timestamptz,
    expires_at timestamptz,
    status text,
    revoked_by bigint,
    revoked_at timestamptz,
    revoke_reason text,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        bl.license_id, bl.guild_id, bl.user_id, bl.license_type,
        bl.issued_by, bl.issued_at, bl.expires_at, bl.status,
        bl.revoked_by, bl.revoked_at, bl.revoke_reason,
        bl.created_at, bl.updated_at
    FROM governance.business_licenses AS bl
    WHERE bl.guild_id = p_guild_id
      AND bl.user_id = p_user_id
    ORDER BY bl.issued_at DESC;
END; $$;

-- ============================================================================
-- fn_check_active_license: 檢查用戶是否擁有特定類型的有效許可
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_check_active_license(bigint, bigint, text);

CREATE OR REPLACE FUNCTION governance.fn_check_active_license(
    p_guild_id bigint,
    p_user_id bigint,
    p_license_type text
)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE
    v_has_license boolean;
BEGIN
    SELECT EXISTS (
        SELECT 1
        FROM governance.business_licenses AS bl
        WHERE bl.guild_id = p_guild_id
          AND bl.user_id = p_user_id
          AND bl.license_type = p_license_type
          AND bl.status = 'active'
          AND bl.expires_at > timezone('utc', clock_timestamp())
    ) INTO v_has_license;

    RETURN v_has_license;
END; $$;

-- ============================================================================
-- fn_expire_business_licenses: 自動過期已到期的許可（可由 pg_cron 調用）
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_expire_business_licenses();

CREATE OR REPLACE FUNCTION governance.fn_expire_business_licenses()
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE
    v_expired_count integer;
BEGIN
    UPDATE governance.business_licenses
    SET status = 'expired',
        updated_at = timezone('utc', clock_timestamp())
    WHERE status = 'active'
      AND expires_at <= timezone('utc', clock_timestamp());

    GET DIAGNOSTICS v_expired_count = ROW_COUNT;
    RETURN v_expired_count;
END; $$;

-- ============================================================================
-- fn_count_business_licenses_by_status: 統計各狀態的許可數量
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_count_business_licenses_by_status(bigint);

CREATE OR REPLACE FUNCTION governance.fn_count_business_licenses_by_status(
    p_guild_id bigint
)
RETURNS TABLE (
    status text,
    count bigint
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT bl.status, COUNT(*)::bigint
    FROM governance.business_licenses AS bl
    WHERE bl.guild_id = p_guild_id
    GROUP BY bl.status;
END; $$;
