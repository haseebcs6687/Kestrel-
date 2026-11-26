# Engineering Learning Notes

## Standard Note Format
Each entry follows: Concept | Definition | Why it matters | How we used it | Architecture | Important terminology | Example | Interview questions (3-5) | Practical mistakes | Revision summary.

---

## Learning Notes — Milestone 6: GitHub Actions CI for Backend

- **Concepts Covered**: Service containers in CI, deterministic lockfile installations, dynamic runner secret masking (`::add-mask::`), dual-layer secret scanning, and advisory dependency vulnerability auditing.
- **Definitions & Architecture**:
  - *PostgreSQL Service Container (ADR-003, ADR-028)*: Ubuntu runner hosts an isolated `postgres:17` container mapped to `127.0.0.1:5432` with healthcheck (`pg_isready`), ensuring tests run against production-identical PostgreSQL engine without mocks.
  - *Dynamic Secret Masking*: Generating ephemeral credentials (`JWT_SECRET_KEY`) at runtime and invoking `echo "::add-mask::$KEY"`; GitHub Actions redaction engine masks every occurrence across step logs and tracebacks.
  - *Dual-Layer Secret Scanning (ADR-029)*: In-repo stdlib scanner (`scripts/secret_scan.py`) acts as local pre-push gate and CI first line; `gitleaks-action@v3` scans full git history (`fetch-depth: 0`) for comprehensive signature coverage.
  - *Advisory Dependency Audits*: Running `pip-audit` with `continue-on-error: true` alerts teams to emerging CVEs without blocking immediate pipeline merges when upstream vendor patches are pending.
- **Terminology**: Service container, `pg_isready`, `add-mask`, Concurrency cancel-in-progress, Ephemeral credential, Advisory audit, Actionlint.
- **Interview Questions & Answers**:
  1. *Q: Why use a real PostgreSQL service container in CI instead of SQLite or mocking?*
     A: SQLite and mocks hide PostgreSQL-specific behaviors: transactional DDL semantics, JSONB operators, identity sequences, and constraint enforcement. Real containers guarantee zero drift between CI test outcomes and production runtime.
  2. *Q: Why run secret scanning both locally (pre-push) and in CI with dual layers (custom script + Gitleaks)?*
     A: Local scanning prevents commits from leaking secrets before reaching remotes; CI dual scanning enforces this on PRs and combines project-specific token rules with broad enterprise secret signatures.
  3. *Q: Why is the dependency vulnerability audit job configured as advisory (`continue-on-error: true`)?*
     A: Third-party vulnerabilities may lack immediate upstream fixes. Treating audits as advisory gives security visibility without halting developer velocity on zero-day notices outside project control.
  4. *Q: How does GitHub Actions handle secrets and masking dynamically generated environment variables (e.g. `::add-mask::`)?*
     A: Calling `::add-mask::<value>` registers the string with the runner log filter, replacing all subsequent stdout/stderr occurrences with `***`, preventing accidental exposure in test or command output.
- **Practical Mistakes**: Relying on SQLite in CI while deploying PostgreSQL; hardcoding static tokens in CI workflow YAML; failing to set `fetch-depth: 0` for Gitleaks; letting blocking security audits break CI on unfixable third-party notices.
- **Revision Summary**: Milestone 6 establishes an automated, secure GitHub Actions CI pipeline with real PostgreSQL, dual secret scanning, and deterministic uv caching.

---

## Learning Notes — Milestone 5b: Audit Logs Schema Alignment, Applied Migration Immutability & Contract Testing

- **Concepts Covered**: Applied migration immutability (ADR-016), forward-migration repair, end-to-end request-ID contract consistency, foreign key ON DELETE RESTRICT on audit history, and reproduction-first bug fixing.
- **Definitions & Architecture**:
  - *Applied Migration Immutability (ADR-016, ADR-027)*: Never edit or delete an already applied migration. Schema corrections must always be enacted as forward migrations (`0003`) to maintain linear consistency across distributed environments.
  - *Data Loss Safeguards in Destructive Rebuilds*: Migration 0003 queries `SELECT count(*) FROM audit_logs` before dropping, aborting with `RuntimeError` if existing records are present to prevent unintentional data loss.
  - *API vs DB Contract Consistency*: The HTTP request-ID middleware allowed 1-64 character IDs, but the initial schema used `VARCHAR(36)`, causing truncation. The column size must always equal or exceed the maximum allowed upstream length.
  - *Audit History Permanence (`ON DELETE RESTRICT`)*: Tenant audit rows must outlive operational records and resist deletion if a tenant workspace is dropped, preserving forensic accountability.
  - *Deferred IP & User-Agent Storage*: Storing client IPs and user-agents without trusted reverse-proxy headers (e.g. `X-Forwarded-For` CIDR validation) introduces spoofing and privacy liabilities; such storage must be deferred until proxy infrastructure is architected.
- **Terminology**: Forward migration, Schema drift, Destructive migration guard, Constraint contract, Monotonic BIGINT identity, ON DELETE RESTRICT, Request ID truncation.
- **Example**: Reproducing the bug before fixing: a test asserting `audit_row.request_id == "A"*32 + "_" + "B"*29 + "-1"` failed on `VARCHAR(36)` before Migration 0003 and passed immediately after.
- **Interview Questions & Answers**:
  1. *Q: Why must database migrations in shared or production repositories never be edited after being applied?*
     A: Editing applied revisions alters migration checksums and histories, creating irreconcilable drift across staging, developer machines, and production instances that disrupts future migrations.
  2. *Q: Why should an audit_logs table configure ON DELETE RESTRICT on tenant workspace foreign keys?*
     A: Audit trails provide statutory and security compliance; configuring CASCADE would allow an attacker or accidental script deleting a tenant workspace to permanently erase the forensic record of their actions.
- **Practical Mistakes**: Editing migration 0002 directly to fix schema discrepancies; truncating request IDs silently in service code instead of expanding the database column; assuming client IP headers are authentic without reverse-proxy validation.
- **Revision Summary**: Milestone 5b establishes migration 0003, bringing audit_logs into complete alignment with the approved design while safeguarding migration immutability.

---

## Learning Notes — Milestone 5: Sessions, Refresh Token Rotation, Reuse Detection & Audit Trail

- **Concepts Covered**: Cryptographic opaque refresh tokens, token family rotation, automated reuse detection, HttpOnly/SameSite cookie security, CSRF defense-in-depth, immutable PostgreSQL audit logging, and defense-in-depth key sanitization.
- **Definitions & Architecture**:
  - *Opaque Refresh Tokens (ADR-024)*: High-entropy random strings (`secrets.token_urlsafe(48)`) stored as deterministic SHA-256 hashes; plaintext tokens are never stored in the database.
  - *Token Rotation & Family Trees*: Each refresh request issues a new token and marks the previous token revoked with a `replaced_by_id` pointer, preserving a traversal history under a shared `family_id`.
  - *Reuse Detection*: If an already revoked token is presented, the server treats it as evidence of token theft, immediately revoking all active tokens in the entire family in an isolated committed transaction.
  - *HttpOnly / SameSite=Strict Cookie (ADR-026)*: Refresh tokens are transmitted via browser cookies inaccessible to client-side JavaScript, mitigating XSS exfiltration.
  - *CSRF Defense-in-Depth*: Requiring the custom client header `X-Kestrel-Client: web` on mutating cookie-authenticated endpoints (`/refresh`, `/logout`), which browsers block cross-origin without CORS approval.
  - *Append-Only Audit Log (ADR-025)*: Immutable operational event stream (`audit_logs`) correlated with Structlog `request_id` and sanitized against sensitive credential keys.
- **Terminology**: Token family, Rotation chain, Reuse detection, Replaced-by pointer, SHA-256 hash digest, HttpOnly, SameSite=Strict, CSRF header, Audit trail, Request ID correlation.
- **Example**: `rotate_refresh_token()` looks up the presented token with `SELECT ... FOR UPDATE`; if `is_revoked`, it invalidates the entire family tree, commits, records an audit event, and raises `RefreshTokenReused`.
- **Interview Questions & Answers**:
  1. *Q: How does refresh token rotation with reuse detection protect users against token theft?*
     A: If an attacker intercepts a refresh token, either the legitimate user or the attacker will use it first. As soon as the other party attempts to use the now-revoked token, reuse is detected, and the entire session family is instantly terminated for both.
  2. *Q: Why store SHA-256 hashes of refresh tokens instead of raw values?*
     A: If database backups or replicas are compromised, attackers obtain only one-way cryptographic hashes, preventing them from forging valid refresh cookie requests.
  3. *Q: Why require a custom header like `X-Kestrel-Client` on cookie-authenticated refresh requests?*
     A: Modern browsers enforce `SameSite=Strict`, but requiring a custom header guarantees that standard HTML form submissions or cross-origin fetch calls cannot trigger refresh operations, as cross-origin custom headers trigger mandatory CORS preflights.
  4. *Q: Why must audit logging participate in the caller's transaction by default, but reuse detection commits immediately?*
     A: Routine audit records should roll back if the business operation fails (to prevent recording actions that never took effect). However, security breach responses like reuse detection must persist immediately even if the HTTP request returns an error.
- **Practical Mistakes**: Storing raw refresh tokens in plaintext; returning 401 on token reuse without revoking the sibling tokens; exposing detailed reuse error messages to the client; putting tokens or passwords in audit metadata details.
- **Revision Summary**: Milestone 5 delivers an enterprise-grade session lifecycle with automatic token theft detection and an unalterable audit trail.

---

## Learning Notes — Milestone 4: Authentication Core & Multi-Tenant Isolation

- **Concepts Covered**: Memory-hard password hashing with Argon2id, timing attack equalization, JWT stateless tokens vs live database authorization, mass-assignment defense, and workspace-scoped repository isolation.
- **Definitions & Architecture**:
  - *Argon2id*: Hybrid password hashing algorithm combining data-dependent and data-independent memory access; highly resilient against side-channel and GPU/ASIC brute-force attacks.
  - *Timing Equalization (`get_dummy_hash`)*: Executing password verification against a synthetic hash when an email is not found, equalizing response times to prevent username enumeration.
  - *Dynamic Database Authorization (ADR-021)*: Restricting JWT claims to `sub` (user UUID); loading active status and roles from PostgreSQL on every request to enable instantaneous access revocation.
  - *`WorkspaceScopedRepository` (ADR-022)*: Architectural pattern that automatically enforces tenant boundaries (`WHERE workspace_id = :id`) on all domain queries by construction.
  - *Mass Assignment Protection*: Pydantic model configuration (`extra="forbid"`) preventing malicious clients from injecting administrative fields (`role`, `is_active`) on public endpoints.
- **Terminology**: Argon2id, Timing attack, Subject claim (`sub`), Dummy hash, Repository pattern, Mass assignment, RBAC, Bearer scheme, Scope constraint.
- **Example**: `UserRepository(db, ws_id).list_users()` automatically applies `where(User.workspace_id == ws_id)`, making cross-tenant user leaks impossible.
- **Interview Questions & Answers**:
  1. *Q: Why store only the user ID in the JWT rather than embedding their role and workspace ID?*
     A: Embedding permissions makes revocation difficult; querying the database on each request ensures immediate enforcement if a user is deactivated or demoted.
  2. *Q: How does a dummy hash prevent account enumeration timing attacks?*
     A: Password verification takes ~50-100ms. If nonexistent accounts return immediately (< 1ms), attackers can measure latency to discover valid email addresses.
  3. *Q: Why use `extra="forbid"` on Pydantic request models?*
     A: Protects against mass assignment vulnerabilities where attackers submit undocumented payload fields (e.g. `role: "admin"`) hoping backend code persists them.
  4. *Q: Why hardcode JWT security constants (`HS256`, `iss`, `aud`) instead of reading them from environment variables?*
     A: Eliminates algorithm confusion attacks and ensures tokens cannot be generated or replayed across disparate environments or untrusted issuers.
- **Practical Mistakes**: Trusting JWT claims without checking `is_active` in the database; querying tenant data without repository scoping; setting JWT expiration too long without refresh tokens.
- **Revision Summary**: Milestone 4 establishes a hardened Argon2id + JWT authentication core, complete multi-tenant isolation, and zero-trust request authorization.

---

## Learning Notes — Milestone 3: Database Schema Design, Alembic & Identity Models

- **Concepts Covered**: Database migration lifecycle, schema drift detection, declarative naming conventions, UUIDv4 vs BIGINT, VARCHAR + CHECK vs PostgreSQL native ENUM, transactional savepoint testing isolation.
- **Definitions & Architecture**:
  - *Alembic Migration Lifecycle*: Versioned DDL scripts providing forward (`upgrade`) and backward (`downgrade`) schema state transitions; `alembic_version` stores the applied revision.
  - *Schema Drift*: Discrepancy between SQLAlchemy Python model definitions and live database tables, detected automatically via `alembic check`.
  - *Naming Convention*: Explicit naming dictionary (`ix_`, `uq_`, `ck_`, `fk_`, `pk_`) ensuring deterministic constraint names across PostgreSQL and Alembic autogeneration.
  - *Transactional Savepoints*: Running test cases within a nested transaction (`SAVEPOINT`); rolling back to the savepoint restores the database in microseconds without slow table dropping.
  - *CHECK Constraints vs Native ENUM*: String columns bounded by `CHECK (col IN (...))` allow fully transactional schema updates, whereas native PostgreSQL enums hinder rollback.
- **Terminology**: Revision, Head, Base, Savepoint, Schema drift, DDL, `gen_random_uuid()`, Autocommit, Foreign key RESTRICT.
- **Example**: `command.check(alembic_cfg)` compares `target_metadata` with DB schema and raises an exception if untracked model fields or missing migrations exist.
- **Interview Questions & Answers**:
  1. *Q: Why use transactional savepoints in pytest fixtures instead of rebuilding tables per test?*
     A: DDL table creation is slow (~100-500ms per test). Nested transactions (`SAVEPOINT`) allow test isolation with instantaneous rollbacks (< 1ms).
  2. *Q: What are the drawbacks of PostgreSQL native ENUMs compared to VARCHAR + CHECK constraints?*
     A: Native ENUM mutations cannot be rolled back inside transactions in many PG operations, values cannot easily be removed, and migration scripts require non-standard DDL.
  3. *Q: How does `alembic check` prevent uncommitted schema changes from breaking production?*
     A: It executes autogenerate comparison logic headlessly; if any model attribute does not match the migration history, the command exits with non-zero status.
  4. *Q: Why use `ON DELETE RESTRICT` for workspace-to-user relationships instead of `CASCADE`?*
     A: Prevents accidental bulk data deletion when deleting a workspace; requires explicit deliberate pruning of associated users first.
- **Practical Mistakes**: Passing database URLs containing `%` directly to `config.set_main_option()` (triggers `ConfigParser` crash); invoking `db_session.add()` before `begin_nested()` when expecting `IntegrityError`; running tests against development database instead of dedicated `_test` DB.
- **Revision Summary**: Milestone 3 establishes an immutable migration history, strict constraint-driven identity models, and zero-drift CI verification.

---

## Learning Notes — Milestone 2: Backend Skeleton & Probes

- **Concepts Covered**: Application factory pattern, dependency injection with `get_db`, Pydantic Settings & `SecretStr`, liveness vs readiness probes, request IDs and structured logging, sync vs async endpoints, and lockfile determinism.
- **Definitions & Architecture**:
  - *App Factory (`create_app`)*: Encapsulates application instantiation, allowing independent configuration for testing, development, and production environments.
  - *Dependency Injection (`get_db`)*: Yields database sessions per request, ensuring automatic connection cleanup in a `finally` block regardless of request outcome.
  - *`SecretStr`*: Masked string type in Pydantic that prevents credentials from leaking in logs, tracebacks, `str()`, or `repr()`.
  - *Liveness (`/health`) vs Readiness (`/health/ready`)*: Liveness confirms the web process is running; readiness confirms backing infrastructure (PostgreSQL) is operational to serve traffic.
  - *Request IDs (`X-Request-ID`)*: Distributed tracing identifier bound to task-local contextvars, attached to every log record and echoed in response headers.
  - *Sync vs Async Endpoints*: With synchronous SQLAlchemy 2.0, endpoints are plain `def`, allowing FastAPI to manage execution in an external threadpool without blocking the async event loop.
  - *Lockfile (`uv.lock`)*: Immutable dependency manifest pinning transitive packages across all development and deployment machines.
- **Terminology**: App factory, Dependency injection, `SecretStr`, Liveness probe, Readiness probe, Contextvars, `X-Request-ID`, Threadpool worker, Lockfile.
- **Example**: `client.get("/health/ready")` executes `SELECT 1`; if PostgreSQL is stopped, returns HTTP 503 `{"status": "unavailable", "checks": {"database": "fail"}}` with no leaked error text.
- **Interview Questions & Answers**:
  1. *Q: Why should readiness probes fail when dependencies are down, while liveness probes continue to succeed?*
     A: If liveness fails on database outage, orchestrators restart web containers in an unrecoverable crash loop; readiness failure simply halts incoming traffic until the database recovers.
  2. *Q: Why define FastAPI endpoints as plain `def` instead of `async def` when using synchronous SQLAlchemy?*
     A: Calling synchronous blocking database queries inside an `async def` endpoint blocks the single-threaded asyncio event loop; plain `def` endpoints are safely offloaded to FastAPI's threadpool.
  3. *Q: How does `SecretStr` prevent accidental secret leakage?*
     A: It overrides `__str__` and `__repr__` to display `**********`; developers must explicitly call `.get_secret_value()` to access the raw plaintext string.
  4. *Q: Why validate incoming `X-Request-ID` headers against a strict regex before binding?*
     A: Prevents log injection, header injection, and unconstrained memory allocation from malicious or malformed client identifiers.
  5. *Q: What problem does a lockfile (`uv.lock`) solve that `pyproject.toml` dependencies do not?*
     A: `pyproject.toml` declares version ranges; `uv.lock` pins the exact transitive dependency graph and cryptographic hashes, preventing unexpected breaking updates.
- **Practical Mistakes**: Concatenating connection strings with unescaped passwords; running blocking sync DB calls in `async def`; returning raw database exceptions in readiness error responses.
- **Revision Summary**: Milestone 2 delivers an unversioned health/readiness probe architecture, sanitized configuration, and correlation request logging using `uv` and FastAPI.

---

## Learning Notes — Milestone 1: Docker & PostgreSQL Containerization

- **Concepts Covered**: Image vs container lifecycle, persistent Docker volumes, localhost-only port binding, container healthchecks, and environment secret hygiene.
- **Definitions & Architecture**:
  - *Image vs Container*: An image (`postgres:17`) is an immutable, read-only template; a container is a stateful, running instance with an ephemeral writable layer.
  - *Named Volumes*: Storage managed by Docker outside the container's root filesystem; preserves database files across container restarts and destructions (`docker compose down`).
  - *Localhost Binding (`127.0.0.1:5432:5432`)*: Explicitly restricts listening sockets to the loopback interface, preventing exposure on local LAN or public networks.
  - *Healthchecks*: Active probes (e.g. `pg_isready`) reporting container readiness to Compose and dependent services before traffic is routed.
- **Terminology**: Image, Container, Named Volume, Daemon, Ephemeral layer, Loopback interface, `pg_isready`, Secret hygiene.
- **Example**: `docker compose down` destroys container instances while preserving `kestrel_pgdata`; `docker compose down -v` destroys both containers and volumes.
- **Interview Questions & Answers**:
  1. *Q: What is the difference between `docker compose down` and `docker compose down -v`?*
     A: `down` stops and removes containers and networks but leaves named volumes intact; `-v` removes volumes as well, resulting in permanent data loss.
  2. *Q: Why bind database ports to `127.0.0.1:5432:5432` instead of `5432:5432`?*
     A: `5432:5432` binds to `0.0.0.0`, exposing the database to the local network or public interfaces; `127.0.0.1` restricts access strictly to the local host machine.
  3. *Q: Why pin PostgreSQL to a specific major version (`postgres:17`) instead of `latest`?*
     A: Major database versions introduce breaking storage engine changes and require explicit migration tools (`pg_upgrade`); `latest` risks inadvertent breakage upon updates.
  4. *Q: How does `pg_isready` prevent race conditions in Docker Compose orchestration?*
     A: It verifies that the Postgres server is actively accepting connections rather than merely confirming that the container process has booted.
- **Practical Mistakes**: Forgetting `-v` deletes volumes or accidentally running `-v` in production; committing `.env` containing live secrets; binding database ports to `0.0.0.0`.
- **Revision Summary**: Milestone 1 establishes a reproducible, isolated PostgreSQL 17 environment with proven volume persistence and zero-secret exposure.

---

## Learning Notes — Milestone 0: Bootstrap & Foundations

- **Concepts Covered**: Monorepo layout, Git & secret hygiene, Conventional Commits with PR flow, and Architecture Decision Records (ADRs).
- **Definitions & Architecture**:
  - *Monorepo*: Single repository containing multiple co-evolving packages (`backend`, `frontend`, `infra`). Simplifies coordinated atomic PRs and shared types.
  - *Secret Hygiene*: Strict exclusion of credentials via `.gitignore`, pre-commit verification, and regex auditing. Crucial to prevent credential leaks to public GitHub.
  - *Branch & PR Flow*: Branch protection on `main`, isolated milestone branches (`milestone/00-bootstrap`), atomic PRs with checklist verification.
  - *ADRs*: Light, version-controlled records capturing context, decisions, and consequences for architectural choices.
- **Terminology**: Monorepo, Fernet, `percentile_cont`, JWT, Conventional Commits, Root commit.
- **Example**: Git pre-push check: `git check-ignore -v .env` returns `.gitignore:2:.env`, preventing accidental leak.
- **Interview Questions & Answers**:
  1. *Q: Why choose an ingest API over an LLM gateway proxy?*
     A: Telemetry records exact client-measured tokens and latency without putting our service in the inference critical path or holding provider keys.
  2. *Q: Why store prices directly on telemetry events instead of joining with a pricing table?*
     A: Snapshotting guarantees that historical cost analytics remain immutable even when providers change token prices later.
  3. *Q: Why can't latency percentiles (p50/p95/p99) be calculated from pre-aggregated rollups?*
     A: Percentiles cannot be mathematically averaged across time buckets; raw latency samples must be retained for accurate quantile queries.
  4. *Q: How do you enforce tenant isolation in a shared database?*
     A: Centralize all database operations in workspace-scoped repositories that mandate `workspace_id` parameters on every query.
- **Practical Mistakes**: Committing `.env` before configuring `.gitignore`; averaging p95 percentiles across hourly rollups; storing raw prompts containing PII/keys.
- **Revision Summary**: Milestone 0 establishes repository scaffolding, documentation invariants, and zero-secret git discipline before writing code.
