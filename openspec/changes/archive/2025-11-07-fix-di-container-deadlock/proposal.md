## Why
The dependency injection container's singleton resolution holds a threading lock while executing factory functions. When factories recursively resolve dependencies that are also singletons, those dependencies attempt to acquire the same lock, causing a deadlock. This manifests as unit tests hanging indefinitely, particularly in tests that exercise circular dependency detection or complex dependency graphs.

## What Changes
- **MODIFIED**: Singleton resolution lock management to prevent deadlocks
- **MODIFIED**: Factory execution now occurs outside the critical section
- **ADDED**: Reentrant lock support or lock release before factory execution
- **ADDED**: Test coverage for concurrent singleton resolution scenarios

## Impact
- Affected specs: `dependency-injection` (when archived)
- Affected code:
  - `src/infra/di/container.py` - Lock management in `_resolve_singleton`
  - `tests/unit/test_di_container.py` - May need additional concurrent test cases
- Risk: Low - This is a bug fix that restores correct behavior
