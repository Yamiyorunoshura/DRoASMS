-- Schema: governance

-- Ensure a clean slate before recreating (avoid "cannot change return type" and
-- eliminate default-arg overload ambiguity across migrations/tests)
DROP FUNCTION IF EXISTS governance.fn_upsert_state_council_config(
    bigint, bigint, bigint, bigint, bigint, bigint, bigint
);
DROP FUNCTION IF EXISTS governance.fn_upsert_state_council_config(
    bigint, bigint, bigint, bigint, bigint, bigint, bigint, bigint, bigint
);

-- Upsert state council config
CREATE OR REPLACE FUNCTION governance.fn_upsert_state_council_config(
    p_guild_id bigint,
    p_leader_id bigint,
    p_leader_role_id bigint,
    p_internal_affairs_account_id bigint,
    p_finance_account_id bigint,
    p_security_account_id bigint,
    p_central_bank_account_id bigint,
    p_citizen_role_id bigint,
    p_suspect_role_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    leader_id bigint,
    leader_role_id bigint,
    internal_affairs_account_id bigint,
    finance_account_id bigint,
    security_account_id bigint,
    central_bank_account_id bigint,
    citizen_role_id bigint,
    suspect_role_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.state_council_config AS c (
        guild_id, leader_id, leader_role_id, internal_affairs_account_id,
        finance_account_id, security_account_id, central_bank_account_id,
        citizen_role_id, suspect_role_id
    ) VALUES (
        p_guild_id, p_leader_id, p_leader_role_id, p_internal_affairs_account_id,
        p_finance_account_id, p_security_account_id, p_central_bank_account_id,
        p_citizen_role_id, p_suspect_role_id
    )
    -- 使用具名主鍵約束避免與 RETURNS TABLE 之 guild_id 衝突
    ON CONFLICT ON CONSTRAINT state_council_config_pkey
    DO UPDATE SET leader_id = EXCLUDED.leader_id,
                  leader_role_id = EXCLUDED.leader_role_id,
                  internal_affairs_account_id = EXCLUDED.internal_affairs_account_id,
                  finance_account_id = EXCLUDED.finance_account_id,
                  security_account_id = EXCLUDED.security_account_id,
                  central_bank_account_id = EXCLUDED.central_bank_account_id,
                  citizen_role_id = EXCLUDED.citizen_role_id,
                  suspect_role_id = EXCLUDED.suspect_role_id,
                  updated_at = timezone('utc', clock_timestamp())
    RETURNING c.guild_id, c.leader_id, c.leader_role_id, c.internal_affairs_account_id,
              c.finance_account_id, c.security_account_id, c.central_bank_account_id,
              c.citizen_role_id, c.suspect_role_id,
              c.created_at, c.updated_at;
END; $$;

-- Backward-compat overload: 7-arg wrapper that forwards to the 9-arg version
-- This preserves existing callers/tests that still use the legacy signature.
CREATE OR REPLACE FUNCTION governance.fn_upsert_state_council_config(
    p_guild_id bigint,
    p_leader_id bigint,
    p_leader_role_id bigint,
    p_internal_affairs_account_id bigint,
    p_finance_account_id bigint,
    p_security_account_id bigint,
    p_central_bank_account_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    leader_id bigint,
    leader_role_id bigint,
    internal_affairs_account_id bigint,
    finance_account_id bigint,
    security_account_id bigint,
    central_bank_account_id bigint,
    citizen_role_id bigint,
    suspect_role_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT * FROM governance.fn_upsert_state_council_config(
        p_guild_id,
        p_leader_id,
        p_leader_role_id,
        p_internal_affairs_account_id,
        p_finance_account_id,
        p_security_account_id,
        p_central_bank_account_id,
        NULL::bigint,
        NULL::bigint
    );
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_get_state_council_config(
    p_guild_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    leader_id bigint,
    leader_role_id bigint,
    internal_affairs_account_id bigint,
    finance_account_id bigint,
    security_account_id bigint,
    central_bank_account_id bigint,
    citizen_role_id bigint,
    suspect_role_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- Qualify columns to avoid ambiguity with OUT params in RETURNS TABLE
    RETURN QUERY
    SELECT c.guild_id, c.leader_id, c.leader_role_id, c.internal_affairs_account_id,
           c.finance_account_id, c.security_account_id, c.central_bank_account_id,
           c.citizen_role_id, c.suspect_role_id,
           c.created_at, c.updated_at
    FROM governance.state_council_config AS c
    WHERE c.guild_id = p_guild_id;
END; $$;

-- Department configs
CREATE OR REPLACE FUNCTION governance.fn_upsert_department_config(
    p_guild_id bigint,
    p_department text,
    p_role_id bigint,
    p_welfare_amount bigint,
    p_welfare_interval_hours integer,
    p_tax_rate_basis bigint,
    p_tax_rate_percent integer,
    p_max_issuance_per_month bigint
)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    department text,
    role_id bigint,
    welfare_amount bigint,
    welfare_interval_hours integer,
    tax_rate_basis bigint,
    tax_rate_percent integer,
    max_issuance_per_month bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.department_configs AS dc (
        guild_id, department, role_id, welfare_amount, welfare_interval_hours,
        tax_rate_basis, tax_rate_percent, max_issuance_per_month
    ) VALUES (
        p_guild_id, p_department, p_role_id, p_welfare_amount, p_welfare_interval_hours,
        p_tax_rate_basis, p_tax_rate_percent, p_max_issuance_per_month
    )
    -- 使用具名唯一約束避免與 RETURNS TABLE 之 guild_id/department 衝突
    ON CONFLICT ON CONSTRAINT uq_governance_department_configs_guild_dept
    DO UPDATE SET role_id = EXCLUDED.role_id,
                  welfare_amount = EXCLUDED.welfare_amount,
                  welfare_interval_hours = EXCLUDED.welfare_interval_hours,
                  tax_rate_basis = EXCLUDED.tax_rate_basis,
                  tax_rate_percent = EXCLUDED.tax_rate_percent,
                  max_issuance_per_month = EXCLUDED.max_issuance_per_month,
                  updated_at = timezone('utc', clock_timestamp())
    RETURNING dc.id, dc.guild_id, dc.department, dc.role_id, dc.welfare_amount, dc.welfare_interval_hours,
              dc.tax_rate_basis, dc.tax_rate_percent, dc.max_issuance_per_month, dc.created_at, dc.updated_at;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_department_configs(p_guild_id bigint)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    department text,
    role_id bigint,
    welfare_amount bigint,
    welfare_interval_hours integer,
    tax_rate_basis bigint,
    tax_rate_percent integer,
    max_issuance_per_month bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 加上資料表別名避免與 RETURNS TABLE 名稱衝突
    RETURN QUERY
    SELECT dc.id, dc.guild_id, dc.department, dc.role_id, dc.welfare_amount, dc.welfare_interval_hours,
           dc.tax_rate_basis::bigint, dc.tax_rate_percent, dc.max_issuance_per_month, dc.created_at, dc.updated_at
    FROM governance.department_configs AS dc
    WHERE dc.guild_id = p_guild_id
    ORDER BY dc.department;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_get_department_config(p_guild_id bigint, p_department text)
RETURNS TABLE (
    id bigint,
    guild_id bigint,
    department text,
    role_id bigint,
    welfare_amount bigint,
    welfare_interval_hours integer,
    tax_rate_basis bigint,
    tax_rate_percent integer,
    max_issuance_per_month bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 資料行一律加上別名以避免與 RETURNS TABLE 輸出參數名稱衝突（ambiguous column "id"）
    RETURN QUERY
    SELECT dc.id, dc.guild_id, dc.department, dc.role_id, dc.welfare_amount, dc.welfare_interval_hours,
           dc.tax_rate_basis::bigint, dc.tax_rate_percent, dc.max_issuance_per_month, dc.created_at, dc.updated_at
    FROM governance.department_configs AS dc
    WHERE dc.guild_id = p_guild_id AND dc.department = p_department;
END; $$;

-- Government accounts
CREATE OR REPLACE FUNCTION governance.fn_upsert_government_account(
    p_account_id bigint,
    p_guild_id bigint,
    p_department text,
    p_balance bigint
)
RETURNS TABLE (
    account_id bigint,
    guild_id bigint,
    department text,
    balance bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.government_accounts AS ga (
        account_id, guild_id, department, balance
    ) VALUES (p_account_id, p_guild_id, p_department, p_balance)
    -- 使用具名主鍵約束避免與 RETURNS TABLE 之 account_id 衝突
    ON CONFLICT ON CONSTRAINT government_accounts_pkey
    DO UPDATE SET balance = EXCLUDED.balance,
                  updated_at = timezone('utc', clock_timestamp())
    RETURNING ga.account_id, ga.guild_id, ga.department, ga.balance, ga.created_at, ga.updated_at;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_government_accounts(p_guild_id bigint)
RETURNS TABLE (
    account_id bigint,
    guild_id bigint,
    department text,
    balance bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 資料行一律加上別名以避免與 RETURNS TABLE 輸出參數名稱衝突（ambiguous column）
    RETURN QUERY
    SELECT ga.account_id, ga.guild_id, ga.department, ga.balance, ga.created_at, ga.updated_at
    FROM governance.government_accounts AS ga
    WHERE ga.guild_id = p_guild_id
    ORDER BY ga.department;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_update_government_account_balance(
    p_account_id bigint,
    p_new_balance bigint
) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    UPDATE governance.government_accounts
    SET balance = p_new_balance,
        updated_at = timezone('utc', clock_timestamp())
    WHERE account_id = p_account_id;
END; $$;

-- Welfare disbursements
CREATE OR REPLACE FUNCTION governance.fn_create_welfare_disbursement(
    p_guild_id bigint,
    p_recipient_id bigint,
    p_amount bigint,
    p_disbursement_type text,
    p_reference_id text
)
RETURNS TABLE (
    disbursement_id uuid,
    guild_id bigint,
    recipient_id bigint,
    amount bigint,
    disbursement_type text,
    reference_id text,
    disbursed_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.welfare_disbursements AS w (
        guild_id, recipient_id, amount, disbursement_type, reference_id
    ) VALUES (p_guild_id, p_recipient_id, p_amount, p_disbursement_type, p_reference_id)
    RETURNING w.disbursement_id, w.guild_id, w.recipient_id, w.amount, w.disbursement_type,
              w.reference_id, w.disbursed_at;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_welfare_disbursements(
    p_guild_id bigint,
    p_limit int,
    p_offset int
)
RETURNS TABLE (
    disbursement_id uuid,
    guild_id bigint,
    recipient_id bigint,
    amount bigint,
    disbursement_type text,
    reference_id text,
    disbursed_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 避免與 RETURNS TABLE 欄位同名造成模稜兩可
    RETURN QUERY
    SELECT w.disbursement_id, w.guild_id, w.recipient_id, w.amount, w.disbursement_type,
           w.reference_id, w.disbursed_at
    FROM governance.welfare_disbursements AS w
    WHERE w.guild_id = p_guild_id
    ORDER BY disbursed_at DESC
    LIMIT p_limit OFFSET p_offset;
END; $$;

-- Tax records
CREATE OR REPLACE FUNCTION governance.fn_create_tax_record(
    p_guild_id bigint,
    p_taxpayer_id bigint,
    p_taxable_amount bigint,
    p_tax_rate_percent int,
    p_tax_amount bigint,
    p_tax_type text,
    p_assessment_period text
)
RETURNS TABLE (
    tax_id uuid,
    guild_id bigint,
    taxpayer_id bigint,
    taxable_amount bigint,
    tax_rate_percent int,
    tax_amount bigint,
    tax_type text,
    assessment_period text,
    collected_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.tax_records AS t (
        guild_id, taxpayer_id, taxable_amount, tax_rate_percent, tax_amount, tax_type, assessment_period
    ) VALUES (p_guild_id, p_taxpayer_id, p_taxable_amount, p_tax_rate_percent, p_tax_amount, p_tax_type, p_assessment_period)
    RETURNING t.tax_id, t.guild_id, t.taxpayer_id, t.taxable_amount, t.tax_rate_percent, t.tax_amount, t.tax_type, t.assessment_period, t.collected_at;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_tax_records(
    p_guild_id bigint,
    p_limit int,
    p_offset int
)
RETURNS TABLE (
    tax_id uuid,
    guild_id bigint,
    taxpayer_id bigint,
    taxable_amount bigint,
    tax_rate_percent int,
    tax_amount bigint,
    tax_type text,
    assessment_period text,
    collected_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 資料行一律加上別名以避免與 RETURNS TABLE 輸出參數名稱衝突
    RETURN QUERY
    SELECT t.tax_id, t.guild_id, t.taxpayer_id, t.taxable_amount, t.tax_rate_percent,
           t.tax_amount, t.tax_type, t.assessment_period, t.collected_at
    FROM governance.tax_records AS t
    WHERE t.guild_id = p_guild_id
    ORDER BY collected_at DESC
    LIMIT p_limit OFFSET p_offset;
END; $$;

-- Identity records
CREATE OR REPLACE FUNCTION governance.fn_create_identity_record(
    p_guild_id bigint,
    p_target_id bigint,
    p_action text,
    p_reason text,
    p_performed_by bigint
)
RETURNS TABLE (
    record_id uuid,
    guild_id bigint,
    target_id bigint,
    action text,
    reason text,
    performed_by bigint,
    performed_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.identity_records AS ir (
        guild_id, target_id, action, reason, performed_by
    ) VALUES (p_guild_id, p_target_id, p_action, p_reason, p_performed_by)
    RETURNING ir.record_id, ir.guild_id, ir.target_id, ir.action, ir.reason, ir.performed_by, ir.performed_at;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_identity_records(
    p_guild_id bigint,
    p_limit int,
    p_offset int
)
RETURNS TABLE (
    record_id uuid,
    guild_id bigint,
    target_id bigint,
    action text,
    reason text,
    performed_by bigint,
    performed_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 資料行加別名，避免與 RETURNS TABLE 欄位同名
    RETURN QUERY
    SELECT ir.record_id, ir.guild_id, ir.target_id, ir.action, ir.reason, ir.performed_by, ir.performed_at
    FROM governance.identity_records AS ir
    WHERE ir.guild_id = p_guild_id
    ORDER BY performed_at DESC
    LIMIT p_limit OFFSET p_offset;
END; $$;

-- Currency issuances
CREATE OR REPLACE FUNCTION governance.fn_create_currency_issuance(
    p_guild_id bigint,
    p_amount bigint,
    p_reason text,
    p_performed_by bigint,
    p_month_period text
)
RETURNS TABLE (
    issuance_id uuid,
    guild_id bigint,
    amount bigint,
    reason text,
    performed_by bigint,
    month_period text,
    issued_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 注意：RETURNS TABLE 宣告的欄位（issuance_id, guild_id, ...）在 plpgsql 中同時是
    -- OUT 參數變數名稱；若在 RETURNING 直接寫欄位名，會與變數同名而造成歧義。
    -- 透過為目標表建立別名（ci）並在 RETURNING 使用 ci.qualified_name 可消除此問題，
    -- 同時不改變對外的回傳欄位名稱與形狀。
    RETURN QUERY
    INSERT INTO governance.currency_issuances AS ci (
        guild_id, amount, reason, performed_by, month_period
    ) VALUES (p_guild_id, p_amount, p_reason, p_performed_by, p_month_period)
    RETURNING ci.issuance_id, ci.guild_id, ci.amount, ci.reason, ci.performed_by, ci.month_period, ci.issued_at;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_currency_issuances(
    p_guild_id bigint,
    p_month_period text,
    p_limit int,
    p_offset int
)
RETURNS TABLE (
    issuance_id uuid,
    guild_id bigint,
    amount bigint,
    reason text,
    performed_by bigint,
    month_period text,
    issued_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    IF p_month_period IS NULL THEN
        -- 加別名避免 RETURNS TABLE 欄位名稱衝突
        RETURN QUERY
        SELECT ci.issuance_id, ci.guild_id, ci.amount, ci.reason, ci.performed_by, ci.month_period, ci.issued_at
        FROM governance.currency_issuances AS ci
        WHERE ci.guild_id = p_guild_id
        ORDER BY issued_at DESC
        LIMIT p_limit OFFSET p_offset;
    ELSE
        RETURN QUERY
        SELECT ci.issuance_id, ci.guild_id, ci.amount, ci.reason, ci.performed_by, ci.month_period, ci.issued_at
        FROM governance.currency_issuances AS ci
        WHERE ci.guild_id = p_guild_id AND ci.month_period = p_month_period
        ORDER BY issued_at DESC
        LIMIT p_limit OFFSET p_offset;
    END IF;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_sum_monthly_issuance(
    p_guild_id bigint,
    p_month_period text
) RETURNS bigint LANGUAGE plpgsql AS $$
DECLARE v_total bigint; BEGIN
    SELECT COALESCE(SUM(amount), 0) INTO v_total
    FROM governance.currency_issuances
    WHERE guild_id = p_guild_id AND month_period = p_month_period;
    RETURN COALESCE(v_total, 0);
END; $$;

-- Interdepartment transfers
CREATE OR REPLACE FUNCTION governance.fn_create_interdepartment_transfer(
    p_guild_id bigint,
    p_from_department text,
    p_to_department text,
    p_amount bigint,
    p_reason text,
    p_performed_by bigint
)
RETURNS TABLE (
    transfer_id uuid,
    guild_id bigint,
    from_department text,
    to_department text,
    amount bigint,
    reason text,
    performed_by bigint,
    transferred_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    INSERT INTO governance.interdepartment_transfers AS it (
        guild_id, from_department, to_department, amount, reason, performed_by
    ) VALUES (p_guild_id, p_from_department, p_to_department, p_amount, p_reason, p_performed_by)
    RETURNING it.transfer_id, it.guild_id, it.from_department, it.to_department, it.amount, it.reason, it.performed_by, it.transferred_at;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_interdepartment_transfers(
    p_guild_id bigint,
    p_limit int,
    p_offset int
)
RETURNS TABLE (
    transfer_id uuid,
    guild_id bigint,
    from_department text,
    to_department text,
    amount bigint,
    reason text,
    performed_by bigint,
    transferred_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 全部加上別名，避免 RETURNS TABLE 名稱與資料表欄位混淆
    RETURN QUERY
    SELECT it.transfer_id, it.guild_id, it.from_department, it.to_department, it.amount,
           it.reason, it.performed_by, it.transferred_at
    FROM governance.interdepartment_transfers AS it
    WHERE it.guild_id = p_guild_id
    ORDER BY transferred_at DESC
    LIMIT p_limit OFFSET p_offset;
END; $$;

-- Reporting helpers
CREATE OR REPLACE FUNCTION governance.fn_list_all_department_configs_with_welfare()
RETURNS TABLE (
    guild_id bigint,
    department text,
    welfare_amount bigint,
    welfare_interval_hours int
) LANGUAGE plpgsql AS $$
BEGIN
    -- Qualify columns to avoid ambiguity with OUT params in RETURNS TABLE
    RETURN QUERY
    SELECT d.guild_id, d.department, d.welfare_amount, d.welfare_interval_hours
    FROM governance.department_configs AS d
    WHERE d.welfare_amount > 0 AND d.welfare_interval_hours > 0;
END; $$;

CREATE OR REPLACE FUNCTION governance.fn_list_all_department_configs_for_issuance()
RETURNS TABLE (
    guild_id bigint,
    department text,
    max_issuance_per_month bigint
) LANGUAGE plpgsql AS $$
BEGIN
    -- Qualify columns to avoid ambiguity with OUT params in RETURNS TABLE
    RETURN QUERY
    SELECT d.guild_id, d.department, d.max_issuance_per_month
    FROM governance.department_configs AS d
    WHERE d.max_issuance_per_month > 0;
END; $$;
