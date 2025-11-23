## 1. Update Docker Compose Configuration
- [x] 1.1 Update `compose.yaml` test service to set `RUN_DISCORD_INTEGRATION_TESTS=1` directly in the `environment` section (not in `.env`)
- [x] 1.2 Ensure `TEST_DISCORD_TOKEN` and `DISCORD_TOKEN` can be passed from host environment using Docker Compose's environment variable passthrough (e.g., `docker compose run -e TEST_DISCORD_TOKEN=... test integration`)
- [x] 1.3 Add comments in `compose.yaml` explaining that test-specific configurations are set here, not in `.env` (to keep production config clean)
- [x] 1.4 Verify that all integration test environment variables are available in the test container without requiring `.env` modifications

## 2. Validation
- [x] 2.1 Run integration tests via `docker compose run test integration` to verify no tests are skipped due to missing `RUN_DISCORD_INTEGRATION_TESTS`
- [x] 2.2 Verify that tests requiring `RUN_DISCORD_INTEGRATION_TESTS` execute successfully
- [x] 2.3 Verify that tests requiring `TEST_DISCORD_TOKEN`/`DISCORD_TOKEN` can receive them via host environment (e.g., `TEST_DISCORD_TOKEN=token docker compose run test integration`)
- [x] 2.4 Verify that tests skip gracefully with clear message if `TEST_DISCORD_TOKEN`/`DISCORD_TOKEN` not provided (not due to missing `RUN_DISCORD_INTEGRATION_TESTS`)
- [x] 2.5 Verify that `.env` file remains clean and does not require test-specific configurations
