# Project Context

## Purpose
DRoASMS is a Discord bot prototype built with Python, focused on community economy systems and governance processes. The bot provides:

- **Virtual Currency System**: Complete in-community economy with point transfers, balance queries, and transaction history
- **Transfer System**: Members can transfer virtual currency to each other with optional notes
- **Administrative Controls**: Authorized administrators can adjust member points (add or deduct)
- **Council Governance**: Proposal and voting system for council-managed transfers
- **State Council Governance**: Department-based governance system with currency issuance and transfers
- **Supreme Peoples Assembly (最高人民會議)**: Server-wide governance body with proposal, voting, and summons capabilities
- **Homeland Security Panel (國土安全部)**: Suspect management system for managing arrested users with automatic release scheduling
- **Justice Department (法務部)**: Legal system governance capabilities
- **Transfer Event Pool**: Asynchronous transfer processing with automatic retry mechanisms
- **Result Error Handling**: Rust-style Result<T,E> error handling pattern for type-safe error management

The project emphasizes reliability, ACID transactions, production-ready implementations without mocks, and provides multiple governance layers for different organizational needs.

## Active Migrations

### Result<T,E> Error Handling Migration (In Progress)
**Change ID**: `add-result-error-handling`
**Status**: Active implementation
**Scope**: Migrating all error handling from traditional try/except to Rust-style Result<T,E> pattern

**Affected Systems**:
- All service layers (`src/bot/services/`)
- All gateway layers (`src/db/gateway/`)
- Discord command handlers (`src/bot/commands/`)
- Economy-commands, council-governance, state-council-governance specs

**Migration Strategy**:
- New methods return `Result[T, ErrorType]` or `AsyncResult[T, ErrorType]`
- Existing methods maintained for backward compatibility
- Gradual migration with comprehensive test coverage
- Integration with structlog for error context

**Key Features**:
- Type-safe error handling with compiler support
- Hierarchical error types (DatabaseError, DiscordError, ValidationError)
- Rich error context with query parameters and stack traces
- Chaining methods: `.map()`, `.and_then()`, `.unwrap_or()`

**Timeline**: Ongoing - targeting completion in next milestone

## Tech Stack

### Core Runtime
- **Python 3.13** (pinned via `uv python pin 3.13`)
- **discord.py** (2.4.0+): Discord API integration
- **asyncpg** (0.30.0+): Async PostgreSQL driver
- **SQLAlchemy** (2.0.30+): ORM and database abstraction
- **Alembic** (1.13.0+): Database migrations
- **structlog** (24.1.0+): Structured logging (JSON Lines output)
- **Pydantic** (2.0.0+): Settings validation and configuration management
- **tenacity** (9.0.0+): Retry logic with exponential backoff
- **mypyc**: Python-to-C compilation for critical performance paths
- **Cython**: C extensions for performance-critical code in governance modules

### Infrastructure
- **PostgreSQL 15+**: Primary database with required extensions:
  - `pgcrypto`: UUID/hashing support (recommended)
  - `pg_cron`: Automated archival (optional, required for migration 004+)
- **Docker & Docker Compose**: Containerized development and deployment
- **uv**: Package management and virtual environment (recommended)

### Development Tools
- **pytest** (8.3.0+): Test framework with async support
- **pytest-asyncio**: Async test support
- **pytest-cov**: Coverage reporting
- **pytest-xdist**: Parallel test execution (`-n auto`)
- **hypothesis** (6.0.0+): Property-based testing
- **faker** (30.0.0+): Test data generation
- **mypy** (1.11.0+): Static type checking (strict mode)
- **ruff** (0.6.0+): Fast Python linter
- **black** (24.8.0+): Code formatter
- **pre-commit**: Git hooks for quality checks
- **dpy-ext-paginator**: Discord.py paginator for enhanced UI components
- **coverage-threshold**: Enforces minimum test coverage requirements (98%+ for critical modules)

### Build & Compilation
- **mypyc**: Ahead-of-time Python-to-C compilation for performance
- **Cython**: C extensions for performance optimization
- **unified-compilation-config**: Standardized compilation configuration across modules
- **CI compilation**: Automated binary builds in CI pipeline
- **performance-benchmarks**: Pytest-based performance regression testing

## Project Conventions

### Code Style
- **Line Length**: 100 characters
- **Python Version**: 3.13 (strict typing required)
- **Type Hints**: Required throughout codebase (mypy strict mode enabled)
- **Formatting**: Black with 100-char line length
- **Linting**: Ruff with selected rules (E, F, I, ASYNC, B, C4)
- **Import Style**: Absolute imports from `src.*` namespace
- **Future Imports**: Use `from __future__ import annotations` for forward references

### Architecture Patterns

#### Dependency Injection
- Custom DI container (`src/infra/di/container.py`) with lifecycle management:
  - `SINGLETON`: One instance shared across application
  - `FACTORY`: New instance on each resolution
  - `THREAD_LOCAL`: One instance per thread
- Automatic dependency inference from constructor type hints
- Bootstrap function (`src/infra/di/bootstrap.py`) registers all services
- Commands accept optional `container` parameter for DI (backward compatible)
- **Result Containers**: Type-safe container resolution with Result<T,E> pattern

#### Layered Architecture
- **Commands Layer** (`src/bot/commands/`): Discord slash command handlers
- **Services Layer** (`src/bot/services/`): Business logic and orchestration
- **Result Services** (`src/bot/services/*_result.py`): Type-safe service wrappers using Result<T,E>
- **Gateway Layer** (`src/db/gateway/`): Database access abstraction
- **Database Layer** (`src/db/`): Migrations, pool management, SQL functions

#### Database Patterns
- **Gateway Pattern**: Each domain has a gateway class for database operations
- **SQL Functions**: Complex logic implemented in PostgreSQL functions (`src/db/functions/`)
- **Migrations**: Alembic migrations with versioned naming (`001_`, `002_`, etc.)
- **Connection Pooling**: Managed via `src/db/pool.py` with asyncpg
- **Result Pattern**: Database operations return Result<T,E> for type-safe error handling

#### Panel Architecture (UI Components)
- **Standardized Tabs**: All governance panels use tab-based navigation
  - Individual tabs for different governance bodies
  - Department tabs for State Council operations
  - Security tabs for Homeland Security operations
- **Modal Flows**: Multi-step processes use modal-based interactions
  - Department creation/editing with multi-field forms
  - Transfer confirmation with detailed previews
  - Suspect management with automatic release scheduling
- **Paginator Integration**: Enhanced view components using dpy-ext-paginator
  - Large data sets with pagination support
  - Inline information display with navigation controls
  - Context-aware pagination state management

#### Error Handling Architecture
- **Result<T,E> Pattern**: Rust-style error handling throughout the codebase
  - `Result[T, ErrorType]` for type-safe operations
  - `AsyncResult[T, ErrorType]` for async operations
  - Chaining methods: `.map()`, `.and_then()`, `.unwrap_or()`
- **Hierarchical Error Types**: Specific error categories
  - `DatabaseError` with connection, constraint, query subtypes
  - `DiscordError` with rate limit, auth, permission subtypes
  - `ValidationError` with field-level validation details
- **Error Context**: Rich error information with query parameters, stack traces, and operational context
- **Integration Points**: Seamless integration with DI, logging, and Discord commands

#### Event-Driven Architecture
- **Transfer Event Pool**: Asynchronous transfer processing using PostgreSQL NOTIFY/LISTEN
- **Event Types**: Defined in `src/infra/events/` (council_events, state_council_events)
- **Telemetry**: Structured event logging via `TelemetryListener`
- **Role-based Events**: Event processing respects role permissions and governance rules

### Testing Strategy

#### Test Organization
- **Unit Tests** (`tests/unit/`): Fast, isolated tests for individual components (85%+ coverage target)
- **Integration Tests** (`tests/integration/`): End-to-end tests requiring Docker/Discord (gated by `RUN_DISCORD_INTEGRATION_TESTS`)
- **Contract Tests** (`tests/contracts/`): SQL function and database contract validation
- **Performance Tests** (`tests/performance/`): Load and performance validation (NFR markers)
- **Database Tests** (`tests/db/`): SQL function tests and database behavior validation
- **Cython Tests**: Specific tests for Cython extensions
- **mypyc Tests**: Performance benchmarks for compiled modules

#### Test Execution
- **Parallel Execution**: Default `-n auto` (detects CPU cores)
- **Test Containers**: Docker-based test environment for consistency (`docker/test.Dockerfile`)
- **Coverage**: HTML reports in `htmlcov/`, term output with missing lines
- **Coverage Threshold**: 98%+ coverage required for critical modules (economy, governance)
- **Timeout**: 300 seconds default (configurable via `PYTEST_TIMEOUT_SECONDS`)
- **CI Integration**: Full test suite runs with coverage gates in CI pipeline

#### Test Data
- **Faker**: Generate realistic test data (guild_id, user_id, amounts)
- **Hypothesis**: Property-based testing for complex logic (balance validation, transfers)
- **Fixtures**: Shared fixtures in `tests/conftest.py` (database pool, DI container)
- **Performance Fixtures**: Mock data sets for load testing

#### Test Quality Gates
- **Type Checking**: mypy strict mode passes (no errors)
- **Linting**: ruff passes with configured rules (E, F, I, ASYNC, B, C4)
- **Formatting**: black formatting validated
- **Pre-commit**: All hooks pass before commit
- **Compilation Tests**: mypyc and Cython builds succeed
- **Integration Tests**: All integration tests pass before merge

#### Test Markers
- `@pytest.mark.integration`: Requires external services
- `@pytest.mark.performance`: Performance/load tests
- `@pytest.mark.timeout`: Custom timeout markers

### Git Workflow
- **Pre-commit Hooks**: Automatic formatting and linting on commit
- **CI Checks**: Format check, lint, type check, and pre-commit validation
- **Changelog**: Keep a Changelog format (see `CHANGELOG.md`)
- **Versioning**: Semantic Versioning (see `pyproject.toml` version)

### Code Quality Gates
- **Format Check**: `black --check` (no modifications)
- **Lint**: `ruff check` (with auto-fix option)
- **Type Check**: `mypy src/` (strict mode)
- **Pre-commit**: All hooks must pass
- **Tests**: All tests must pass (excluding integration tests in default CI)

## Domain Context

### Economy System
- **Currency**: Virtual points (configurable name/icon per server via `/currency_config`)
- **Accounts**: Per-user, per-guild accounts stored in PostgreSQL
- **Transfers**: Member-to-member transfers with optional reason/notes
- **Adjustments**: Admin-only point adjustments (positive or negative)
- **History**: Transaction history with pagination (30-day retention, then archival)

### Rate Limiting
- **Daily Transfer Limit**: Configurable via `TRANSFER_DAILY_LIMIT` (default: unlimited)
- **Cooldown**: 5-minute cooldown after frequent transfers
- **Balance Protection**: Prevents negative balances

### Transfer Event Pool
- **Asynchronous Processing**: Transfers enter queue for async execution
- **Automatic Retry**: Exponential backoff (up to 10 retries) for failed checks
- **Event-Driven**: PostgreSQL NOTIFY/LISTEN for decoupled check/execute phases
- **Enablement**: Set `TRANSFER_EVENT_POOL_ENABLED=true` (default: false for backward compatibility)
- **Role-based Events**: Event pool respects role-specific configurations

### Governance Systems

#### Council Governance (理事會)
- **Proposals**: Council members create transfer proposals (max 5 active per guild)
- **Voting**: DM-based voting with buttons (approve/reject/abstain)
- **Threshold**: `floor(N/2) + 1` where N = council snapshot at proposal creation
- **Timeline**: 72-hour voting window with 24-hour reminder
- **Execution**: Automatic transfer attempt when threshold reached
- **Panel**: Interactive management panel (`/council_panel`)

#### State Council Governance (國務院)
- **Departments**: Department-based organization with leaders, tax rates, issuance limits
- **Currency Issuance**: State Council can issue currency to departments
- **Department Transfers**: Departments transfer to members via government accounts
- **Exemptions**: Government transfers exempt from cooldown and daily limits
- **Panel**: Interactive department management panel (`/state_council_panel`)
- **Role-based Permissions**: Configurable per-department access controls

#### Supreme Peoples Assembly (最高人民會議)
- **Account**: Server-wide account with deterministic ID generation
- **Transfer Capabilities**: Can transfer to users, council, government departments
- **Proposals**: Table-based proposals with content, amount, and purpose
- **Voting**: 3-option voting (approve/reject/abstain) with snapshot immutability
- **Threshold**: `floor(N/2) + 1` where N = members at proposal creation
- **Timeline**: 72-hour voting window with 24-hour reminder
- **Anonymity then Disclosure**: Anonymous during voting, disclosed after completion
- **Summons**: Power to summon council members or government officials via DM
- **Panel**: Interactive proposal management and voting interface

#### Homeland Security Panel (國土安全部)
- **Suspect Management**: View, release, and schedule automatic release of arrested users
- **Arrest Records**: Persistent storage of arrest details with reasons and timestamps
- **Release Mechanisms**: Manual single/multi-release and automatic timed release
- **Release Scheduling**: Configurable automatic release (1-168 hours)
- **Audit Trail**: Complete history of all arrest and release operations
- **Panel**: Specialized management interface for security operations
- **Role-based Access**: Multi-tier homeland security role configuration

#### Justice Department (法務部)
- **Legal System**: Legal governance and compliance management
- **Role Configuration**: Configurable justice-related role assignments
- **Integration**: Works with other governance bodies for legal oversight

### Database Schema
- **Multi-Guild Support**: Each Discord guild has isolated economy system
- **ACID Transactions**: All operations use database transactions
- **Automatic Archival**: 30-day transaction archival (requires `pg_cron`)
- **SQL Functions**: Complex validation and business logic in PostgreSQL
- **Role Storage**: Configurable role mappings for all governance bodies
- **Governance Records**: Proposal, voting, and decision history with full audit trails

## Important Constraints

### Production Environment
- **No Mocks**: Production code MUST use real implementations (no mock data or fake endpoints)
- **Real Integrations**: All external services (Discord API, database, third-party) must use real endpoints and authentication
- **Environment Separation**: Development mocks must be clearly marked and disabled in production
- **Validation**: If mocks are needed for development, must provide explicit environment configuration (`DEVELOPMENT_MODE=true`)
- **Performance**: Critical paths MUST support mypyc/Cython compilation
- **Result Pattern**: All service operations MUST return Result<T,E> (active transition, backward compatibility maintained)
- **Error Handling**: All operations MUST handle errors using Result<T,E> pattern (comprehensive error handling required)

### Technical Constraints
- **Python 3.13**: Strict version requirement (pinned via `uv`)
- **PostgreSQL Extensions**: `pgcrypto` recommended, `pg_cron` required for full feature set
- **Discord Intents**: Must enable `members` intent for governance features (role membership snapshots)
- **Async/Await**: All I/O operations must be async (asyncpg, discord.py)
- **Type Safety**: mypy strict mode enabled, no type errors allowed
- **Compilation**: Critical modules must support mypyc/Cython compilation
- **Error Propagation**: Result<T,E> pattern must be used for all new service methods

### Performance Targets
- **Startup Time**: Bot ready signal (`bot.ready` event) within 60 seconds (P95 ≤ 120 seconds)
- **Database Connections**: Connection pooling required (no direct connections)
- **Parallel Testing**: Tests must support parallel execution (use independent connection pools)
- **Panel Response**: UI panel interactions must respond within 2 seconds (P95)
- **Governance Operations**: Proposal creation/voting operations must complete within 1 second
- **Compilation Performance**: mypyc/Cython compiled modules must show measurable performance improvement

### Security Constraints
- **Role-based Permissions**: All governance operations MUST enforce role-based access control
- **Audit Trail**: All administrative operations MUST generate audit logs
- **Input Validation**: All user inputs MUST be validated and sanitized
- **Rate Limiting**: API operations MUST respect Discord rate limits
- **Error Sanitization**: Production error messages MUST NOT expose implementation details

## External Dependencies

### Discord API
- **Service**: Discord Bot API via discord.py
- **Authentication**: Bot token via `DISCORD_TOKEN` environment variable
- **Intents**: `guilds` and `members` intents required
- **Rate Limits**: Handled by discord.py library
- **Webhooks**: Not currently used
- **Buttons/Components**: Interactive UI via Discord message components

### PostgreSQL Database
- **Connection**: Via `DATABASE_URL` environment variable
- **Format**: `postgresql://user:password@host:port/database`
- **Extensions**: `pgcrypto` (recommended), `pg_cron` (optional, required for archival)
- **Connection Pooling**: Managed by asyncpg pool
- **Migrations**: Alembic manages schema versioning
- **Advanced Features**: NOTIFY/LISTEN for event-driven architecture

### Environment Variables

#### Core Configuration
- **Required**:
  - `DISCORD_TOKEN`: Discord bot authentication token
  - `DATABASE_URL`: PostgreSQL connection string
- **Guild Configuration**:
  - `DISCORD_GUILD_ALLOWLIST`: Comma-separated guild IDs (whitelist)
- **Feature Flags**:
  - `TRANSFER_EVENT_POOL_ENABLED`: Enable async transfer processing (default: `false`)
  - `TRANSFER_DAILY_LIMIT`: Daily transfer limit per user (default: unlimited if 0 or unset)
- **Database & Migration**:
  - `ALEMBIC_UPGRADE_TARGET`: Target migration version (default: `head`)
  - `PGADMIN_PORT`: pgAdmin port for dev profile (default: `8081`)
- **Performance & Compilation**:
  - `MYPYC_BUILD_DIR`: Build directory for mypyc compiled modules
  - `CYTHON_BUILD_DIR`: Build directory for Cython extensions
  - `PERFORMANCE_BENCHMARK_MODE`: Enable performance comparison mode
- **Development Mode**:
  - `DEVELOPMENT_MODE`: Enable development-only features (default: `false`)
  - `DEBUG_SQL`: Log SQL queries (default: `false`)
  - `MOCK_DISCORD_API`: Use Discord API mocks (for testing only)

#### Test Configuration
- **Test Execution**:
  - `RUN_DISCORD_INTEGRATION_TESTS`: Enable Discord integration tests (default: `false`)
  - `PYTEST_TIMEOUT_SECONDS`: Test timeout duration (default: `300`)
  - `PYTEST_PARALLEL_WORKERS`: Number of parallel workers (default: `-n auto`)
- **Test Data**:
  - `TEST_SEED`: Random seed for reproducible test data
  - `TEST_DISCORD_GUILD_ID`: Test guild ID for integration tests
  - `TEST_DISCORD_USER_ID`: Test user ID for authenticated operations

#### Security Configuration
- **Rate Limiting**:
  - `GOVERNANCE_RATE_LIMIT_PER_USER`: Max operations per user per minute (default: `10`)
  - `TRANSFER_RATE_LIMIT_PER_USER`: Max transfers per user per minute (default: `20`)
- **Audit Logging**:
  - `AUDIT_LOG_CHANNEL_ID`: Discord channel for audit logs
  - `AUDIT_LOG_LEVEL`: Log level for audit events (default: `INFO`)

### Docker Services
- **postgres**: PostgreSQL 15+ with extensions (pgcrypto, pg_cron)
- **bot**: Main application container
- **pgadmin**: Database admin UI (dev profile only)
- **test**: Test execution container with pytest and dependencies
- **benchmark**: Performance testing container (benchmark profile)

### Third-Party Services
- **mypyc**: Python-to-C compilation service for performance optimization
- **Cython**: C extension compiler
- **pytest-xdist**: Distributed testing infrastructure
- **structlog**: Structured logging aggregation (JSON Lines format)
- **alembic**: Database migration management
