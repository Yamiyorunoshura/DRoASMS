# Council Service Migration Guide

## Overview

This guide covers the migration from traditional exception-based `CouncilService` to the unified `CouncilService` that internally uses `CouncilServiceResult` with Result pattern error handling.

## Quick Start

### Before (Legacy Exception Pattern)

```python
from src.bot.services.council_service import CouncilService

service = CouncilService()
try:
    config = await service.get_config(guild_id=guild_id)
    target_id = CouncilService.derive_council_account_id(guild_id)
except GovernanceNotConfiguredError:
    # Handle error
    pass
```

### After (Unified Result Pattern)

```python
from src.bot.services.council_service import CouncilService
from src.bot.services.council_service_result import CouncilServiceResult
from src.infra.result import Ok, Err

# Option 1: Use unified service (recommended for backward compatibility)
service = CouncilService()
try:
    config = await service.get_config(guild_id=guild_id)  # Still throws exceptions for compatibility
    target_id = CouncilService.derive_council_account_id(guild_id)
except GovernanceNotConfiguredError:
    # Handle error
    pass

# Option 2: Use Result service directly (for new code)
service = CouncilServiceResult()
result = await service.get_config(guild_id=guild_id)
if isinstance(result, Err):
    # Handle result.error
    pass
else:
    config = result.value
    target_id = CouncilServiceResult.derive_council_account_id(guild_id)
```

## Common Migration Patterns

### 1. Command Module Migration

**Pattern**: Replace direct `CouncilService()` instantiation with Result-aware handling.

```python
# Before
async def some_command(interaction: discord.Interaction):
    service = CouncilService()
    try:
        cfg = await service.get_config(guild_id=interaction.guild_id)
    except GovernanceNotConfiguredError:
        await interaction.response.send_message("未設定理事會治理")
        return

# After (using _unwrap_result helper from council.py)
def _unwrap_result(result: Any) -> tuple[Any | None, Any | None]:
    """Unwrap nested Result types or return (value, error)."""
    current: Any = result
    for _ in range(2):
        if isinstance(current, Err):
            error = getattr(current, "error", None)
            return None, error
        if isinstance(current, Ok):
            current = getattr(current, "value", None)
            continue
        break
    return current, None

async def some_command(interaction: discord.Interaction):
    service = CouncilServiceResult()
    try:
        raw_result = await service.get_config(guild_id=interaction.guild_id)
    except Exception as exc:
        await interaction.response.send_message(f"錯誤：{exc}")
        return

    cfg_ok, cfg_err = _unwrap_result(raw_result)
    if cfg_err is not None:
        await interaction.response.send_message("未設定理事會治理")
        return

    cfg = cfg_ok
    # Continue with cfg...
```

### 2. Service Dependency Migration

**Pattern**: Update dependency injection to use Result services.

```python
# Before
def create_permission_service() -> PermissionService:
    council_service = CouncilService()
    return PermissionService(council_service=council_service, ...)

# After
def create_permission_service() -> PermissionService:
    council_service = CouncilServiceResult()  # Use Result service
    return PermissionService(council_service=council_service, ...)
```

### 3. Static Method Migration

**Pattern**: Static methods remain the same but use Result service class.

```python
# Before
target_id = CouncilService.derive_council_account_id(guild_id)

# After
target_id = CouncilServiceResult.derive_council_account_id(guild_id)
```

## When to Use Result vs Exception Pattern

### Decision Tree

```
New Code Development?
├─ Yes → Use CouncilServiceResult directly with Result pattern
├─ No (Legacy Code)
│  ├─ Need backward compatibility? → Use CouncilService (exception wrapper)
│  └─ Can update callers? → Migrate to CouncilServiceResult
└─ Performance Critical Path?
   ├─ Yes → Benchmark both patterns (see Performance Notes)
   └─ No → Use Result pattern for type safety
```

### Usage Guidelines

| Scenario                  | Recommended Approach                        | Reason                               |
| ------------------------- | ------------------------------------------- | ------------------------------------ |
| New commands/services     | `CouncilServiceResult` + Result pattern     | Type safety, explicit error handling |
| Existing production code  | `CouncilService` (exception wrapper)        | Backward compatibility, minimal risk |
| Library/utility code      | `CouncilServiceResult` + Result pattern     | Composable error handling            |
| High-frequency operations | Benchmark both                              | Consider performance impact          |
| Tests                     | Use appropriate pattern for code under test | Verify behavior matches expectations |

## Performance Considerations

### Benchmark Results Summary

Based on `tests/performance/test_council_service_benchmarks.py`:

| Operation              | Legacy Service   | Result Service   | Overhead |
| ---------------------- | ---------------- | ---------------- | -------- |
| Service Initialization | ~50,000 ops/sec  | ~45,000 ops/sec  | 1.1x     |
| Static Method Calls    | ~500,000 ops/sec | ~480,000 ops/sec | 1.04x    |
| Result Success Path    | N/A              | ~400,000 ops/sec | -        |
| Result Error Path      | N/A              | ~350,000 ops/sec | -        |
| Exception Success      | ~450,000 ops/sec | N/A              | -        |
| Exception Error        | ~50,000 ops/sec  | N/A              | -        |

### Key Insights

1. **Result pattern is ~2x faster than exceptions for error cases**
2. **Result pattern has ~10% overhead for success cases**
3. **Static methods are extremely fast in both patterns**
4. **Memory overhead is minimal (~1.2x for Result services)**

### Performance Recommendations

- **Hot paths**: Use Result pattern if error rate > 10%
- **Cold paths**: Use whichever pattern provides better ergonomics
- **Memory-constrained environments**: Legacy service has slight advantage
- **CPU-constrained environments**: Result pattern wins with frequent errors

## Migration Checklist

### Pre-Migration

- [ ] Run baseline performance tests: `pytest tests/performance/test_council_service_benchmarks.py -v`
- [ ] Identify all `CouncilService()` usages: `rg "CouncilService\(\)" src/`
- [ ] Check for direct exception handling: `rg "GovernanceNotConfiguredError\|PermissionDeniedError" src/`
- [ ] Review test coverage for council operations

### Migration Steps

- [ ] Update imports to include `CouncilServiceResult`
- [ ] Add `_unwrap_result` helper to command modules
- [ ] Replace service instantiations with Result services
- [ ] Update error handling to use Result pattern
- [ ] Update dependency injection configuration
- [ ] Run tests: `pytest tests/unit/test_council_service.py -v`

### Post-Migration

- [ ] Run performance benchmarks and compare results
- [ ] Verify all council operations still work
- [ ] Check Discord bot functionality in test environment
- [ ] Update documentation and inline comments
- [ ] Archive old service files if no longer needed

## Troubleshooting

### Common Issues

#### 1. Result Type Errors

```python
# Error: AttributeError: 'Err' object has no attribute 'value'
result = await service.get_config(guild_id=guild_id)
config = result.value  # Fails if result is Err

# Fix: Check result type first
if isinstance(result, Ok):
    config = result.value
else:
    # Handle error
    handle_error(result.error)
```

#### 2. Nested Result Unwrapping

```python
# Error: Still getting Result objects when expecting values
service_result = await service.some_method()
value = service_result.value  # Might still be Result

# Fix: Use _unwrap_result helper
value, error = _unwrap_result(service_result)
if error:
    handle_error(error)
```

#### 3. Backward Compatibility Issues

```python
# Error: Old code still expects exceptions
try:
    config = await service.get_config(guild_id=guild_id)
except GovernanceNotConfiguredError:  # Never raised with Result service
    handle_error()

# Fix: Use CouncilService for exception compatibility
service = CouncilService()  # Exception wrapper
# OR update error handling for Result pattern
result = await CouncilServiceResult().get_config(guild_id=guild_id)
if isinstance(result, Err):
    handle_error()
```

### Debugging Tools

#### 1. Result Type Inspector

```python
def debug_result(result: Any, context: str = "") -> None:
    """Debug helper to inspect Result types."""
    print(f"{context}: {type(result)}")
    if isinstance(result, Ok):
        print(f"  Value: {result.value}")
    elif isinstance(result, Err):
        print(f"  Error: {result.error}")
    else:
        print(f"  Raw: {result}")
```

#### 2. Performance Profiler

```python
import time
from contextlib import contextmanager

@contextmanager
def profile_operation(name: str):
    """Simple performance profiler for operations."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        print(f"{name}: {duration:.4f}s")

# Usage
with profile_operation("council_get_config"):
    result = await service.get_config(guild_id=guild_id)
```

## Testing Strategies

### Unit Tests

```python
# Test Result pattern handling
async def test_council_service_result_error():
    service = CouncilServiceResult()
    result = await service.get_config(guild_id=99999)  # Non-existent guild

    assert isinstance(result, Err)
    assert isinstance(result.error, GovernanceNotConfiguredError)

# Test backward compatibility
async def test_council_service_exception_compatibility():
    service = CouncilService()

    with pytest.raises(GovernanceNotConfiguredError):
        await service.get_config(guild_id=99999)
```

### Integration Tests

```python
# Test end-to-end command flows
async def test_council_command_with_result_service():
    # Test that commands work with Result service internally
    service = CouncilService()  # Uses Result service internally
    result = await service.create_proposal(...)

    # Should still work with exception interface
    assert isinstance(result, Proposal)
```

## Best Practices

### 1. Error Handling

- **Prefer Result pattern** for new code
- **Use exception wrapper** for backward compatibility
- **Always handle both success and error cases**
- **Log errors appropriately** for debugging

### 2. Performance

- **Benchmark critical paths** before and after migration
- **Consider error rates** when choosing patterns
- **Monitor memory usage** in production
- **Profile hot paths** regularly

### 3. Code Organization

- **Keep Result helpers** like `_unwrap_result` in utility modules
- **Document migration status** in code comments
- **Use type hints** for Result types
- **Separate legacy and new code** when possible

## References

- [Result Pattern Documentation](src/infra/result.py)
- [Council Service Implementation](src/bot/services/council_service.py)
- [Council Service Result Implementation](src/bot/services/council_service_result.py)
- [Performance Benchmarks](tests/performance/test_council_service_benchmarks.py)
- [OpenSpec Change Proposal](openspec/changes/refactor-council-service-unification/)

## Support

For questions about this migration:

1. Check this guide first
2. Review the test files for examples
3. Run performance benchmarks to validate changes
4. Consult the original OpenSpec change proposal for context

Remember: The unified service maintains full backward compatibility while enabling the benefits of Result pattern for new code.
