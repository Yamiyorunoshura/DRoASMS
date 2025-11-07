-- Trigger function to initiate transfer checks when a pending transfer is created
CREATE OR REPLACE FUNCTION economy.trigger_pending_transfer_check()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    -- Update status to checking
    UPDATE economy.pending_transfers
    SET status = 'checking',
        updated_at = timezone('utc', clock_timestamp())
    WHERE transfer_id = NEW.transfer_id;

    -- Trigger async checks
    PERFORM economy.fn_check_transfer_balance(NEW.transfer_id);
    PERFORM economy.fn_check_transfer_cooldown(NEW.transfer_id);
    PERFORM economy.fn_check_transfer_daily_limit(NEW.transfer_id);

    RETURN NEW;
END;
$$;

-- Create trigger
DROP TRIGGER IF EXISTS trigger_pending_transfer_check ON economy.pending_transfers;
CREATE TRIGGER trigger_pending_transfer_check
    AFTER INSERT ON economy.pending_transfers
    FOR EACH ROW
    EXECUTE FUNCTION economy.trigger_pending_transfer_check();
