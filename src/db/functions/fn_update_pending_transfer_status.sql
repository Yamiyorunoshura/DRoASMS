-- Update pending transfer status
CREATE OR REPLACE FUNCTION economy.fn_update_pending_transfer_status(
    p_transfer_id uuid,
    p_new_status text
)
RETURNS void
LANGUAGE plpgsql
AS $$
BEGIN
    IF p_new_status NOT IN ('pending', 'checking', 'approved', 'completed', 'rejected') THEN
        RAISE EXCEPTION 'Invalid status: %. Must be one of: pending, checking, approved, completed, rejected', p_new_status
            USING ERRCODE = '22023';
    END IF;

    UPDATE economy.pending_transfers
    SET status = p_new_status,
        updated_at = timezone('utc', clock_timestamp())
    WHERE transfer_id = p_transfer_id;
END;
$$;
