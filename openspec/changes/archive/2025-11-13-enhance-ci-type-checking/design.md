# CI Type Checking Enhancement - Design Document

## Context

The DRoASMS project currently uses MyPy for static type checking in strict mode. While the project already has Pyright configured in pyproject.toml with strict mode settings, Pyright is not integrated into the CI pipeline. This creates a gap where potential type errors that Pyright might catch could go undetected in CI.

Additionally, integration tests are not included in the standard `make ci` command, which means local CI checks don't fully match the remote CI environment that includes integration tests.

The project emphasizes type safety with Python 3.13 and strict typing requirements throughout the codebase, making comprehensive type checking essential for maintaining code quality.

## Goals / Non-Goals

**Goals:**
- Provide comprehensive type safety coverage by using both MyPy and Pyright strict mode checking
- Ensure local CI environment matches remote CI environment by including integration tests
- Maintain backward compatibility with existing development workflows
- Minimize CI execution time through parallel job execution
- Leverage existing configuration in pyproject.toml

**Non-Goals:**
- Modify existing type checking configurations (both tools are already configured correctly)
- Change the Python version or dependency management approach
- Alter the integration test implementation or test structure
- Introduce new type checking tools beyond MyPy and Pyright

## Decisions

### Decision: Dual Type Checking Strategy
**What**: Use both MyPy and Pyright in strict mode for comprehensive type coverage
**Why**: Different type checkers catch different types of errors. MyPy is more mature and has better support for certain Python features, while Pyright (developed by Microsoft) has excellent type inference and can catch issues that MyPy might miss. Using both provides the most comprehensive type safety coverage.

**Alternatives considered:**
- **Single type checker (MyPy only)**: Simpler but misses potential issues
- **Single type checker (Pyright only)**: Good type inference but less mature ecosystem
- **Add additional type checkers**: Increased complexity with diminishing returns

### Decision: Parallel Job Execution in CI
**What**: Run MyPy and Pyright jobs in parallel in GitHub Actions
**Why**: Minimizes total CI execution time while providing comprehensive checking. Both type checkers are independent and can run simultaneously.

**Alternatives considered:**
- **Sequential execution**: Simpler but increases total CI time
- **Single job with both tools**: Easier to manage but loses parallelism benefits

### Decision: Integration Test Inclusion
**What**: Include integration tests as part of standard `make ci` execution
**Why**: Ensures local development environment matches remote CI environment. Currently, integration tests run in GitHub Actions but not in local `make ci`, creating potential discrepancies.

**Alternatives considered:**
- **Keep integration tests separate**: Maintains status quo but allows environment drift
- **Make integration tests optional**: Reduces CI time but compromises coverage

### Decision: Leverage Existing Configuration
**What**: Use existing MyPy and Pyright configurations in pyproject.toml
**Why**: Both tools are already properly configured with strict mode and appropriate module exclusions. No need to duplicate configuration or introduce new configuration files.

**Alternatives considered:**
- **Separate configuration files**: More explicit but introduces maintenance overhead
- **Environment-specific configurations**: Complex and error-prone

## Risks / Trade-offs

**Risk**: Increased CI execution time
- **Impact**: Developers wait longer for CI feedback
- **Mitigation**: Parallel job execution, optimized configurations

**Risk**: Conflicting type checker results
- **Impact**: MyPy and Pyright might disagree on certain type issues
- **Mitigation**: Use existing configurations, prioritize strict mode compliance, document any known differences

**Risk**: Integration test environment requirements
- **Impact**: Local development might need additional setup
- **Mitigation**: Docker-based test infrastructure already handles integration test requirements

**Trade-off**: Complexity vs. Coverage
- Adding Pyright increases CI complexity but provides significantly better type coverage
- This is justified given the project's emphasis on type safety and production reliability

## Migration Plan

### Phase 1: Add Pyright to Makefile
1. Add `pyright-check` target to Makefile
2. Update `ci-local` target to include pyright-check
3. Update `ci` target to include integration tests
4. Test local execution

### Phase 2: Add Pyright to GitHub Actions
1. Create new `pyright-check` job in .github/workflows/ci.yml
2. Configure job to run in parallel with existing MyPy job
3. Add proper caching and dependencies
4. Test in fork/feature branch

### Phase 3: Integration Test Enhancement
1. Modify test execution strategy to include integration tests by default
2. Ensure proper resource cleanup and timeout handling
3. Update documentation and help text
4. Validate complete pipeline

### Rollback Steps
If issues arise during implementation:
1. Remove Pyright job from GitHub Actions
2. Remove pyright-check target from Makefile
3. Revert ci-local and ci targets to original state
4. Update documentation accordingly

## Open Questions

1. **Performance Impact**: What will be the actual impact on CI execution time?
   - **Mitigation**: Monitor execution times after implementation
   - **Fallback**: Optimize configurations or adjust parallelization strategy

2. **Type Checker Conflicts**: How to handle disagreements between MyPy and Pyright?
   - **Mitigation**: Document any known differences, prioritize strict compliance
   - **Fallback**: Choose one tool as primary if conflicts become unmanageable

3. **Integration Test Reliability**: Will integration tests be stable in local CI environment?
   - **Mitigation**: Leverage existing Docker-based test infrastructure
   - **Fallback**: Make integration tests opt-out if reliability issues persist

## Implementation Notes

### Configuration Strategy
- Use existing pyproject.toml configurations
- Maintain strict mode for both type checkers
- Preserve existing module exclusions and overrides

### Testing Strategy
- Validate both type checkers pass on current codebase
- Test CI pipeline with sample changes
- Ensure integration test execution works reliably

### Documentation Updates
- Update README.md to reflect dual type checking
- Document purpose of using both MyPy and Pyright
- Update help text in Makefile targets
- Provide troubleshooting guidance for type checker issues
