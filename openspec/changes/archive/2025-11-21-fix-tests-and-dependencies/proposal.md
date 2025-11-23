# Change: Fix Test Failures and Update Dependencies

## Why
Recent technical debt analysis revealed critical blocking issues preventing the test suite from running and multiple outdated dependencies with security vulnerabilities. The `Suspect` import error is blocking 29 test files from collection, and 18 dependencies require updates including major version jumps.

## What Changes
- **CRITICAL FIX**: Resolve Cython import error for `Suspect` class in `src/cython_ext/council_governance_models.pyx:8`
- Update pytest configuration to include missing `contract` marker definition
- Update 18 outdated dependencies with focus on ruff (0.5.7→0.7.3) and pytest ecosystem
- Address 8 security vulnerabilities identified in dependency scanning
- Clean up minor code quality issues (unused MyPy ignore comment)
- Validate all compatibility after dependency updates

## Impact
- **Affected specs**: test-infrastructure, development-tooling
- **Affected code**:
  - `src/cython_ext/council_governance_models.pyx` (missing Suspect class)
  - `src/bot/services/justice_service.py:8` (failing import)
  - `src/cython_ext/state_council_models.pyx` (contains Suspect-related classes)
  - `pyproject.toml` (pytest markers and dependency versions)
  - `src/infra/retry.py:31` (unused type ignore)

**BREAKING**: Potential breaking changes from major dependency updates (ruff, pytest) - will verify compatibility during implementation.

## Validation Criteria
- All 29 test files can be collected successfully
- pytest runs without `contract` marker warnings
- All dependencies updated without breaking changes
- Security vulnerabilities resolved
- MyPy strict mode passes without unused ignores
- Full test suite passes (98%+ coverage maintained)
