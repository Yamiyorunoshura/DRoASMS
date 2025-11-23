# Change: Ensure Integration Test Configurations in Docker

## Why
Currently, integration tests are skipped when required environment variables are not set in the Docker test environment. Specifically, tests check for `RUN_DISCORD_INTEGRATION_TESTS` and `TEST_DISCORD_TOKEN`/`DISCORD_TOKEN`, but the Docker Compose test service doesn't explicitly provide these configurations. This causes integration tests to be silently skipped, reducing test coverage and making it unclear when tests are not running.

## What Changes
- Update `compose.yaml` test service to set `RUN_DISCORD_INTEGRATION_TESTS=1` directly in the environment section (not in `.env`)
- Ensure `TEST_DISCORD_TOKEN` and `DISCORD_TOKEN` can be passed from host environment when running tests (via `docker compose run -e TEST_DISCORD_TOKEN=... test integration`)
- Keep test-specific configurations out of `.env` file (which is used for production)
- Update test service environment configuration to explicitly include all required integration test variables only in Docker Compose

## Impact
- Affected specs: `test-infrastructure`
- Affected code:
  - `compose.yaml` - Update test service environment configuration to set `RUN_DISCORD_INTEGRATION_TESTS=1` and allow passing `TEST_DISCORD_TOKEN`/`DISCORD_TOKEN` from host
