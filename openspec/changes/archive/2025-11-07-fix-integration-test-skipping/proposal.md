# Change: Fix Integration Test Skipping

## Why
Integration tests are being skipped due to missing Docker/Compose configuration and missing environment variables. Six integration tests are currently skipped:
1. `test_compose_dependencies.py` - Docker/Compose not available
2. `test_compose_ready.py` - Docker/Compose not available
3. `test_compose_restart_update.py` - Docker/Compose not available
4. `test_db_not_ready_retry.py` - Docker/Compose not available
5. `test_external_db_override.py` - Missing `RUN_DOCKER_TESTS` environment variable
6. `test_migration_failure_exit_code.py` - Missing `TEST_MIGRATION_DB_URL` environment variable

These tests require Docker CLI access from within the test container to run `docker compose` commands. Additionally, some tests require specific environment variables that are not configured in `compose.yaml`.

## What Changes
- **MODIFIED**: Test container configuration to provide Docker CLI access (via Docker socket mounting or Docker-in-Docker)
- **MODIFIED**: `compose.yaml` test service to include missing environment variables (`RUN_DOCKER_TESTS`, `TEST_MIGRATION_DB_URL`)
- **MODIFIED**: Test infrastructure requirements to ensure all integration tests can run without being skipped (when prerequisites like Discord token are provided)

## Impact
- **Affected specs**: `test-infrastructure`
- **Affected code**:
  - `compose.yaml` (test service configuration)
  - `docker/test.Dockerfile` (if Docker CLI needs to be installed)
  - Integration tests will no longer be skipped due to missing Docker/Compose access or missing environment variables
