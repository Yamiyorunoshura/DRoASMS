-- Schema: governance
-- Company Management Functions for Business Entity Management

-- ============================================================================
-- fn_create_company: 創建公司
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_create_company(
    bigint, bigint, uuid, varchar, bigint
);

CREATE OR REPLACE FUNCTION governance.fn_create_company(
    p_guild_id bigint,
    p_owner_id bigint,
    p_license_id uuid,
    p_name varchar(100),
    p_account_id bigint
)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    owner_id bigint,
    license_id uuid,
    name varchar,
    account_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
DECLARE
    v_license RECORD;
    v_existing_company RECORD;
BEGIN
    -- Verify license exists, is active, and belongs to the owner
    SELECT * INTO v_license
    FROM governance.business_licenses AS bl
    WHERE bl.license_id = p_license_id
      AND bl.guild_id = p_guild_id
      AND bl.user_id = p_owner_id
      AND bl.status = 'active';

    IF v_license IS NULL THEN
        RAISE EXCEPTION 'Invalid or inactive license: %', p_license_id
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    -- Check if license already has a company
    SELECT * INTO v_existing_company
    FROM governance.companies AS c
    WHERE c.guild_id = p_guild_id
      AND c.license_id = p_license_id;

    IF v_existing_company IS NOT NULL THEN
        RAISE EXCEPTION 'License already has an associated company'
            USING ERRCODE = 'unique_violation';
    END IF;

    -- Validate name length
    IF length(trim(p_name)) < 1 OR length(trim(p_name)) > 100 THEN
        RAISE EXCEPTION 'Company name must be 1-100 characters'
            USING ERRCODE = 'invalid_parameter_value';
    END IF;

    RETURN QUERY
    INSERT INTO governance.companies AS c (
        guild_id, owner_id, license_id, name, account_id
    ) VALUES (
        p_guild_id, p_owner_id, p_license_id, trim(p_name), p_account_id
    )
    RETURNING
        c.id, c.guild_id, c.owner_id, c.license_id,
        c.name, c.account_id, c.created_at, c.updated_at;
END; $$;

-- ============================================================================
-- fn_get_company: 取得單一公司詳情
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_get_company(bigint);

CREATE OR REPLACE FUNCTION governance.fn_get_company(
    p_company_id bigint
)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    owner_id bigint,
    license_id uuid,
    name varchar,
    account_id bigint,
    license_type text,
    license_status text,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id, c.guild_id, c.owner_id, c.license_id,
        c.name, c.account_id,
        bl.license_type, bl.status AS license_status,
        c.created_at, c.updated_at
    FROM governance.companies AS c
    JOIN governance.business_licenses AS bl ON bl.license_id = c.license_id
    WHERE c.id = p_company_id;
END; $$;

-- ============================================================================
-- fn_get_company_by_account: 根據帳戶 ID 取得公司
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_get_company_by_account(bigint);

CREATE OR REPLACE FUNCTION governance.fn_get_company_by_account(
    p_account_id bigint
)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    owner_id bigint,
    license_id uuid,
    name varchar,
    account_id bigint,
    license_type text,
    license_status text,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id, c.guild_id, c.owner_id, c.license_id,
        c.name, c.account_id,
        bl.license_type, bl.status AS license_status,
        c.created_at, c.updated_at
    FROM governance.companies AS c
    JOIN governance.business_licenses AS bl ON bl.license_id = c.license_id
    WHERE c.account_id = p_account_id;
END; $$;

-- ============================================================================
-- fn_list_user_companies: 列出用戶擁有的所有公司
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_list_user_companies(bigint, bigint);

CREATE OR REPLACE FUNCTION governance.fn_list_user_companies(
    p_guild_id bigint,
    p_owner_id bigint
)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    owner_id bigint,
    license_id uuid,
    name varchar,
    account_id bigint,
    license_type text,
    license_status text,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id, c.guild_id, c.owner_id, c.license_id,
        c.name, c.account_id,
        bl.license_type, bl.status AS license_status,
        c.created_at, c.updated_at
    FROM governance.companies AS c
    JOIN governance.business_licenses AS bl ON bl.license_id = c.license_id
    WHERE c.guild_id = p_guild_id
      AND c.owner_id = p_owner_id
    ORDER BY c.created_at DESC;
END; $$;

-- ============================================================================
-- fn_list_guild_companies: 列出伺服器內所有公司
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_list_guild_companies(bigint, int, int);

CREATE OR REPLACE FUNCTION governance.fn_list_guild_companies(
    p_guild_id bigint,
    p_limit int DEFAULT 20,
    p_offset int DEFAULT 0
)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    owner_id bigint,
    license_id uuid,
    name varchar,
    account_id bigint,
    license_type text,
    license_status text,
    created_at timestamptz,
    updated_at timestamptz,
    total_count bigint
) LANGUAGE plpgsql AS $$
DECLARE
    v_total_count bigint;
BEGIN
    -- Get total count
    SELECT COUNT(*) INTO v_total_count
    FROM governance.companies AS c
    WHERE c.guild_id = p_guild_id;

    RETURN QUERY
    SELECT
        c.id, c.guild_id, c.owner_id, c.license_id,
        c.name, c.account_id,
        bl.license_type, bl.status AS license_status,
        c.created_at, c.updated_at,
        v_total_count
    FROM governance.companies AS c
    JOIN governance.business_licenses AS bl ON bl.license_id = c.license_id
    WHERE c.guild_id = p_guild_id
    ORDER BY c.created_at DESC
    LIMIT p_limit
    OFFSET p_offset;
END; $$;

-- ============================================================================
-- fn_get_available_licenses_for_company: 取得可用於建立公司的許可證
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_get_available_licenses_for_company(bigint, bigint);

CREATE OR REPLACE FUNCTION governance.fn_get_available_licenses_for_company(
    p_guild_id bigint,
    p_user_id bigint
)
RETURNS TABLE (
    license_id uuid,
    license_type text,
    issued_at timestamptz,
    expires_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT
        bl.license_id, bl.license_type, bl.issued_at, bl.expires_at
    FROM governance.business_licenses AS bl
    LEFT JOIN governance.companies AS c ON c.license_id = bl.license_id
    WHERE bl.guild_id = p_guild_id
      AND bl.user_id = p_user_id
      AND bl.status = 'active'
      AND c.id IS NULL  -- No company associated yet
    ORDER BY bl.issued_at DESC;
END; $$;

-- ============================================================================
-- fn_check_company_ownership: 驗證公司擁有權
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_check_company_ownership(bigint, bigint);

CREATE OR REPLACE FUNCTION governance.fn_check_company_ownership(
    p_company_id bigint,
    p_user_id bigint
)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE
    v_owner_id bigint;
BEGIN
    SELECT c.owner_id INTO v_owner_id
    FROM governance.companies AS c
    WHERE c.id = p_company_id;

    RETURN v_owner_id = p_user_id;
END; $$;

-- ============================================================================
-- fn_check_company_license_valid: 驗證公司許可證是否有效
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_check_company_license_valid(bigint);

CREATE OR REPLACE FUNCTION governance.fn_check_company_license_valid(
    p_company_id bigint
)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE
    v_license_status text;
BEGIN
    SELECT bl.status INTO v_license_status
    FROM governance.companies AS c
    JOIN governance.business_licenses AS bl ON bl.license_id = c.license_id
    WHERE c.id = p_company_id;

    RETURN v_license_status = 'active';
END; $$;

-- ============================================================================
-- fn_derive_company_account_id: 計算公司帳戶 ID
-- ============================================================================
DROP FUNCTION IF EXISTS governance.fn_derive_company_account_id(bigint, bigint);

CREATE OR REPLACE FUNCTION governance.fn_derive_company_account_id(
    p_guild_id bigint,
    p_company_id bigint
)
RETURNS bigint LANGUAGE plpgsql AS $$
BEGIN
    --
    -- 2025-11 修正：舊公式使用 guild_id * 1000，在 Discord 雪花 ID 約 1.3e18
    -- 的情況下會超過 BIGINT 上限 9_223_372_036_854_775_807，導致溢位。
    -- 改為只使用全域唯一的 company_id 偏移，維持可預測且避免碰撞，並保留
    -- 9.6e15 區段與其他治理帳戶（9.0e15~9.5e15）分隔。參數 p_guild_id 保留
    -- 相容性但不再參與計算。
    --
    RETURN 9600000000000000 + p_company_id;
END; $$;
