# Release Plan: v0.7.0

## Dry-Run Summary

### Version Analysis

**Current State:**
- Current version: `0.6.0` (from `pyproject.toml`)
- Latest tag: `v0.6.0`
- Branch: `main`
- Remote: `origin` (https://github.com/Yamiyorunoshura/DRoASMS.git)

**Staged Changes Analysis:**
- 15 files changed, 830 insertions(+), 50 deletions(-)
- Major architectural refactoring introducing dependency injection infrastructure

### Inferred Version Bump: **MINOR** (0.6.0 → 0.7.0)

**Rationale:**
1. **New Feature Addition**: Comprehensive dependency injection container system
   - New modules: `src/infra/di/__init__.py`, `bootstrap.py`, `container.py`, `lifecycle.py`
   - 235+ lines of new DI container implementation
   - Thread-local scoped instances, lifecycle management, automatic dependency resolution

2. **Significant Refactoring**: Command registration system refactored
   - All command modules updated to accept optional `container` parameter
   - Backward compatible (fallback to direct instantiation)
   - Updated: `adjust.py`, `balance.py`, `council.py`, `state_council.py`, `transfer.py`

3. **Test Infrastructure Enhancement**:
   - New comprehensive test suite: `tests/unit/test_di_container.py` (297 lines)
   - Enhanced test fixtures in `tests/conftest.py`

4. **No Breaking Changes Detected**:
   - Public APIs remain unchanged (Discord slash commands work identically)
   - Backward compatible migration path
   - No BREAKING CHANGE markers in commit messages

### Files That Will Be Updated

1. **pyproject.toml**
   - `version = "0.6.0"` → `version = "0.7.0"`

2. **CHANGELOG.md**
   - New entry for version 0.7.0 with categorized changes

### Release Artifacts

- **Release Branch**: `release/0.7.0`
- **Tag**: `v0.7.0`
- **Commit Message**: `chore(release): v0.7.0`
- **Changelog Entry**: See below

## Changelog Entry

```markdown
## [0.7.0] - 2025-01-27

### Added
- **Dependency Injection Infrastructure**: Introduced comprehensive DI container system
  - New `DependencyContainer` with lifecycle management (singleton, transient, scoped)
  - Automatic dependency resolution with type inference
  - Bootstrap utilities for container initialization
  - Thread-local scoped instances support
  - Comprehensive test coverage

### Changed
- **Command Registration**: Refactored command registration to support dependency injection
  - Commands now accept optional `container` parameter for service resolution
  - Backward compatible: falls back to direct instantiation if container not provided
  - Updated all command modules: `adjust`, `balance`, `council`, `state_council`, `transfer`
- **Bot Initialization**: Integrated DI container bootstrap in bot startup sequence
- **Test Infrastructure**: Enhanced test fixtures with DI container support

### Fixed
- Improved service lifecycle management and resource cleanup
```

## PR Description

```markdown
# Release v0.7.0: Dependency Injection Infrastructure

## Summary

This release introduces a comprehensive dependency injection (DI) container system to improve code organization, testability, and maintainability. The changes are backward compatible and do not affect the public API.

## Changes

### Added
- **Dependency Injection Infrastructure**: Complete DI container implementation
  - `DependencyContainer` class with lifecycle management (singleton, transient, scoped)
  - Automatic dependency resolution with type inference
  - Bootstrap utilities (`bootstrap_container()`)
  - Thread-local scoped instances support
  - Comprehensive unit tests (297 lines)

### Changed
- **Command Registration**: Refactored to support dependency injection
  - All command modules now accept optional `container` parameter
  - Backward compatible fallback to direct instantiation
  - Updated modules: `adjust`, `balance`, `council`, `state_council`, `transfer`
- **Bot Initialization**: Integrated DI container bootstrap in startup sequence
- **Test Infrastructure**: Enhanced fixtures with DI container support

### Technical Details

- **Files Changed**: 15 files (830 insertions, 50 deletions)
- **New Modules**: `src/infra/di/*` (4 new files)
- **Test Coverage**: New comprehensive test suite for DI container

## Version Bump

- **Type**: MINOR (0.6.0 → 0.7.0)
- **Rationale**: New feature addition (DI infrastructure) with significant internal refactoring, no breaking changes

## Testing

- ✅ All existing tests pass
- ✅ New DI container tests added and passing
- ✅ Backward compatibility verified

## Migration Notes

No migration required. The changes are internal and backward compatible. Commands continue to work as before.
```

## Commit Message

```
chore(release): v0.7.0

- Bump version from 0.6.0 to 0.7.0
- Add dependency injection infrastructure
- Refactor command registration to support DI
- Update test infrastructure for DI support

Version bump type: MINOR
```

## Safeguards

1. **Monotonicity Check**: Validates new version is greater than latest tag
2. **Git State Validation**: Ensures clean working directory (unless dry-run)
3. **Manifest Syntax**: Uses standard sed patterns compatible with pyproject.toml format
4. **Idempotency**: Safe to re-run; checks for existing release branch
5. **Error Handling**: Proper exit codes and error messages
6. **Dry-Run Mode**: Test changes without modifying repository

## Execution Plan

1. Run dry-run to verify: `./scripts/release.sh --dry-run`
2. Execute release: `./scripts/release.sh --bump MINOR`
3. Review and merge PR (if using `--pr` flag)
4. Tag will be created automatically on merge

## Notes

- The script supports both direct merge and PR workflows
- Sign-off is enabled by default (can be disabled with `--no-signoff`)
- Tag prefix defaults to `v` (can be customized with `--tag-prefix`)
