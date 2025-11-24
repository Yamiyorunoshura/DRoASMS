## ADDED Requirements
### Requirement: Environment-Specific Container Builds
The system SHALL provide separate Docker container builds for development and production environments with optimized dependency management.

#### Scenario: Development container with full toolchain
- **WHEN** developer executes `make start-dev`
- **THEN** the system builds and starts containers containing all development dependencies including testing frameworks, linting tools, and compilation utilities
- **AND** pgadmin service is included for database management
- **AND** all development tools are available inside the bot container

#### Scenario: Production container with minimal dependencies
- **WHEN** operator executes `make start-prod`
- **THEN** the system builds and starts containers containing only runtime dependencies required for bot operation
- **AND** development tools are excluded to reduce attack surface
- **AND** only bot and postgres services are started in background mode

#### Scenario: Consistent build interface
- **WHEN** developers use either start-dev or start-prod commands
- **THEN** the build process uses consistent Docker layer caching strategy
- **AND** both environments produce functionally equivalent bot behavior
- **AND** environment-specific optimizations are applied transparently

#### Scenario: Development workflow preservation
- **WHEN** developers execute testing or compilation commands in development environment
- **THEN** all required tools (pytest, mypy, black, ruff, Cython, mypyc) are available
- **AND** compilation of performance modules works correctly
- **AND** full test suite can be executed without additional setup

## MODIFIED Requirements
### Requirement: Container-based Deployment
The system SHALL provide Docker containers for all services including bot, database, and tooling, with environment-specific optimization for development and production deployments.

#### Scenario: Development environment startup
- **WHEN** developer runs `make start-dev`
- **THEN** all services start including bot, postgres, and pgadmin
- **AND** containers include complete development toolchain
- **AND** bot container mounts development volumes for live code updates

#### Scenario: Production environment startup
- **WHEN** operator runs `make start-prod`
- **THEN** only essential services start (bot and postgres)
- **AND** containers contain minimal runtime dependencies
- **AND** services run in detached mode with automatic restart policy

#### Scenario: Build optimization
- **WHEN** containers are built for specific environments
- **THEN** development containers include all dependency groups for comprehensive tooling
- **AND** production containers include only runtime dependencies
- **AND** build artifacts are optimized for target environment size and security

#### Scenario: Service health and dependencies
- **WHEN** containers start in any environment
- **THEN** bot container waits for postgres health check before starting
- **AND** database initialization scripts run automatically
- **AND** service startup order is maintained across environments
