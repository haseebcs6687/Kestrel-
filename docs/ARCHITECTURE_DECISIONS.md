# Architecture Decision Records (ADRs)

### ADR 001: Modular Monolith Architecture
- **Status**: Accepted
- **Context**: Kestrel needs clear domain boundaries (auth, ingest, analytics, providers) developed, tested, and maintained by a single engineer without the operational complexity of distributed microservices.
- **Decision**: Build Kestrel as a modular monolith within a single codebase where modules interact via clean service contracts rather than internal network calls.
- **Consequences**: Greatly simplifies deployment, testing, and debugging; enforces domain encapsulation so any module can be extracted into an independent microservice later if scale demands.

### ADR 002: Ingest-API-First Telemetry Without Gateway Proxy
- **Status**: Accepted
- **Context**: Tracking LLM metrics could be implemented either by proxying every LLM call through a gateway or by having client apps send telemetry directly to an ingest API.
- **Decision**: Implement an ingest-first telemetry API (`POST /ingest/events`) accompanied by a lightweight client wrapper, rather than building an inline proxy gateway.
- **Consequences**: Telemetry records exact client-measured tokens and latency without Kestrel becoming a single point of failure in the inference critical path; Kestrel never needs to store customer provider keys for inference.

### ADR 003: PostgreSQL as Unified Datastore (No Redis or TimescaleDB at MVP)
- **Status**: Accepted
- **Context**: LLM telemetry involves time-series metrics, transactional configuration, and analytical aggregations, which could tempt multi-database architectures.
- **Decision**: Use a single PostgreSQL database leveraging native indexing, `percentile_cont`, and scheduled rollup tables for analytical queries.
- **Consequences**: Minimizes operational overhead and infrastructure complexity during MVP; avoids dual-write synchronization bugs; can revisit TimescaleDB or Redis when measured throughput necessitates.

### ADR 004: Synchronous SQLAlchemy 2.x with Async HTTPX for Outbound Calls
- **Status**: Accepted
- **Context**: FastAPI supports asynchronous database drivers, but async ORM code increases debugging complexity, connection pool subtleties, and test harness fragility.
- **Decision**: Use synchronous SQLAlchemy 2.x (2.1.9 locked) with the 2.0-style typed API (`Mapped`, `mapped_column`) and Alembic for all database operations, while using async `httpx` for outbound provider health probes and model queries.
- **Consequences**: Delivers reliable, straightforward database transactions and debugging; outbound network I/O remains non-blocking for background tasks.

### ADR 005: Separate Worker Process with APScheduler
- **Status**: Accepted
- **Context**: Periodic tasks (provider health checks, alert rule evaluations, aggregation rollups, data retention) must run reliably without degrading API request throughput.
- **Decision**: Run a separate worker process executing APScheduler, sharing the same domain models and database connection pool with the API process.
- **Consequences**: Isolates scheduled workloads from HTTP API performance without introducing Celery, RabbitMQ, or Redis queue infrastructure; worker failure does not crash the HTTP API.

### ADR 006: Argon2 Password Hashing and Server-Enforced JWT Roles
- **Status**: Accepted
- **Context**: The platform requires secure user authentication and strict authorization separation between administrative operators and read-only viewers.
- **Decision**: Hash passwords with `argon2-cffi` and issue stateless JWT tokens; enforce `admin` and `viewer` permissions server-side on every route and repository query.
- **Consequences**: Robust resistance against GPU-based cracking attacks; client-side role manipulation cannot bypass API authorization boundaries.

### ADR 007: Fernet Symmetric Encryption for Provider Credentials at Rest
- **Status**: Accepted
- **Context**: Users configure upstream provider API keys (Groq, Gemini) for health checks and model discovery that must be kept safe from unauthorized database access.
- **Decision**: Encrypt all stored provider credentials using Fernet symmetric encryption with a master key supplied strictly via environment variables; credentials are never returned by the API or logged.
- **Consequences**: Secures credentials against database snapshot leaks; requires secure management of the master encryption key; prevents frontend exposure after initial submission.

### ADR 008: Metadata-Only Telemetry (Zero Prompt/Response Storage)
- **Status**: Accepted
- **Context**: Logging prompt text and model output text introduces immense data storage overhead, privacy liabilities, and enterprise security compliance hurdles.
- **Decision**: Collect and store only operational metadata (token counts, latency, status codes, error classifications, model names); never store prompt or completion text.
- **Consequences**: Drastically reduces storage requirements, simplifies privacy compliance, and eliminates risk of leaking sensitive user prompts or proprietary IP in telemetry tables.

### ADR 009: Event-Level Price Snapshotting
- **Status**: Accepted
- **Context**: LLM provider token pricing changes over time; calculating historical costs from a mutable current pricing table causes historical reporting to drift retroactively.
- **Decision**: Snapshot the exact effective token price onto each telemetry event record at the time of ingestion.
- **Consequences**: Historical financial analytics and audit trails remain permanently immutable; updates to pricing tables only affect future ingested events.

### ADR 010: React SPA with Tailwind, shadcn/ui, TanStack Query, and ECharts
- **Status**: Accepted
- **Context**: The frontend requires responsive dashboard visualizations, rapid state management, and an accessible, polished user interface.
- **Decision**: Build a React SPA using Vite, TypeScript, Tailwind CSS, shadcn/ui component primitives, TanStack Query for server state, and Apache ECharts; visual direction inspired by Minia's design feel without copying assets.
- **Consequences**: Clean, accessible component system with optimized charting performance; zero licensing risks or third-party proprietary code entanglements.

### ADR 011: Percentiles Computed from Raw Events, Rollups for Counts and Sums
- **Status**: Accepted
- **Context**: Pre-aggregating latency into hourly or daily rollups prevents accurate multi-window percentile calculations (`p50`, `p95`, `p99`) because percentiles cannot be mathematically averaged.
- **Decision**: Retain raw event latency for accurate percentile calculations across arbitrary query windows; restrict rollups exclusively to additive metrics (request counts, token sums, cost totals).
- **Consequences**: Guarantees mathematically accurate latency percentiles; requires scheduled retention pruning of aged raw events once beyond the active detailed query window.

### ADR 012: Docker Compose for Local Dependencies; PostgreSQL 17 Pinned
- **Status**: Accepted
- **Context**: Local development requires a consistent, reproducible PostgreSQL environment that matches target deployment without forcing developers to install native PostgreSQL server instances on Windows host machines.
- **Decision**: Use Docker Compose (`compose.yaml`) with major version pinned to `postgres:17`, binding exclusively to `127.0.0.1:${POSTGRES_PORT:-5432}` and storing database state in a named Docker volume (`kestrel_pgdata`).
- **Consequences**: Ensures predictable database behavior across developer environments; protects database port from external network exposure; persists development data across `docker compose down` while allowing clean resets via `docker compose down -v`.

### ADR 013: uv with pyproject.toml and uv.lock for Python Dependencies
- **Status**: Accepted
- **Context**: Python dependency management must be fast, deterministic, cross-platform, and fully reproducible across local Windows development and CI pipelines without lockfile discrepancy.
- **Decision**: Adopt `uv` with standard PEP 621 `pyproject.toml` and lockfile `uv.lock` for all backend packaging and virtual environments.
- **Consequences**: Delivers sub-second package resolution and installation; eliminates pip-compile divergence; standardizes tool configurations (ruff, pytest) inside a single file.

### ADR 014: API Conventions: Product Endpoints under /api/v1; Probes Unversioned at Root
- **Status**: Accepted
- **Context**: Infrastructure probes (Kubernetes, Compose, reverse proxies) require standard static paths for liveness and readiness, whereas product business APIs evolve with explicit version deprecation lifecycles.
- **Decision**: Expose operational infrastructure probes (`/health`, `/health/ready`) unversioned at the server root; route all application domain endpoints under `/api/v1`.
- **Consequences**: Shields cluster monitoring from product API version deprecations; keeps internal infrastructure probes clean and lightweight.

### ADR 015: Direct-to-Main Workflow with Milestone Tags and a Pre-Push Quality Gate
- **Status**: Accepted
- **Context**: A solo engineering cadence requires eliminating pull request latency while preserving strict repository safety, traceable rollback points, and non-negotiable code quality.
- **Decision**: Commit directly to `main` with Conventional Commits, tagging each completed milestone (e.g. `m1-docker-postgres`, `m2-backend-skeleton`) and enforcing a mandatory pre-push quality gate (`ruff check`, `ruff format --check`, `pytest`, secret scan).
- **Consequences**: Maximizes development velocity without branch sprawl; tags provide exact immutable rollback points; pre-push gates guarantee broken code or secrets never land on `main`.

---

## ADR-016: UUIDv4 vs BIGINT Identity for Primary Keys

- **Status**: Accepted (2026-11-26)
- **Context**: Kestrel stores multi-tenant workspace entities, user identities, provider connections, and high-volume telemetry records. We must select a primary key strategy that supports distributed generation, prevents enumeration attacks, and maintains database performance.
- **Decision**: Standardize on UUIDv4 (PostgreSQL native `UUID` type with server default `gen_random_uuid()`) for primary keys on all relation tables (`workspaces`, `users`, `api_keys`, `providers`, `pricing_rules`, `alerts`, `incidents`, `audit_logs`).
- **Consequences**: IDs can be generated safely client-side or by application workers prior to persistence; eliminates sequential ID crawling and guessing across workspaces; avoids cross-environment ID collision during testing; slightly larger storage size (16 bytes vs 8 bytes for `BIGINT`), which is negligible for entity tables and fully supported by PostgreSQL native operators. High-throughput telemetry events will pair UUIDv4/UUIDv7 with time-series range partitioning.

---

## ADR-017: VARCHAR with CHECK Constraints vs PostgreSQL Native ENUM for Categorical Fields

- **Status**: Accepted (2026-11-26)
- **Context**: Multiple tables require constrained categorical values (e.g. `users.role IN ('admin', 'viewer')`, `providers.provider_type`, `incidents.status`). PostgreSQL provides both native `ENUM` types (`CREATE TYPE ... AS ENUM`) and `VARCHAR(N)` columns bounded by table-level `CHECK` constraints.
- **Decision**: Standardize on `VARCHAR(N)` with explicit, named `CHECK` constraints (e.g., `ck_users_role_valid`) across all models instead of PostgreSQL native `ENUM` types.
- **Consequences**: PostgreSQL native enums present operational challenges: adding values cannot easily be rolled back in transactions, altering or renaming values requires non-transactional metadata locks, and dropping enum values is difficult. `CHECK` constraints are fully transactional, easily modified via standard `ALTER TABLE ... DROP/ADD CONSTRAINT`, cleanly inspected by Alembic autogenerate, and portable.

---

## ADR-018: Alembic Migrations and Dedicated Test Database Strategy

- **Status**: Accepted (2026-11-26)
- **Context**: Database schema evolution must be version-controlled, repeatable, and reversible. Automated tests must execute against real PostgreSQL to validate Postgres-specific SQL, constraints, and indexes without mutating developer or production data or causing concurrency collisions.
- **Decision**:
  1. Manage all DDL through Alembic version scripts in `backend/migrations/versions/`.
  2. Use a dedicated test database (`kestrel_test`) automatically provisioned and migrated to `head` in session-scoped pytest fixtures. Individual test cases run in function-scoped nested transactions with savepoints (`join_transaction_mode="create_savepoint"`) and rollback on teardown.
  3. Author dedicated migration lifecycle tests (`backend/tests/test_migrations.py`) using an ephemeral throwaway database (`kestrel_migration_test`) that verifies upgrade to `head`, downgrade to `base`, re-upgrade to `head`, and validates zero schema drift via `alembic check`.
  4. Enforce safety guards: test fixtures strictly refuse to connect to or drop any database name that does not end with `_test`.
- **Consequences**: Schema migrations are validated on every test run; test cases execute in milliseconds without re-migrating between tests; schema drift between SQLAlchemy ORM metadata and migration files is caught automatically.

---

## ADR-019: SHA-256 for API Keys vs Argon2id for User Passwords

- **Status**: Accepted (2026-11-26)
- **Context**: Telemetry ingestion (`POST /ingest/events`) receives high-frequency client requests authenticated via workspace API keys. Dashboard users authenticate via human passwords. The security and performance profiles for these two credential types differ fundamentally.
- **Decision**:
  1. User passwords will use Argon2id with recommended memory and iteration parameters (high compute cost to defeat offline dictionary attacks on human-chosen passwords).
  2. Workspace API keys will use high-entropy random tokens (e.g. `ks_live_<32_random_bytes>`) stored exclusively as unsalted SHA-256 hashes (`key_hash VARCHAR(64)`).
- **Consequences**: API key verification requires a fast SHA-256 digest computation (< 1ms), preventing ingestion bottlenecks; high entropy of generated keys eliminates dictionary attacks. User passwords have an intentional ~100-300ms verification cost suitable for interactive login. Plaintext secrets are never persisted in the database.

---

## ADR-020: Hardcoded JWT Security Constants vs Environment Configuration

- **Status**: Accepted (2026-11-26)
- **Context**: JWT implementations can be vulnerable to algorithm confusion attacks (e.g., accepting `none` or switching symmetric/asymmetric algorithms) or signature forgery if issuers, audiences, and algorithms are loosely configured or dynamically parsed from unverified token headers.
- **Decision**: Hardcode JWT cryptographic constants in application code:
  - `JWT_ALGORITHM = "HS256"`
  - `JWT_ISSUER = "kestrel"`
  - `JWT_AUDIENCE = "kestrel-api"`
  These constants are never loaded from environment variables and never taken from unverified token headers.
- **Consequences**: Completely eliminates algorithm substitution vulnerabilities; ensures tokens generated for other internal or third-party APIs cannot be replayed against Kestrel endpoints; simplifies configuration while hardening signature verification.

---

## ADR-021: Database-Backed Authorization over Rich JWT Token Claims

- **Status**: Accepted (2026-11-26)
- **Context**: Purely stateless JWT architectures encode user permissions, roles, and tenant IDs directly in claims. However, if a user is compromised, deactivated, or demoted, their existing tokens remain authorized until expiration (up to 60 minutes), requiring complex distributed token revocation lists or Redis blacklists.
- **Decision**: Keep access tokens strictly minimal, containing only `sub` (user UUID) and standard timestamp claims. On every authenticated request, `get_current_user` decodes the UUID and queries PostgreSQL to verify that the user exists and `is_active` is true, retrieving their live `role` and `workspace_id`.
- **Consequences**: Immediate authorization revocation upon user deactivation with zero lag; avoids token bloat; adds one indexed primary key lookup per request (~0.5ms on local/pooled PostgreSQL), which is acceptable for dashboard and management traffic. High-frequency telemetry ingestion uses API keys, not JWTs.

---

## ADR-022: Workspace-Scoped Repository Pattern for Multi-Tenant Isolation

- **Status**: Accepted (2026-11-26)
- **Context**: Kestrel operates a shared-database, shared-schema multi-tenant model. Hand-crafting SQL queries in routers or ad-hoc handlers creates significant risk of missing a `workspace_id` filter, resulting in cross-tenant data leakage.
- **Decision**: Require all domain data access to pass through repositories inheriting from `WorkspaceScopedRepository`. The repository requires `workspace_id` at instantiation and automatically applies `statement.where(Model.workspace_id == self.workspace_id)` via `self.scope()`. Unscoped queries are strictly forbidden in business modules and permitted only in authentication for initial email lookup and token ID resolution.
- **Consequences**: Prevents accidental cross-tenant data leaks by construction; centralizes pagination, sorting, and tenant query logic; provides a single auditing point for data isolation.
