# Change: Add Pyright Type Checking and Integration Tests to CI

## Why
Enhance CI type safety by leveraging Pyright strict mode checking (already configured) alongside existing MyPy, and ensure local CI environment matches remote CI by including integration tests in standard CI execution.

## What Changes
- Add Pyright strict mode checking to Makefile and GitHub Actions
- Include integration tests in `make ci` command execution
- Add Pyright job to GitHub Actions workflow running in parallel with MyPy
- Update CI documentation to reflect dual type checking strategy

## Impact
- **Affected specs**: test-infrastructure (MODIFIED)
- **Affected code**: Makefile, .github/workflows/ci.yml, docker/bin/test.sh
- **Breaking changes**: None (backward compatible)
