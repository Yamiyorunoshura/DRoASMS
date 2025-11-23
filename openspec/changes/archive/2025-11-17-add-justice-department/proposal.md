# Change: Add Justice Department Panel and Related Features

## Why
The State Council system lacks a Justice Department, resulting in an incomplete government structure. Adding a Justice Department will complete the governance system and provide suspect management and prosecution capabilities to enhance judicial processes.

## What Changes
- Add a Justice Department tab to the State Council panel
- Grant Justice Department the same economic operation permissions as other departments (transfer funds, adjust balances)
- Add Justice Department-specific suspect management features
- Ensure charged individuals cannot be automatically released by Homeland Security

## Impact
- Affected specs: justice_department_panel, transfer_economics, adjust_economics, suspect_management
- Affected code:
  - State Council UI in `src/bot/commands/state_council.py`
  - Transfer command in `src/bot/commands/transfer.py`
  - Adjust command in `src/bot/commands/adjust.py`
  - Homeland Security release logic in `src/bot/services/homeland_security_service.py`
  - Database schema with new `governance.suspects` table
