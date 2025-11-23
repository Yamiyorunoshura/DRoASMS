## 1. Investigation
- [x] 1.1 Run `make test-integration` and identify skipped tests
- [x] 1.2 Analyze skip reasons for each test
- [x] 1.3 Identify missing configuration (Docker access, environment variables)

## 2. Docker Access Configuration
- [x] 2.1 Mount Docker socket (`/var/run/docker.sock`) to test container in `compose.yaml`
- [x] 2.2 Verify Docker CLI is available in test container (or install if needed)
- [ ] 2.3 Test that `docker compose` commands work from within test container

## 3. Environment Variables
- [x] 3.1 Add `RUN_DOCKER_TESTS=1` to test service environment in `compose.yaml`
- [x] 3.2 Add `TEST_MIGRATION_DB_URL` to test service environment in `compose.yaml` (with default value or allow override from host)
- [x] 3.3 Document these environment variables in comments

## 4. Validation
- [x] 4.1 Run `make test-integration` and verify no tests are skipped (except those requiring Discord token)
- [x] 4.2 Verify tests don't hang when Docker is properly configured
- [x] 4.3 Verify tests clean up Docker Compose resources properly
