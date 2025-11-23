# CI Type Checking Enhancement - Tasks

## 1. Add Pyright to Makefile
- [x] 1.1 Add pyright-check target to Makefile
- [x] 1.2 Update ci-local target to include pyright-check
- [x] 1.3 Update ci target to include integration tests
- [x] 1.4 Add help text for new targets

## 2. Add Pyright to GitHub Actions
- [x] 2.1 Create pyright-check job in .github/workflows/ci.yml
- [x] 2.2 Configure job to use Python 3.13 container
- [x] 2.3 Set up uv installation and dependency sync
- [x] 2.4 Configure job to run in parallel with MyPy job
- [x] 2.5 Add appropriate caching for uv dependencies

## 3. Integration Test Enhancement
- [x] 3.1 Modify test execution to include integration tests by default
- [x] 3.2 Ensure integration tests run in docker/bin/test.sh ci command
- [x] 3.3 Validate integration test inclusion in CI pipeline
- [x] 3.4 Verify test failures properly cause CI to fail

## 4. Documentation Updates
- [x] 4.1 Update README.md to reflect dual type checking strategy
- [x] 4.2 Document purpose of using both MyPy and Pyright
- [x] 4.3 Add instructions for local development workflow
- [x] 4.4 Update Makefile help text

## 5. Validation and Testing
- [x] 5.1 Run full CI pipeline to ensure all checks pass
- [x] 5.2 Verify both MyPy and Pyright execute successfully
- [x] 5.3 Confirm integration tests run and pass
- [x] 5.4 Check that all jobs complete successfully in GitHub Actions
- [x] 5.5 Monitor CI execution time after changes
