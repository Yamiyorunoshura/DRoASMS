# Design: Result Pattern Migration

## Context

The project currently operates in a hybrid state regarding error handling. While the `Result<T, E>` pattern has been introduced (`add-result-error-handling`), legacy exception-based patterns persist in core services (`CouncilService`, `TransferService`). This inconsistency violates the "Unique Implementation Source" requirement, complicates maintenance, and creates confusion for developers.

### Constraints

- Must maintain full backward compatibility for existing data.
- Must pass strict `mypy` type checking.
- Must not introduce new runtime dependencies.

## Goals / Non-Goals

- **Goals**:

  - Establish `src.infra.result` as the single authority for error handling.
  - Eliminate legacy exception-based service methods in favor of `Result` returns.
  - Ensure `TransferService` consistently uses `Result` for all domain errors.
  - Remove legacy compatibility layers (`src.common.result`, `src.common.errors`).

- **Non-Goals**:
  - Refactoring the internal implementation of `src.infra.result`.
  - Changing the database schema or migration logic.
  - Modifying unrelated services (e.g., `SuspectService`) unless they depend on legacy patterns.

## Decisions

### 1. TransferService In-Place Migration

**Decision**: Refactor `TransferService` directly to return `Result` instead of creating a temporary `_result` subclass.
**Reasoning**: `TransferService` already uses `Result` internally. Creating a subclass would be redundant. We will modify the return signatures and remove the exception-raising logic in a single atomic step.

### 2. Swap-and-Rename for Governance Services

**Decision**: For `CouncilService`, `StateCouncilService`, etc., which already have parallel `_result.py` implementations, we will delete the legacy file and rename the `_result.py` file to the canonical name.
**Reasoning**: The `_result` implementations are already verified. Swapping them ensures a clean cutover and preserves the file history of the new implementation (mostly).

### 3. Command Handler Strictness

**Decision**: Command handlers must explicitly handle `Ok`/`Err` cases. No `try/except` blocks for domain errors (like `GovernanceNotConfiguredError`) should remain.
**Reasoning**: This enforces the `Result` pattern at the UI boundary, ensuring all errors are handled consciously.

## Risks / Trade-offs

- **Risk**: Call sites expecting exceptions might silently ignore `Result` error objects (which evaluate to `True`).
  - **Mitigation**: Comprehensive regex search for all service usages. Strict `mypy` checks will catch type mismatches (e.g., `Result` vs `int`).
- **Risk**: Temporary breakage during the "Swap-and-Rename" phase.
  - **Mitigation**: The tasks are ordered to update consumers (commands) immediately after or alongside service updates.

## Migration Plan

### Phase 1: TransferService (Critical Path)

1.  Refactor `TransferService.transfer_currency`.
2.  Update `transfer` command.

### Phase 2: Governance Services

1.  Swap `CouncilService`.
2.  Swap `StateCouncilService`.
3.  Swap `SupremeAssemblyService`.
4.  Swap `PermissionService`.
5.  Update associated commands.

### Phase 3: Cleanup

1.  Remove `src.common.result` and `src.common.errors`.
2.  Verify no imports remain.
