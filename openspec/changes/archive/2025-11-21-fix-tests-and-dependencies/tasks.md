## 1. Critical Import Fix
- [x] 1.1 Analyze Suspect class location and usage across codebase
- [x] 1.2 Determine correct fix: add missing class vs update import path
- [x] 1.3 Implement import fix with minimal disruption
- [x] 1.4 Verify all related imports compile correctly

## 2. Dependency Updates
- [x] 2.1 Backup current pyproject.toml dependencies
- [x] 2.2 Update ruff from 0.5.7 to 0.7.x (major version jump)
- [x] 2.3 Update pytest ecosystem dependencies
- [x] 2.4 Update remaining 16 outdated dependencies
- [x] 2.5 Address security vulnerabilities in system packages

## 3. Code Quality Fixes
- [x] 3.1 Add missing pytest contract marker to pyproject.toml
- [x] 3.2 Remove unused MyPy type ignore comment in src/infra/retry.py:31
- [x] 3.3 Validate Black formatting after dependency updates
- [x] 3.4 Run Ruff linting and address any new rule violations

## 4. Validation and Testing
- [x] 4.1 Verify pytest can collect all test files (target: 0 collection errors)
- [x] 4.2 Run pytest without contract marker warnings
- [x] 4.3 Execute full test suite with coverage (target: 98%+ maintained)
- [x] 4.4 Validate MyPy strict mode passes (no errors)
- [x] 4.5 Run pre-commit hooks to ensure code quality gates pass

## 5. Compatibility Verification
- [x] 5.1 Test Discord command functionality after updates
- [x] 5.2 Verify database operations work correctly
- [x] 5.3 Check Cython compilation still functions
- [x] 5.4 Validate mypyc compilation if applicable
- [x] 5.5 Confirm DI container resolves all services without errors

## 6. Final Checks
- [x] 6.1 Confirm no breaking changes in public APIs
- [x] 6.2 Validate all environment variables still respected
- [x] 6.3 Check Docker builds succeed with updated dependencies
- [x] 6.4 Run integrated smoke test of core bot functionality
