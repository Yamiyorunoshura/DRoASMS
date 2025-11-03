-- Test fn_check_transfer_balance
BEGIN;

-- Setup: Create a pending transfer and set up balances
INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
VALUES 
    (123456789, 111111111, 500),  -- Sufficient balance
    (123456789, 222222222, 0);

SELECT economy.fn_create_pending_transfer(
    123456789::bigint,
    111111111::bigint,
    222222222::bigint,
    200::bigint,  -- Less than balance (500)
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id;

-- Get the transfer_id (in real test, we'd capture this)
DO $$
DECLARE
    v_transfer_id uuid;
BEGIN
    SELECT transfer_id INTO v_transfer_id
    FROM economy.pending_transfers
    WHERE initiator_id = 111111111
    ORDER BY created_at DESC
    LIMIT 1;

    -- Update status to checking manually (trigger would do this)
    UPDATE economy.pending_transfers
    SET status = 'checking'
    WHERE transfer_id = v_transfer_id;

    -- Test balance check
    PERFORM economy.fn_check_transfer_balance(v_transfer_id);
END $$;

-- Verify check result
SELECT 
    transfer_id,
    status,
    checks->>'balance' AS balance_check
FROM economy.pending_transfers
WHERE initiator_id = 111111111;

-- Test 2: Insufficient balance
INSERT INTO economy.guild_member_balances (guild_id, member_id, current_balance)
VALUES (123456789, 333333333, 50);

SELECT economy.fn_create_pending_transfer(
    123456789::bigint,
    333333333::bigint,
    444444444::bigint,
    200::bigint,  -- More than balance (50)
    '{}'::jsonb,
    NULL::timestamptz
) AS transfer_id_2;

DO $$
DECLARE
    v_transfer_id uuid;
BEGIN
    SELECT transfer_id INTO v_transfer_id
    FROM economy.pending_transfers
    WHERE initiator_id = 333333333
    ORDER BY created_at DESC
    LIMIT 1;

    UPDATE economy.pending_transfers
    SET status = 'checking'
    WHERE transfer_id = v_transfer_id;

    PERFORM economy.fn_check_transfer_balance(v_transfer_id);
END $$;

-- Verify insufficient balance check
SELECT 
    transfer_id,
    checks->>'balance' AS balance_check
FROM economy.pending_transfers
WHERE initiator_id = 333333333;

ROLLBACK;

