## Context
The `DependencyContainer` uses a threading lock (`threading.Lock`) to ensure thread-safe singleton creation. The current implementation acquires the lock and holds it while calling the factory function:

```python
with self._lock:
    if service_type in self._singletons:
        return self._singletons[service_type]
    instance = factory()  # Lock held here
    self._singletons[service_type] = instance
    return instance
```

The factory function (created by `_create_auto_factory`) recursively calls `self.resolve()` for constructor dependencies. If those dependencies are also singletons, they attempt to acquire the same lock, causing a deadlock.

## Goals / Non-Goals
- **Goals**:
  - Eliminate deadlock in singleton resolution
  - Maintain thread-safety for singleton creation
  - Preserve existing API and behavior
  - Ensure circular dependency detection still works correctly
- **Non-Goals**:
  - Changing the lifecycle API
  - Adding new lifecycle types
  - Modifying the factory creation logic

## Decisions
- **Decision**: Use reentrant lock (`threading.RLock`) instead of regular lock
  - **Rationale**: Factory execution may need to resolve other singletons, which requires the lock. A reentrant lock allows the same thread to acquire the lock multiple times, preventing deadlock while maintaining thread-safety. This is the standard solution for recursive locking scenarios.
  - **Alternatives considered**:
    1. **Release lock before factory, re-acquire for storage**: Could lead to race conditions where multiple threads create instances simultaneously, requiring complex double-checked locking with potential for wasted work.
    2. **Lock-free double-checked locking**: More complex, requires careful memory ordering considerations and doesn't solve the recursive locking issue.
    3. **Separate lock for factory execution**: Adds complexity without clear benefit and doesn't solve the fundamental recursive locking need.
  - **Chosen approach**: Replace `threading.Lock` with `threading.RLock`:
    ```python
    # In __init__:
    self._lock = threading.RLock()  # Changed from threading.Lock()

    # In _resolve_singleton (no other changes needed):
    with self._lock:
        if service_type in self._singletons:
            return self._singletons[service_type]
        instance = factory()  # Can now recursively acquire lock
        self._singletons[service_type] = instance
        return instance
    ```

## Risks / Trade-offs
- **Risk**: RLock allows same thread to acquire lock multiple times, which could mask bugs
  - **Mitigation**: This is the intended behavior for recursive resolution. The circular dependency detection (`_resolving` set) still prevents infinite loops, and RLock is the standard solution for this pattern.
- **Risk**: Slight performance overhead from RLock vs regular Lock
  - **Mitigation**: Minimal impact - RLock has negligible overhead compared to regular Lock, and this only affects singleton creation (subsequent resolutions are lock-free).
- **Trade-off**: Simplicity vs. perfect optimization
  - **Chosen**: Simplicity - RLock is the standard, well-understood solution for recursive locking scenarios and requires minimal code changes.

## Migration Plan
- No migration needed - this is a bug fix that restores correct behavior
- Existing code using the container will benefit immediately
- No API changes required

## Open Questions
- None - the solution is straightforward and well-understood
