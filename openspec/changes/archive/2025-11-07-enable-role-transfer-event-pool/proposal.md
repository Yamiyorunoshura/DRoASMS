# Change: Enable Role Transfer in Event Pool

## Why
現有的轉帳事件池架構已支援一般使用者之間的轉帳，但尚未完整支援使用者與政府部門、理事會的身分組轉帳。雖然規範要求支援國務院領袖身分組轉帳，但實際代碼中缺少此功能。此外，需要確保事件池模式能正確處理所有類型的身分組轉帳，並補足相關單元測試以確保功能正確性。

## What Changes
- **補足國務院領袖身分組轉帳支援**：在 `/transfer` 指令中新增對國務院領袖身分組的處理，將其映射至國務院主帳戶
- **新增國務院主帳戶 ID 推導方法**：在 `StateCouncilService` 中新增 `derive_main_account_id` 靜態方法
- **確保事件池模式支援所有身分組轉帳**：驗證並確保事件池模式能正確處理理事會、國務院領袖、部門領導人身分組的轉帳
- **補足單元測試**：新增針對身分組轉帳（特別是事件池模式）的單元測試

## Impact
- **Affected specs**: `economy-commands`
- **Affected code**:
  - `src/bot/commands/transfer.py` - 新增國務院領袖身分組處理邏輯
  - `src/bot/services/state_council_service.py` - 新增主帳戶 ID 推導方法
  - `tests/unit/test_transfer_command.py` - 新增身分組轉帳測試
  - `tests/unit/test_transfer_event_pool.py` - 新增事件池模式身分組轉帳測試
