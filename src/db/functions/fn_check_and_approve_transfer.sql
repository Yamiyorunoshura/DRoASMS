-- Internal helper function to check if all checks passed and approve transfer
CREATE OR REPLACE FUNCTION economy._check_and_approve_transfer(p_transfer_id uuid)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
    v_guild_id bigint;
    v_initiator_id bigint;
    v_target_id bigint;
    v_amount bigint;
BEGIN
    -- 以單一原子 UPDATE 判斷所有檢查是否通過，並從 checking 轉為 approved。
    -- 若並行呼叫，僅會有 1 筆能成功更新（避免重複核准與重複通知）。
    UPDATE economy.pending_transfers pt
    SET status = 'approved',
        updated_at = timezone('utc', now())
    WHERE pt.transfer_id = p_transfer_id
      AND pt.status = 'checking'
      AND (pt.checks->>'balance') IS NOT NULL
      AND (pt.checks->>'cooldown') IS NOT NULL
      AND (pt.checks->>'daily_limit') IS NOT NULL
      AND (pt.checks->>'balance')::int = 1
      AND (pt.checks->>'cooldown')::int = 1
      AND (pt.checks->>'daily_limit')::int = 1;

    IF NOT FOUND THEN
        RETURN; -- 不是 checking 狀態或尚未全部通過，或已被其他交易更新
    END IF;

    -- 取出必要欄位以便通知（這裡不需要 FOR UPDATE，因為狀態已更新為 approved）
    SELECT guild_id, initiator_id, target_id, amount
    INTO v_guild_id, v_initiator_id, v_target_id, v_amount
    FROM economy.pending_transfers
    WHERE transfer_id = p_transfer_id;

    -- 發送核准事件
    PERFORM pg_notify(
        'economy_events',
        jsonb_build_object(
            'event_type', 'transfer_check_approved',
            'transfer_id', p_transfer_id,
            'guild_id', v_guild_id,
            'initiator_id', v_initiator_id,
            'target_id', v_target_id,
            'amount', v_amount
        )::text
    );
END;
$$;
