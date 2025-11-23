# Change: Complete Result Pattern Migration

## Why

The project is currently in a hybrid state regarding error handling:

- Some services use the new `Result<T, E>` pattern (e.g., `CouncilServiceResult`).
- Others use legacy exception-based patterns (e.g., `CouncilService`).
- `TransferService` is internally hybrid (uses `Result` but raises exceptions externally).

This duality violates the "Unique Implementation Source" requirement, increases cognitive load, and duplicates maintenance effort. The previous change `unify-result-error-handling` laid the groundwork, but the actual migration of core services and removal of legacy compatibility layers has not been completed.

## What Changes

### 1. Migrate `TransferService`

- Refactor `TransferService.transfer_currency` to return `Result[TransferResult | UUID, TransferError]` directly.
- Remove logic that unwraps `Result` to raise exceptions.
- Update `src/bot/commands/transfer.py` to handle `Result` returns.

### 2. Unify Service Implementations

- Replace legacy services with their Result-based counterparts:
  - `CouncilService` replaced by `CouncilServiceResult`.
  - `PermissionService` replaced by `PermissionServiceResult`.
  - `StateCouncilService` replaced by `StateCouncilServiceResult`.
  - `SupremeAssemblyService` replaced by `SupremeAssemblyServiceResult`.
- Rename the `*_result` classes to their canonical names (e.g., `CouncilServiceResult` -> `CouncilService`) and delete the old files.

### 3. Update Commands

- Refactor `council`, `state_council`, and `supreme_assembly` commands to remove support for legacy services (checking `if service_result is None`).
- Ensure strict `Result` usage in all command handlers.

### 4. Remove Legacy Compatibility Layer

- Delete `src/common/result.py` and `src/common/errors.py`.
- Remove `src/infra/result_compat.py` if unused, or restrict its scope.

## Impact

### Affected Specifications

- `openspec/specs/error-handling/spec.md`: Remove "Compatibility Layer Boundary" requirement.

### Affected Code

- `src/bot/services/` (Transfer, Council, State, Supreme Assembly)
- `src/bot/commands/` (Transfer, Council, State, Supreme Assembly)
- `src/common/` (Delete `result.py`, `errors.py`)

### Risks

- **Silent Failures**: If a call site expects an exception but receives a `Result` object (which evaluates to `True`), errors might be ignored.
  - _Mitigation_: Comprehensive `grep` search for all service usages and strict type checking (`mypy`).

## Rollout Plan

1.  **Migrate Services**: Swap implementations and rename classes.
2.  **Update Consumers**: Fix all call sites in commands and tests.
3.  **Verify**: Run full test suite and type checks.
4.  **Cleanup**: Delete legacy common modules.
