# Result<T,E> Pattern Migration Guide

This guide helps you migrate from traditional exception-based error handling to the new Rust-style Result<T,E> pattern in DRoASMS.

## Overview

The Result pattern provides:
- **Type safety**: Errors are part of the type system
- **Explicit error handling**: You must handle errors explicitly
- **Better composability**: Errors can be chained and transformed
- **Reduced exceptions**: Less try/except boilerplate

## Quick Start

### Canonical Import Paths
- **唯一入口**：所有 Result / Error 型別 MUST 從 `src.infra.result` 匯入。
- **Legacy 相容層**：`src.common.errors` 與 `src.common.result` 僅 re-export 權威型別並在載入時記錄遷移警告；請勿在新檔案中使用。
- **相容工具**：若暫時需要例外樣式 API，請使用 `src.infra.result_compat` 的 helper（`wrap_function`、`CompatibilityZone` 等），並在 PR 中標註 legacy 區域。
- **靜態檢查**：Pyright 型別註記應直接引用 `src.infra.result` 中的型別，以維持單一來源的一致性。

### Basic Result Types

```python
from src.infra.result import Result, Ok, Err, Ok, Err

def divide(a: int, b: int) -> Result[float, ValidationError]:
    if b == 0:
        return Err(ValidationError("Cannot divide by zero"))
    return Ok(a / b)

# Usage
result = divide(10, 2)
if result.is_ok():
    print(f"Result: {result.unwrap()}")
else:
    print(f"Error: {result.unwrap_err()}")
```

### Common Patterns

#### 1. Chaining Operations
```python
# Before (exceptions)
def process_data(data):
    try:
        validated = validate(data)
        transformed = transform(validated)
        saved = save(transformed)
        return saved
    except Exception as e:
        logger.error(f"Processing failed: {e}")
        raise

# After (Result pattern)
def process_data(data: str) -> Result[SavedData, Error]:
    return (
        validate(data)
        .and_then(transform)
        .and_then(save)
        .map_err(lambda e: logger.error(f"Processing failed: {e}") or e)
    )
```

#### 2. Handling Different Error Types
```python
from src.infra.result import Result, DatabaseError, ValidationError, BusinessLogicError

def create_user(data: dict) -> Result[User, ValidationError | DatabaseError]:
    # Validate input
    if not data.get("email"):
        return Err(ValidationError("Email is required"))

    # Check business rules
    if len(data["email"]) > 100:
        return Err(BusinessLogicError("Email too long"))

    # Save to database (might return DatabaseError)
    return save_user_to_db(data)
```

#### 3. Async Operations
```python
from src.infra.result import AsyncResult, async_returns_result

@async_returns_result(DatabaseError)
async def fetch_user(user_id: int) -> User:
    # Database operation that might fail
    return await db.fetch_user(user_id)

# Usage
async def main():
    result = await fetch_user(123)
    if result.is_ok():
        user = result.unwrap()
        print(f"Found user: {user.name}")
```

## Migration Steps

### Step 1: Identify Code to Migrate

Use the migration analyzer:
```bash
python scripts/migrate_to_result.py src/bot/services/ --priority high
```

### Step 2: Convert Simple Cases First

Start with functions that:
- Have simple validation logic
- Return success/failure status
- Don't have complex exception hierarchies

Example:
```python
# Before
def validate_age(age: int) -> bool:
    if age < 0:
        raise ValueError("Age cannot be negative")
    if age > 150:
        raise ValueError("Age seems unrealistic")
    return True

# After
def validate_age(age: int) -> Result[bool, ValidationError]:
    if age < 0:
        return Err(ValidationError("Age cannot be negative"))
    if age > 150:
        return Err(ValidationError("Age seems unrealistic"))
    return Ok(True)
```

### Step 3: Update Callers

Update code that calls migrated functions:

```python
# Before
try:
    is_valid = validate_age(user_age)
    process_user(user_data)
except ValueError as e:
    show_error(str(e))

# After
result = validate_age(user_age)
if result.is_err():
    show_error(str(result.unwrap_err()))
else:
    process_user(user_data)
```

### Step 4: Handle Async Code

For async functions, use AsyncResult:

```python
# Before
async def fetch_data():
    try:
        async with db.transaction():
            data = await db.fetch()
            return process_data(data)
    except DatabaseError as e:
        logger.error(f"Fetch failed: {e}")
        raise

# After
async def fetch_data() -> Result[ProcessedData, DatabaseError]:
    async with db.transaction():
        result = await db.fetch_result()  # Returns AsyncResult
        return await result.map(process_data)

### Example: Service 與指令如何回傳 Result

```python
from src.infra.result import Result, DatabaseError, async_returns_result

class TaxationService:
    def __init__(self, gateway: TaxGateway) -> None:
        self._gateway = gateway

    @async_returns_result(DatabaseError)
    async def issue_tax(self, guild_id: int, amount: int) -> TaxRecord:
        record = await self._gateway.insert_tax(guild_id=guild_id, amount=amount)
        return record


async def run_command(service: TaxationService, guild_id: int) -> None:
    result = await service.issue_tax(guild_id, 100)
    if result.is_err():
        await respond_ephemeral(f"稅務失敗：{result.unwrap_err().message}")
        return
    await respond_success(f"稅務成功，單號 {result.unwrap().record_id}")
```
```

## Error Handling Guidelines

### Use Appropriate Error Types

```python
from src.infra.result import (
    ValidationError,      # For input validation
    DatabaseError,        # For database operations
    BusinessLogicError,   # For business rule violations
    SystemError,          # For system-level issues
    DiscordError,         # For Discord API errors
)
```

### Provide Context

```python
def fetch_user(user_id: int) -> Result[User, DatabaseError]:
    try:
        user = await db.fetch_user(user_id)
        if user is None:
            return Err(DatabaseError(
                message=f"User {user_id} not found",
                context={"user_id": user_id, "table": "users"}
            ))
        return Ok(user)
    except asyncpg.PostgresError as e:
        return Err(DatabaseError(
            message="Database query failed",
            context={"sqlstate": e.sqlstate, "query": "SELECT * FROM users WHERE id = $1"},
            cause=e
        ))
```

### Chain Operations Safely

```python
def process_order(order_data: dict) -> Result[Order, Error]:
    return (
        validate_order_data(order_data)
        .and_then(check_inventory)
        .and_then(reserve_items)
        .and_then(create_order)
        .and_then(process_payment)
        .map_err(log_error)  # Log any error that occurs
    )
```

## Common Pitfalls

### 1. Don't Mix Patterns
Avoid mixing exceptions and Results:

```python
# Bad
async def bad_function() -> Result[Data, Error]:
    if invalid_input:
        raise ValueError("Invalid input")  # Don't raise in Result-returning functions
    return Ok(data)

# Good
async def good_function() -> Result[Data, Error]:
    if invalid_input:
        return Err(ValidationError("Invalid input"))
    return Ok(data)
```

### 2. Handle All Error Cases
Don't unwrap without checking:

```python
# Bad
result = risky_operation()
data = result.unwrap()  # Might raise!

# Good
result = risky_operation()
if result.is_ok():
    data = result.unwrap()
    process(data)
else:
    error = result.unwrap_err()
    handle_error(error)
```

### 3. Use map/map_err for Transformations
```python
# Bad
if result.is_ok():
    value = result.unwrap()
    transformed = transform(value)
    return Ok(transformed)

# Good
return result.map(transform)
```

## Testing

### Test Success and Error Cases
```python
import pytest
from src.infra.result import Ok, Err, ValidationError

def test_divide_success():
    result = divide(10, 2)
    assert result.is_ok()
    assert result.unwrap() == 5.0

def test_divide_by_zero():
    result = divide(10, 0)
    assert result.is_err()
    error = result.unwrap_err()
    assert isinstance(error, ValidationError)
    assert str(error) == "Cannot divide by zero"
```

### Use Result in Test Fixtures
```python
@pytest.fixture
def test_user() -> Result[User, ValidationError]:
    return create_user({
        "name": "Test User",
        "email": "test@example.com"
    })
```

## Compatibility Layer

During migration, use the compatibility layer:

```python
from src.infra.result_compat import migrate_step1, adapt_result_for_exception_code

# Step 1: Wrap existing functions
@migrate_step1(exceptions=(ValueError, TypeError))
def legacy_function(x: int) -> int:
    if x < 0:
        raise ValueError("x must be positive")
    return x * 2

# Step 2: Gradually update callers
result = legacy_function(5)  # Still throws, but internally uses Result

# Step 3: For functions returning Result that need to work with legacy code
result = new_result_function()
try:
    value = adapt_result_for_exception_code(result)
    # Use value in legacy code
except Exception as e:
    # Handle error in legacy way
```

## Migration Checklist

- [ ] Run analyzer on codebase: `python scripts/migrate_to_result.py src/`
- [ ] Identify high-priority files (many try/except blocks)
- [ ] Start with simple validation functions
- [ ] Update service layer methods
- [ ] Add @async_returns_result to async database operations
- [ ] Update command handlers
- [ ] Test error cases thoroughly
- [ ] Update documentation
- [ ] Train team on new patterns
- [ ] Monitor for issues post-deployment

## Further Reading

- [Rust Result Documentation](https://doc.rust-lang.org/std/result/)
- [Railway Oriented Programming](https://fsharpforfunandprofit.com/posts/recipe-part2/)
- [Error Handling in Functional Programming](https://elm-lang.org/news/the-perfect-bug-report)

## Support

For questions or issues with migration:
1. Check existing examples in `src/bot/services/`
2. Run `python -m pytest tests/unit/test_result_types.py` to verify setup
3. Review error logs for compatibility warnings
4. Contact the development team

---

Remember: Migration is gradual. Use the compatibility layer when needed, and prioritize the most critical error paths first. Happy migrating! 🚀

## Migration Tools

### 1. Migration Analyzer
Analyze your code for migration opportunities:
```bash
# Analyze specific files
python scripts/migrate_to_result.py src/bot/commands/transfer.py src/bot/commands/adjust.py

# Analyze entire directories
python scripts/migrate_to_result.py src/bot/services/ --priority high

# Generate detailed report
python scripts/migrate_to_result.py src/ --output migration_report.md
```

### 2. Compatibility Layer
Use during gradual migration:
```python
from src.infra.result_compat import (
    migrate_step1,           # Step 1: Internal Result usage
    adapt_result_for_exception_code,  # Temporary adapter
    CompatibilityZone,       # Mark legacy sections
    mark_migrated,           # Track progress
)
```

### 3. Migration Tracker
Track your migration progress:
```python
from src.infra.result_compat import get_migration_report

print(get_migration_report())
# Shows percentage migrated, remaining items, etc.
```

## Best Practices Summary

1. **Start Small**: Begin with simple functions
2. **Be Consistent**: Don't mix patterns in the same function
3. **Provide Context**: Always include helpful error context
4. **Test Thoroughly**: Test both success and error paths
5. **Use Tools**: Leverage migration tools and analyzers
6. **Document**: Update docstrings to reflect Result returns
7. **Train Team**: Ensure everyone understands the new patterns
8. **Monitor**: Watch for issues after deployment

## Troubleshooting

### Common Issues

1. **"Called unwrap on Err value"**
   - Always check `is_ok()` before `unwrap()`
   - Use `unwrap_or(default)` for safe defaults

2. **Type checking errors**
   - Ensure proper type annotations: `Result[T, E]`
   - Use specific error types, not generic `Error`

3. **Async/await confusion**
   - Use `AsyncResult` for async operations
   - Remember to `await` AsyncResult operations

4. **Forgot to handle errors**
   - Use linters to catch unhandled Results
   - Consider using `# noqa` comments sparingly

### Getting Help

1. Check this guide
2. Look at existing examples
3. Run tests to verify behavior
4. Ask in team channels
5. Create minimal reproduction examples

---

*This guide is living documentation. Please update it as patterns evolve and new lessons are learned.*

Last updated: 2025-01-17
Version: 1.0.0
