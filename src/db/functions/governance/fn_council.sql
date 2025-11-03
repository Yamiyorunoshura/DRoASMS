-- Council governance functions consolidated in one file.
-- Schema assumed: governance
-- All timestamps use UTC.

-- Upsert council config
CREATE OR REPLACE FUNCTION governance.fn_upsert_council_config(
    p_guild_id bigint,
    p_council_role_id bigint,
    p_council_account_member_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    council_role_id bigint,
    council_account_member_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 資料行一律加上表別名，避免與 RETURNS TABLE 的 OUT 參數（guild_id 等）同名而產生模糊
    RETURN QUERY
    INSERT INTO governance.council_config AS cc (
        guild_id, council_role_id, council_account_member_id
    ) VALUES (p_guild_id, p_council_role_id, p_council_account_member_id)
    ON CONFLICT ON CONSTRAINT council_config_pkey
    DO UPDATE SET council_role_id = EXCLUDED.council_role_id,
                  council_account_member_id = EXCLUDED.council_account_member_id,
                  updated_at = timezone('utc', now())
    RETURNING cc.guild_id, cc.council_role_id, cc.council_account_member_id, cc.created_at, cc.updated_at;
END;
$$;

-- Get council config
CREATE OR REPLACE FUNCTION governance.fn_get_council_config(
    p_guild_id bigint
)
RETURNS TABLE (
    guild_id bigint,
    council_role_id bigint,
    council_account_member_id bigint,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- 一律加上別名避免與 OUT 參數同名的欄位產生模糊
    RETURN QUERY
    SELECT cc.guild_id, cc.council_role_id, cc.council_account_member_id, cc.created_at, cc.updated_at
    FROM governance.council_config AS cc
    WHERE cc.guild_id = p_guild_id;
END;
$$;

-- Create proposal with snapshot and concurrency limit (max 5 active per guild)
CREATE OR REPLACE FUNCTION governance.fn_create_proposal(
    p_guild_id bigint,
    p_proposer_id bigint,
    p_target_id bigint,
    p_amount bigint,
    p_description text,
    p_attachment_url text,
    p_snapshot_member_ids bigint[],
    p_deadline_hours integer DEFAULT 72
)
RETURNS TABLE (
    proposal_id uuid,
    guild_id bigint,
    proposer_id bigint,
    target_id bigint,
    amount bigint,
    description text,
    attachment_url text,
    snapshot_n integer,
    threshold_t integer,
    deadline_at timestamptz,
    status text,
    reminder_sent boolean,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
DECLARE
    v_now timestamptz := timezone('utc', now());
    v_active_count int;
    v_n int;
    v_t int;
    v_deadline timestamptz;
BEGIN
    SELECT COUNT(*) INTO v_active_count
    FROM governance.proposals
    WHERE guild_id = p_guild_id AND status = '進行中';
    IF v_active_count >= 5 THEN
        RAISE EXCEPTION 'active proposal limit reached for guild %', p_guild_id USING ERRCODE = 'P0001';
    END IF;

    v_n := COALESCE(array_length(p_snapshot_member_ids, 1), 0);
    v_t := v_n / 2 + 1;
    v_deadline := v_now + make_interval(hours => COALESCE(p_deadline_hours, 72));

    INSERT INTO governance.proposals AS p (
        guild_id, proposer_id, target_id, amount, description, attachment_url,
        snapshot_n, threshold_t, deadline_at, status
    ) VALUES (
        p_guild_id, p_proposer_id, p_target_id, p_amount, p_description, p_attachment_url,
        v_n, v_t, v_deadline, '進行中'
    )
    RETURNING p.proposal_id, p.guild_id, p.proposer_id, p.target_id, p.amount, p.description,
              p.attachment_url, p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
              p.reminder_sent, p.created_at, p.updated_at
    INTO proposal_id, guild_id, proposer_id, target_id, amount, description,
         attachment_url, snapshot_n, threshold_t, deadline_at, status,
         reminder_sent, created_at, updated_at;

    IF v_n > 0 THEN
        INSERT INTO governance.proposal_snapshots (proposal_id, member_id)
        SELECT proposal_id, unnest(p_snapshot_member_ids)
        ON CONFLICT DO NOTHING;
    END IF;

    RETURN NEXT;
END;
$$;

-- Fetch proposal by id
CREATE OR REPLACE FUNCTION governance.fn_get_proposal(p_proposal_id uuid)
RETURNS TABLE (
    proposal_id uuid,
    guild_id bigint,
    proposer_id bigint,
    target_id bigint,
    amount bigint,
    description text,
    attachment_url text,
    snapshot_n integer,
    threshold_t integer,
    deadline_at timestamptz,
    status text,
    reminder_sent boolean,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- Qualify columns to avoid ambiguity with OUT params in RETURNS TABLE
    RETURN QUERY
    SELECT p.proposal_id, p.guild_id, p.proposer_id, p.target_id, p.amount, p.description,
           p.attachment_url, p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
           p.reminder_sent, p.created_at, p.updated_at
    FROM governance.proposals AS p
    WHERE p.proposal_id = p_proposal_id;
END;
$$;

-- Fetch snapshot member ids
CREATE OR REPLACE FUNCTION governance.fn_get_snapshot_members(p_proposal_id uuid)
RETURNS SETOF bigint LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT member_id FROM governance.proposal_snapshots WHERE proposal_id = p_proposal_id;
END;
$$;

-- Count active proposals for a guild
CREATE OR REPLACE FUNCTION governance.fn_count_active_proposals(p_guild_id bigint)
RETURNS integer LANGUAGE plpgsql AS $$
DECLARE v_count int; BEGIN
    SELECT COUNT(*) INTO v_count FROM governance.proposals
    WHERE guild_id = p_guild_id AND status = '進行中';
    RETURN COALESCE(v_count, 0);
END; $$;

-- Attempt cancel proposal only if no votes exist
CREATE OR REPLACE FUNCTION governance.fn_attempt_cancel_proposal(p_proposal_id uuid)
RETURNS boolean LANGUAGE plpgsql AS $$
DECLARE v_votes int; v_ok boolean := false; BEGIN
    SELECT COUNT(*) INTO v_votes FROM governance.votes WHERE proposal_id = p_proposal_id;
    IF COALESCE(v_votes, 0) = 0 THEN
        UPDATE governance.proposals
        SET status = '已撤案', updated_at = timezone('utc', now())
        WHERE proposal_id = p_proposal_id AND status = '進行中';
        GET DIAGNOSTICS v_votes = ROW_COUNT;
        v_ok := (v_votes = 1);
    END IF;
    RETURN v_ok;
END; $$;

-- Upsert a vote
CREATE OR REPLACE FUNCTION governance.fn_upsert_vote(
    p_proposal_id uuid,
    p_voter_id bigint,
    p_choice text
) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO governance.votes (proposal_id, voter_id, choice)
    VALUES (p_proposal_id, p_voter_id, p_choice)
    ON CONFLICT (proposal_id, voter_id)
    DO UPDATE SET choice = EXCLUDED.choice,
                  updated_at = timezone('utc', now());
END; $$;

-- Fetch tally counts in one row
CREATE OR REPLACE FUNCTION governance.fn_fetch_tally(p_proposal_id uuid)
RETURNS TABLE (
    approve integer,
    reject integer,
    abstain integer,
    total_voted integer
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    WITH counts AS (
        SELECT choice, COUNT(*)::int AS c
        FROM governance.votes WHERE proposal_id = p_proposal_id
        GROUP BY choice
    )
    SELECT
        COALESCE(MAX(CASE WHEN choice = 'approve' THEN c END), 0) AS approve,
        COALESCE(MAX(CASE WHEN choice = 'reject' THEN c END), 0) AS reject,
        COALESCE(MAX(CASE WHEN choice = 'abstain' THEN c END), 0) AS abstain,
        COALESCE(SUM(c), 0) AS total_voted
    FROM counts;
END; $$;

-- List votes detail (voter_id, choice)
CREATE OR REPLACE FUNCTION governance.fn_list_votes_detail(p_proposal_id uuid)
RETURNS TABLE (
    voter_id bigint,
    choice text
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT voter_id, choice
    FROM governance.votes WHERE proposal_id = p_proposal_id
    ORDER BY updated_at;
END; $$;

-- Mark proposal status and optional execution info
CREATE OR REPLACE FUNCTION governance.fn_mark_status(
    p_proposal_id uuid,
    p_status text,
    p_execution_tx_id uuid,
    p_execution_error text
) RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    UPDATE governance.proposals
    SET status = p_status,
        execution_tx_id = p_execution_tx_id,
        execution_error = p_execution_error,
        updated_at = timezone('utc', now())
    WHERE proposal_id = p_proposal_id;
END; $$;

-- List due proposals (進行中 且 deadline <= now)
CREATE OR REPLACE FUNCTION governance.fn_list_due_proposals()
RETURNS TABLE (
    proposal_id uuid,
    guild_id bigint,
    proposer_id bigint,
    target_id bigint,
    amount bigint,
    description text,
    attachment_url text,
    snapshot_n integer,
    threshold_t integer,
    deadline_at timestamptz,
    status text,
    reminder_sent boolean,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- Qualify columns to avoid ambiguity with OUT params in RETURNS TABLE
    RETURN QUERY
    SELECT p.proposal_id, p.guild_id, p.proposer_id, p.target_id, p.amount, p.description,
           p.attachment_url, p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
           p.reminder_sent, p.created_at, p.updated_at
    FROM governance.proposals AS p
    WHERE p.status = '進行中' AND p.deadline_at <= timezone('utc', now());
END; $$;

-- List reminder candidates (24h to deadline and not reminded)
CREATE OR REPLACE FUNCTION governance.fn_list_reminder_candidates()
RETURNS TABLE (
    proposal_id uuid,
    guild_id bigint,
    proposer_id bigint,
    target_id bigint,
    amount bigint,
    description text,
    attachment_url text,
    snapshot_n integer,
    threshold_t integer,
    deadline_at timestamptz,
    status text,
    reminder_sent boolean,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- Qualify columns to avoid ambiguity with OUT params in RETURNS TABLE
    RETURN QUERY
    SELECT p.proposal_id, p.guild_id, p.proposer_id, p.target_id, p.amount, p.description,
           p.attachment_url, p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
           p.reminder_sent, p.created_at, p.updated_at
    FROM governance.proposals AS p
    WHERE p.status = '進行中'
      AND p.reminder_sent = false
      AND p.deadline_at - interval '24 hours' <= timezone('utc', now());
END; $$;

-- List active proposals
CREATE OR REPLACE FUNCTION governance.fn_list_active_proposals()
RETURNS TABLE (
    proposal_id uuid,
    guild_id bigint,
    proposer_id bigint,
    target_id bigint,
    amount bigint,
    description text,
    attachment_url text,
    snapshot_n integer,
    threshold_t integer,
    deadline_at timestamptz,
    status text,
    reminder_sent boolean,
    created_at timestamptz,
    updated_at timestamptz
) LANGUAGE plpgsql AS $$
BEGIN
    -- Qualify columns to avoid ambiguity with OUT params in RETURNS TABLE
    RETURN QUERY
    SELECT p.proposal_id, p.guild_id, p.proposer_id, p.target_id, p.amount, p.description,
           p.attachment_url, p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
           p.reminder_sent, p.created_at, p.updated_at
    FROM governance.proposals AS p
    WHERE p.status = '進行中'
    ORDER BY p.created_at;
END; $$;

-- Mark reminded
CREATE OR REPLACE FUNCTION governance.fn_mark_reminded(p_proposal_id uuid)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    UPDATE governance.proposals
    SET reminder_sent = true,
        updated_at = timezone('utc', now())
    WHERE proposal_id = p_proposal_id;
END; $$;

-- Export proposals within interval with aggregated votes and snapshot JSON
CREATE OR REPLACE FUNCTION governance.fn_export_interval(
    p_guild_id bigint,
    p_start timestamptz,
    p_end timestamptz
)
RETURNS TABLE (
    proposal_id uuid,
    guild_id bigint,
    proposer_id bigint,
    target_id bigint,
    amount bigint,
    description text,
    attachment_url text,
    snapshot_n integer,
    threshold_t integer,
    deadline_at timestamptz,
    status text,
    execution_tx_id uuid,
    execution_error text,
    created_at timestamptz,
    updated_at timestamptz,
    votes json,
    snapshot json
) LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT p.proposal_id, p.guild_id, p.proposer_id, p.target_id, p.amount, p.description,
           p.attachment_url, p.snapshot_n, p.threshold_t, p.deadline_at, p.status,
           p.execution_tx_id, p.execution_error, p.created_at, p.updated_at,
           COALESCE(v.votes, '[]'::json) AS votes,
           COALESCE(s.snapshot, '[]'::json) AS snapshot
    FROM governance.proposals p
    LEFT JOIN LATERAL (
        SELECT json_agg(
                   json_build_object(
                       'voter_id', v.voter_id,
                       'choice', v.choice,
                       'created_at', v.created_at,
                       'updated_at', v.updated_at
                   ) ORDER BY v.updated_at
               ) AS votes
        FROM governance.votes v
        WHERE v.proposal_id = p.proposal_id
    ) v ON TRUE
    LEFT JOIN LATERAL (
        SELECT json_agg(ps.member_id) AS snapshot
        FROM governance.proposal_snapshots ps
        WHERE ps.proposal_id = p.proposal_id
    ) s ON TRUE
    WHERE p.guild_id = p_guild_id AND p.created_at >= p_start AND p.created_at < p_end
    ORDER BY p.created_at;
END; $$;

-- List unvoted members for a proposal
CREATE OR REPLACE FUNCTION governance.fn_list_unvoted_members(p_proposal_id uuid)
RETURNS SETOF bigint LANGUAGE plpgsql AS $$
BEGIN
    RETURN QUERY
    SELECT ps.member_id
    FROM governance.proposal_snapshots ps
    WHERE ps.proposal_id = p_proposal_id
      AND NOT EXISTS (
          SELECT 1 FROM governance.votes v
          WHERE v.proposal_id = ps.proposal_id AND v.voter_id = ps.member_id
      )
    ORDER BY ps.member_id;
END; $$;
