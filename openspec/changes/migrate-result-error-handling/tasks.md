## 1. Migrate TransferService

- [ ] 1.1 Refactor `src/bot/services/transfer_service.py` to return `Result`
- [ ] 1.2 Update `src/bot/commands/transfer.py` to handle `Result` returns
- [ ] 1.3 Verify `TransferService` no longer raises domain exceptions externally

## 2. Unify Service Implementations

- [ ] 2.1 Replace `CouncilService` with `CouncilServiceResult` implementation
- [ ] 2.2 Replace `PermissionService` with `PermissionServiceResult` implementation
- [ ] 2.3 Replace `StateCouncilService` with `StateCouncilServiceResult` implementation
- [ ] 2.4 Replace `SupremeAssemblyService` with `SupremeAssemblyServiceResult` implementation
- [ ] 2.5 Delete `src/bot/services/*_result.py` files

## 3. Update Commands

- [ ] 3.1 Update `src/bot/commands/council.py` to remove legacy compatibility mode
- [ ] 3.2 Update `src/bot/commands/state_council.py` to remove legacy compatibility mode
- [ ] 3.3 Update `src/bot/commands/supreme_assembly.py` to remove legacy compatibility mode
- [ ] 3.4 Verify all commands consume `Result` types correctly

## 4. Cleanup and Verification

- [ ] 4.1 Remove `src/common/result.py`
- [ ] 4.2 Remove `src/common/errors.py`
- [ ] 4.3 Verify no imports of legacy common modules remain
- [ ] 4.4 Run strict type checking (mypy)
- [ ] 4.5 Run full test suite
