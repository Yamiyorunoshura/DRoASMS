-- Trigger function to emit NOTIFY payloads for adjustment transactions.

CREATE OR REPLACE FUNCTION economy.fn_notify_adjustment()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
    v_payload jsonb;
BEGIN
    IF NEW.direction IN ('adjustment_grant', 'adjustment_deduct') THEN
        v_payload := jsonb_build_object(
            'event_type', 'adjustment_success',
            'transaction_id', NEW.transaction_id,
            'guild_id', NEW.guild_id,
            'admin_id', NEW.initiator_id,
            'target_id', NEW.target_id,
            'amount', NEW.amount,
            'direction', NEW.direction,
            'reason', NEW.reason,
            'metadata', NEW.metadata
        );
        PERFORM pg_notify('economy_events', v_payload::text);
    END IF;
    RETURN NULL;
END;
$$;

