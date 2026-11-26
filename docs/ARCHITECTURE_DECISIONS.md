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

## ADR-020: JWT access tokens (HS256, 15 minutes, minimal claims; algorithm, issuer and audience are code constants)

- **Status**: Accepted (2026-11-26)
- **Context**: JWT implementations can be vulnerable to algorithm confusion attacks (e.g., accepting `none` or switching symmetric/asymmetric algorithms) or signature forgery if issuers, audiences, and algorithms are loosely configured or dynamically parsed from unverified token headers.
- **Decision**: Hardcode JWT cryptographic constants in application code:
  - `JWT_ALGORITHM = "HS256"`
  - `JWT_ISSUER = "kestrel"`
  - `JWT_AUDIENCE = "kestrel-api"`
  These constants are never loaded from environment variables and never taken from unverified token headers. Tokens are signed with HS256, have a 15-minute default expiration, and contain minimal claims (`sub`, `iat`, `exp`, `iss`, `aud`, `typ`).
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

---

## ADR-023: Generic authentication errors and dummy-hash verification to limit user enumeration; duplicate-email disclosure at registration accepted for the MVP

- **Status**: Accepted (2026-11-26)
- **Context**: Authentication endpoints can disclose account existence through disparate error codes/messages or timing discrepancies between valid and nonexistent accounts.
- **Decision**:
  1. On login failure, return identical HTTP 401 status, header (`WWW-Authenticate: Bearer`), and body (`{"detail": "Invalid email or password"}`) whether the email does not exist, the password is wrong, or the account is deactivated.
  2. For nonexistent accounts during login, execute an Argon2id verification against a cached dummy hash (`get_dummy_hash()`) to equalize CPU execution time.
  3. On registration, return HTTP 409 Conflict (`{"detail": "Email already registered"}`). Disclosing email registration state is accepted for the MVP to prioritize immediate developer usability over delayed email confirmation flows.
- **Consequences**: Prevents timing attacks and account harvesting on login; adds ~50ms computation on failed logins; trade-off on registration error disclosure is explicitly documented.

---

## ADR-024: DB-Backed Opaque Refresh Tokens with Rotation and Reuse Detection

- **Status**: Accepted (2026-11-26)
- **Context**: Short-lived access tokens (15 minutes) reduce the exposure window of stolen credentials but degrade usability if users are forced to re-enter passwords frequently. Long-lived stateless refresh tokens cannot be revoked individually and pose major replay risks if intercepted.
- **Decision**: Implement database-backed opaque refresh tokens generated via `secrets.token_urlsafe(48)` (~288 bits entropy) and persisted strictly as deterministic SHA-256 hashes in `refresh_tokens(token_hash)`. Plaintext tokens are never stored. On every `/api/v1/auth/refresh` request, enforce single-use token rotation: revoke the current token, link it to the successor token via `replaced_by_id`, and issue a new token within the same `family_id`. If an already revoked token is presented, detect reuse immediately, invalidate all active tokens in the entire family in a committed transaction, record an `auth.refresh_reuse_detected` audit log, and return an opaque 401 error.
- **Consequences**: Mitigates token theft and replay attacks automatically; compromised session families are terminated upon detection; requires one database update and insert per refresh call; guarantees zero exposure of plaintext session secrets from database dumps.

---

## ADR-025: Append-Only Audit Log in PostgreSQL with Request-ID Correlation and Defense-in-Depth Sanitization

- **Status**: Accepted (2026-11-26)
- **Context**: Enterprise compliance, tenant security, and incident forensics require an immutable history of sensitive operational and security events without risking credential leakage into log stores.
- **Decision**: Maintain an append-only `audit_logs` table in PostgreSQL with composite indexing on `(workspace_id, created_at DESC)` and `(workspace_id, action)`. Correlate entries with the active Structlog `request_id` context variable. Enforce defense-in-depth sanitization in `audit_service.record()`: recursively validate `details` JSON payloads and raise an exception if forbidden credential keys or substrings (`password`, `token`, `secret`, `cookie`, `authorization`, `hash`) appear. Participate in the caller's transaction by default (calling `flush()` without `commit()`) so aborted business operations do not leave misleading audit trails, while security breach alarms commit immediately.
- **Consequences**: Provides reliable, tenant-isolated audit logs; prevents accidental leakage of credentials into audit storage; ensures cross-layer traceability between HTTP server logs and database records.

---

## ADR-026: HttpOnly Cookie for Refresh Tokens with Custom Header Requirement for CSRF Defense-in-Depth

- **Status**: Accepted (2026-11-26)
- **Context**: Delivering refresh tokens in JSON bodies encourages frontend clients to store them in `localStorage` or `sessionStorage`, where they are vulnerable to exfiltration via Cross-Site Scripting (XSS). Delivering tokens via cookies eliminates XSS extraction but introduces Cross-Site Request Forgery (CSRF) concerns.
- **Decision**: Deliver refresh tokens exclusively via HttpOnly cookies (`kestrel_refresh`) with `Path=/api/v1/auth`, `SameSite=Strict`, and `Secure` attributes. For defense-in-depth beyond browser `SameSite` enforcement, require mutating session endpoints (`/api/v1/auth/refresh` and `/api/v1/auth/logout`) to present the custom header `X-Kestrel-Client: web`.
- **Consequences**: Frontend JavaScript cannot access or exfiltrate the refresh token; cross-site attackers cannot forge requests with custom headers without preflight CORS approval; browsers automatically handle cookie transport and expiration; client-side applications must supply the custom header during refresh and logout calls.

---

## ADR-027: Corrective migration 0003 rebuilds audit_logs: applied migrations are never edited; IP address and user agent are not stored until a trusted-proxy design exists

- **Status**: Accepted (2026-11-26)
- **Context**: Milestone 5 applied migration `0002` with an initial `audit_logs` table that drifted from the approved design in `docs/DATABASE_SCHEMA.md`:
  1. It used a random UUID primary key instead of `BIGINT GENERATED ALWAYS AS IDENTITY`.
  2. It configured `workspace_id` foreign key with `ON DELETE CASCADE` instead of `ON DELETE RESTRICT`.
  3. It defined `request_id` as `VARCHAR(36)` which truncated valid 64-character request IDs permitted by the HTTP request ID middleware (`^[A-Za-z0-9_-]{1,64}$`).
  4. It stored `ip_address` and `user_agent` directly from unvalidated client headers without a trusted-proxy network architecture or reverse-proxy CIDR configuration.
  5. It deviated from canonical column names (`actor_id` vs `actor_user_id`, `resource_type` vs `target_type`, `resource_id` vs `target_id`).
- **Decision**:
  1. In strict compliance with ADR-016 (applied migrations are immutable), do NOT modify or delete applied migrations `0001` or `0002`.
  2. Implement migration `0003` (`0003_rebuild_audit_logs_to_match_schema_design.py`) to drop and rebuild `audit_logs` matching the canonical design: `BIGINT GENERATED ALWAYS AS IDENTITY` primary key, `ON DELETE RESTRICT` on `workspace_id`, `ON DELETE SET NULL` on `actor_user_id`, `VARCHAR(64)` for `request_id`, non-null `details` with default `'{}'::jsonb`, and composite indexes on `(workspace_id, created_at DESC)` and `(workspace_id, action)`.
  3. Include a data-loss guard in `upgrade()` that checks `SELECT count(*) FROM audit_logs` and aborts with `RuntimeError` if existing records exist.
  4. Omit `ip_address` and `user_agent` storage from the audit model, service, and database until a hardened trusted-proxy derivation design is established.
- **Consequences**:
  - Full alignment between SQLAlchemy models, migration chain, and `docs/DATABASE_SCHEMA.md`.
  - Up to 64-character request IDs are persisted without truncation.
  - Audit history is permanently protected against cascade deletion when tenant workspaces are removed.
  - Zero risk of spoofed IP address or user-agent data poisoning the audit trail.

---

## ADR-028: GitHub Actions CI: PostgreSQL Service Container, uv Sync --locked, Least-Privilege Permissions, and Cancel-in-Progress

- **Status**: Accepted (2026-11-26)
- **Context**: In line with ADR-003, all tests must execute against real PostgreSQL rather than mocks or SQLite. Automated continuous integration is required to enforce this constraint, validate database migrations, catch schema drift, and run linting on every commit and pull request. The CI environment must prevent secret leakage, run with minimal permissions, and avoid wasting compute on superseded runs.
- **Decision**:
  1. Define `.github/workflows/ci.yml` triggering on push to `main` and temporary test branches (`ci-test/**`), pull requests, and manual triggers (`workflow_dispatch`).
  2. Run a real PostgreSQL 17 Docker service container (`postgres:17`) inside the runner, mapped to `127.0.0.1:5432` with health checks (`pg_isready`).
  3. Use an obvious, ephemeral mock password (`ci_only_ephemeral_password`) for the PostgreSQL service container; generate a random 48-byte URL-safe `JWT_SECRET_KEY` on each run, immediately masking it with `::add-mask::` before adding it to `$GITHUB_ENV`.
  4. Restrict workflow permissions to `permissions: contents: read`.
  5. Enforce deterministic dependency installation with `astral-sh/setup-uv@v10.4.0` and `uv sync --locked`, caching dependencies on `backend/uv.lock`.
  6. Configure concurrency group `ci-${{ github.ref }}` with `cancel-in-progress: true` to abort superseded jobs automatically.
- **Consequences**:
  - CI environment mirrors local production-identical PostgreSQL setup (ADR-003).
  - Schema drift (`alembic check`) and migration health (`alembic upgrade head`) are verified continuously.
  - Zero secrets or credentials are bound in CI configuration; tokens are masked and discarded when the job ends.
  - Runner compute is conserved by cancelling outdated runs upon subsequent pushes.

---

## ADR-029: Secret Scanning via In-Repo Stdlib Script and Gitleaks, with Advisory Dependency Vulnerability Auditing

- **Status**: Accepted (2026-11-26)
- **Context**: Committing secrets (passwords, private keys, API credentials) to public repositories is irreversible and hazardous. Developers need immediate local feedback before pushing to prevent secret leakage, and CI needs automated verification before code enters `main`. Additionally, dependencies must be checked for vulnerabilities without causing sudden build outages when external advisories are published.
- **Decision**:
  1. Implement an in-repo Python standard-library secret scanner (`scripts/secret_scan.py`) that uses `git grep -nIE` to search for known credential patterns (database passwords, JWT secret keys, API key prefixes `sk-`, `AIza`, `gsk_`, private key headers, and forbidden `.env*` files).
  2. Mandate `python scripts/secret_scan.py` as part of the local pre-push quality gate across all environments.
  3. In CI, run dual-layer secret scanning: `scripts/secret_scan.py` followed by `gitleaks/gitleaks-action@v3` on full repository history (`fetch-depth: 0`).
  4. Run dependency vulnerability scanning via `uv export` and `uvx pip-audit` in an isolated job marked `continue-on-error: true` (advisory).
- **Consequences**:
  - Developers can run the exact secret scanning tool locally with zero third-party dependencies.
  - Secret scanning outputs only file paths and line numbers, never matching token text.
  - Dual-layer CI secret scanning protects against both custom project-specific leaks and broad common credential formats.
  - Advisory status on `pip-audit` provides immediate visibility into newly discovered CVEs without blocking critical releases or developer velocity while fixes or upstream updates are pending.

---

## ADR-030: User Management: Deactivation Instead of Deletion; Last-Active-Admin Protection Enforced Under Workspace Row Lock; Multi-Tenant 404 Isolation

- **Status**: Accepted (2026-11-26)
- **Context**: User lifecycles require provisioning, role updates, and termination. Hard-deleting user rows destroys historical audit trails (`actor_user_id`), breaks relational foreign key integrity, and makes post-incident forensic investigation impossible. Furthermore, concurrent admin demotion or deactivation requests could simultaneously pass read checks and leave a workspace with zero active admins (a lock-out condition). Finally, inquiring about or mutating users across workspaces must not reveal cross-tenant user existence.
- **Decision**:
  1. **Deactivation Instead of Deletion**: Users are never hard-deleted from the database. Offboarding is achieved strictly by setting `is_active = false`. Deactivated users are blocked immediately by `get_current_user` on subsequent requests and all active refresh tokens are revoked.
  2. **Last-Active-Admin Invariant via Workspace Row Lock**: A workspace must always retain at least one active administrator. To eliminate mutual-demotion or deactivation race conditions between concurrent admin requests, `update_user` acquires an exclusive row lock on the parent workspace (`SELECT id FROM workspaces WHERE id = :workspace_id FOR UPDATE`) before checking the remaining active admin count. Any transaction attempting to deactivate or demote the last active admin is rejected with HTTP 409 Conflict (`Cannot remove the last active admin`).
  3. **Multi-Tenant 404 Isolation**: Any attempt to read, update, or reset the password of a user belonging to another workspace returns HTTP 404 Not Found, never HTTP 403 Forbidden. Cross-tenant user IDs are treated as nonexistent to prevent ID enumeration.
- **Consequences**:
  - Complete preservation of historical audit records and referential integrity across the datastore.
  - Eliminates the race condition where concurrent admins simultaneously demote or deactivate each other, rendering the tenant orphan.
  - Strict tenant boundary enforcement prevents cross-tenant identity discovery.

---

## ADR-031: Password Management: Session and Refresh Token Revocation on Changes/Resets; 400 for Incorrect Current Password

- **Status**: Accepted (2026-11-26)
- **Context**: When a user's password changes (either via administrative reset or self-service password update), existing authenticated sessions may represent compromised devices or stolen credentials that must not continue renewing tokens. Additionally, error handling for incorrect current passwords must be carefully designed to distinguish credential errors from unauthenticated requests.
- **Decision**:
  1. **Immediate Session Revocation**: Whenever a user's password is reset by an admin (`PUT /api/v1/users/{user_id}/password`) or changed by the user (`POST /api/v1/auth/change-password`), the service executes `revoke_all_user_tokens(db, user_id)`, immediately revoking all active refresh tokens across all session families for that user. On self-service change, the response also clears the caller's `kestrel_refresh` cookie (`Max-Age=0`).
  2. **Error Semantics for Current Password**: When an authenticated user calls `POST /api/v1/auth/change-password` with an incorrect `current_password`, the endpoint returns HTTP 400 Bad Request (`{"detail": "Incorrect current password"}`), NOT HTTP 401 Unauthorized. HTTP 401 indicates that the caller's bearer authentication token is invalid or missing, which triggers client-side logout interceptors. HTTP 400 indicates that the caller is authenticated but submitted invalid payload parameters.
  3. **Identical Password Prohibition**: Changing a password to the identical existing password is rejected with HTTP 400 Bad Request (`{"detail": "New password cannot be the same as the current password"}`) to prevent accidental no-op credential changes.
- **Consequences**:
  - Prevents attackers with existing refresh tokens from continuing to rotate sessions after a legitimate password reset or change.
  - Clean separation in frontend HTTP interceptors between expired auth tokens (401) and failed form validation/wrong current password (400).
  - Short-lived JWTs (15 min) expire naturally and cannot be renewed once refresh tokens are revoked.
