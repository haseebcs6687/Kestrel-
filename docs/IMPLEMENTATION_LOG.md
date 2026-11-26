# Implementation Log — Kestrel AI Control Center

## 2026-11-26 — Milestone 6: GitHub Actions CI for Backend

### Objectives
- Close Milestone 5b review gaps: review test suite against checklist, add `test_audit_log_order_newest_first` to `backend/tests/test_audit.py`.
- Implement in-repo standard-library secret scanner `scripts/secret_scan.py`:
  - Search tracked files using `git grep -nIE` across sensitive patterns (DB passwords, JWT secret keys, API key prefixes `sk-`, `AIza`, `gsk_`, private keys).
  - Verify absence of forbidden `.env*` files in repository tracking.
  - Safe reporting: output only file paths, line numbers, and pattern names; never print secret content.
  - Implement automated test suite in `backend/tests/test_secret_scan_script.py` with runtime synthetic fake tokens.
- Implement GitHub Actions CI workflow in `.github/workflows/ci.yml`:
  - Triggers on push to `main` and temporary test branches (`ci-test/**`), pull requests, and `workflow_dispatch`.
  - Concurrency group `ci-${{ github.ref }}` with `cancel-in-progress: true`.
  - Least-privilege permissions: `permissions: contents: read`.
  - `backend` job: Ubuntu runner, real PostgreSQL 17 Docker service container (`postgres:17`) bound to `127.0.0.1:5432` with `pg_isready` healthcheck; deterministic `astral-sh/setup-uv@v10.4.0` with `uv.lock` caching; `uv sync --locked`; dynamically generated and masked `JWT_SECRET_KEY` via `::add-mask::`; `uv run ruff check .`; `uv run ruff format --check .`; `uv run alembic upgrade head`; `uv run alembic check`; `uv run pytest -ra`.
  - `secrets` job: Full git history checkout (`fetch-depth: 0`), in-repo `python scripts/secret_scan.py`, and `gitleaks/gitleaks-action@v3`.
  - `dependency-audit` job: Advisory dependency vulnerability scan (`continue-on-error: true`) with `uv export` and `uvx pip-audit`.
- Validate workflow file syntax locally using `rhysd/actionlint:latest` Docker container.
- Push to `main`, poll initial CI run, and verify complete green execution.
- Execute negative probe test on temporary branch `ci-test/negative`: confirm deliberate failure on broken test, verify `secrets` and `dependency-audit` jobs succeed, delete branch.
- Add CI workflow badge to `README.md`, update security documentation, record ADR-028 and ADR-029, and document learning notes.

### Files Created & Modified
- `scripts/secret_scan.py`: Standard-library secret scanning script.
- `backend/tests/test_secret_scan_script.py`: Secret scanner unit and integration tests.
- `backend/tests/test_audit.py`: Added `test_audit_log_order_newest_first`.
- `backend/pyproject.toml`: Added `S603` and `S607` per-file ignores for tests.
- `.github/workflows/ci.yml`: GitHub Actions CI pipeline configuration.
- `README.md`: Added CI status badge and Continuous Integration section.
- `docs/ARCHITECTURE_DECISIONS.md`: Added ADR-028 (CI workflow) and ADR-029 (Secret scanning and advisory dependency auditing).
- `docs/SECURITY.md`: Updated secret scanning and dependency vulnerability scanning statuses; added action pinning roadmap.
- `docs/LEARNING_NOTES.md`: Added Milestone 6 learning notes and 4 interview Q&As.
- `docs/ROADMAP.md`, `docs/PROJECT_STATUS.md`, `docs/PROJECT_CONTEXT.md`, `docs/TODO.md`: Updated project tracking.

---

## 2026-11-26 — Milestone 5b: Corrective Schema Fix & Audit Logs Rebuild (Migration 0003)

### Objectives
- Reproduce the `request_id` truncation bug first: write failing tests proving that valid 64-character and 37-character `X-Request-ID` headers are truncated by the database and service.
- Implement migration `0003_rebuild_audit_logs_to_match_schema_design.py` hand-crafted with Alembic `op.*` operations:
  - Add data loss safeguard aborting with `RuntimeError` if existing records exist.
  - Drop 0002 `audit_logs` table and indexes.
  - Recreate canonical `audit_logs`: `BIGINT GENERATED ALWAYS AS IDENTITY` primary key, `ON DELETE RESTRICT` on `workspace_id`, `ON DELETE SET NULL` on `actor_user_id`, `actor_type IN ('user', 'api_key', 'system')`, `request_id VARCHAR(64)`, `details JSONB NOT NULL DEFAULT '{}'::jsonb`, and composite indexes on `(workspace_id, created_at DESC)` and `(workspace_id, action)`.
  - Downgrade recreates exact 0002 shape.
- Update `AuditLog` SQLAlchemy model, `audit_service.record(...)`, `AuditLogRead` schema, repository, and auth caller modules (`service.py`, `sessions.py`, `router.py`). Remove all code attempting to store `ip_address` or `user_agent` until a trusted reverse-proxy design exists.
- Add comprehensive automated test coverage on real PostgreSQL:
  - Verify Part 1 request_id tests now pass.
  - Verify `audit_logs` constraints: BIGINT identity increments, `actor_type` check constraint, `details` NOT NULL and default, FK `RESTRICT` on workspace delete, FK `SET NULL` on user delete, inspector schema validation.
  - Verify `refresh_tokens` constraints: unique `token_hash`, `expires_at > issued_at`, cascade on user delete, `replaced_by_id` SET NULL, cookie attributes and Secure flag resolution, raw token absence in DB, garbage cookie 401, inactive user family revocation, multi-session logout isolation, log safety.
  - Verify migration 0003 lifecycle: upgrade head, step-downgrade to 0002, abort upgrade if rows exist, downgrade to base, re-upgrade to head.
- Documentation updates: ADR-027, `docs/DATABASE_SCHEMA.md` with accepted deviations for refresh_tokens, `docs/SECURITY.md`, `docs/LEARNING_NOTES.md` (< 25 lines with 2 interview Q&As), roadmap, status, context, and log.

### Files Created & Modified
- `backend/migrations/versions/0003_rebuild_audit_logs_to_match_schema_design.py`: Hand-crafted migration rebuilding `audit_logs` with data-loss abort guard.
- `backend/app/modules/audit/models.py`: Updated `AuditLog` model to match canonical schema.
- `backend/app/modules/audit/schemas.py`: Updated `AuditLogRead` schema.
- `backend/app/modules/audit/service.py`: Updated `record(...)` signature, sanitization, and request_id handling.
- `backend/app/modules/auth/service.py`: Updated audit event recording parameters; removed `ip_address` and `user_agent`.
- `backend/app/modules/auth/sessions.py`: Updated audit recording, family revocation for inactive users.
- `backend/app/modules/auth/router.py`: Removed passing `ip_address` and `user_agent` to auth services.
- `backend/tests/test_audit.py`: Added 64-char/37-char reproduction tests and 6 constraint/inspector tests.
- `backend/tests/test_sessions.py`: Added 10 constraint, cookie attribute, multi-session, and log safety tests.
- `backend/tests/test_migrations.py`: Added migration 0003 abort-with-rows, downgrade, and re-upgrade test.
- `docs/ARCHITECTURE_DECISIONS.md`: Added ADR-027.
- `docs/DATABASE_SCHEMA.md`: Updated `audit_logs` catalog and definition; added accepted deviations note for `refresh_tokens`.
- `docs/SECURITY.md`: Updated Audit Log and Multi-Tenant Isolation sections.
- `docs/LEARNING_NOTES.md`: Added Milestone 5b notes with 2 interview Q&As.
- `docs/PROJECT_STATUS.md`, `docs/PROJECT_CONTEXT.md`, `docs/ROADMAP.md`, `docs/TODO.md`: Updated project tracking.

---

## 2026-11-26 — Milestone 5: Sessions, Refresh Token Rotation, Reuse Detection & Audit Trail

### Objectives
- Complete Milestone 4 review follow-ups: close test gaps in `test_auth_security.py` (alg none, wrong iss, wrong aud, missing exp) and `test_auth_api.py` (pw > 128 chars, identical 401s, spy test for dummy-hash verification, case-insensitive login email, deleted user 401, demoted admin 403, /users pagination, log safety test), refine ADR-020 title, add ADR-023, and update `docs/DATABASE_SCHEMA.md`.
- Add session settings and code constants: `REFRESH_COOKIE_NAME = "kestrel_refresh"`, `REFRESH_COOKIE_PATH = "/api/v1/auth"`, `CSRF_HEADER_NAME = "X-Kestrel-Client"`, `CSRF_HEADER_VALUE = "web"`, `refresh_token_days` (1..30, default 7), `cookie_secure` with auto-resolution via `is_cookie_secure`.
- Define `RefreshToken` model in `app/modules/auth/models.py` with foreign keys, family ID, expiration check constraints, and helper properties (`is_expired`, `is_revoked`, `is_active`).
- Create `app/modules/audit/` module with `AuditLog` model with composite indexing on `(workspace_id, created_at DESC)` and `(workspace_id, action)`.
- Register models in `app/core/models_registry.py` and autogenerate migration `0002_create_refresh_tokens_and_audit_logs.py`.
- Implement `audit_service.record(...)` with structlog `request_id` extraction, transaction alignment, and defense-in-depth sanitization of sensitive keys.
- Implement `AuditLogRepository` and `GET /api/v1/audit-logs` endpoint (AdminUser only).
- Implement refresh token session service (`app/modules/auth/sessions.py`): `issue_refresh_token`, `rotate_refresh_token` with reuse detection revoking the entire token family, and idempotent `revoke_family_by_token`.
- Wire audit events into registration (`auth.register`), authentication (`auth.login`), rotation (`auth.refresh`), reuse detection (`auth.refresh_reuse_detected`), and logout (`auth.logout`).
- Add cookie management helper functions and update endpoints (`POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/logout`) with `X-Kestrel-Client` CSRF protection and cookie clearance on errors.
- Author comprehensive test suites (`test_sessions.py`, `test_audit.py`, `test_migrations.py`) reaching 87 automated tests running against real PostgreSQL with 100% pass rate.
- Author documentation: `docs/ROADMAP.md` (Milestones 1–19), `docs/SECURITY.md` (Sessions, Audit Log, Frontend Contract, updated gaps), ADR-024..026, and schema docs.

### Files Created & Modified
- `backend/app/core/config.py`: Added session constants and settings fields (`refresh_token_days`, `cookie_secure`, `is_cookie_secure`).
- `backend/app/modules/auth/models.py`: Added `RefreshToken` model with cascade delete and helper properties.
- `backend/app/modules/audit/models.py`: Added `AuditLog` entity with composite indexing.
- `backend/app/core/models_registry.py`: Centralized model discovery registry for Alembic.
- `backend/migrations/versions/0002_create_refresh_tokens_and_audit_logs.py`: Migration creating `refresh_tokens` and `audit_logs` tables and indexes.
- `backend/app/modules/auth/security.py`: Added `generate_refresh_token` and `hash_refresh_token`.
- `backend/app/modules/audit/schemas.py`: Added `AuditLogRead` Pydantic model.
- `backend/app/modules/audit/service.py`: Audit recording service with defense-in-depth key sanitization.
- `backend/app/modules/audit/repository.py`: Tenant-scoped `AuditLogRepository`.
- `backend/app/modules/audit/router.py`: `GET /api/v1/audit-logs` endpoint.
- `backend/app/modules/auth/sessions.py`: Session management, rotation, reuse detection, and family revocation.
- `backend/app/modules/auth/service.py`: Wired audit events into `register` and `authenticate`, removed internal commit from authenticate.
- `backend/app/modules/auth/router.py`: Added refresh cookies, `/refresh`, `/logout`, and CSRF protection.
- `backend/app/main.py`: Registered audit router and handlers for `InvalidRefreshToken` and `RefreshTokenReused`.
- `backend/tests/test_sessions.py`: 10 integration tests for cookies, rotation, reuse detection, and logout.
- `backend/tests/test_audit.py`: 7 integration tests for audit recording, defense-in-depth, RBAC, and tenancy isolation.
- `backend/tests/test_migrations.py`: Added migration 0002 step-downgrade and re-upgrade tests.
- `docs/ROADMAP.md`: Created complete 19-milestone project roadmap.
- `docs/SECURITY.md`: Added Sessions, Audit Log, and Frontend Contract sections; updated gaps table.
- `docs/ARCHITECTURE_DECISIONS.md`: Added ADR-024, ADR-025, and ADR-026.
- `docs/DATABASE_SCHEMA.md`: Marked migration 0002 implemented.
- `backend/README.md` & `README.md`: Updated layout, endpoints, and test counts.
- `docs/PROJECT_STATUS.md`, `docs/PROJECT_CONTEXT.md`, `docs/LEARNING_NOTES.md`, `docs/TODO.md`: Updated tracking.

---

## 2026-11-26 — Milestone 4: Authentication Core & Workspace-Scoped Multi-Tenancy

### Objectives
- Complete Milestone 3 Part 0 follow-ups: resolve Alembic deprecation warnings via `path_separator = os`, verify 100% naming convention alignment, prove dev-database isolation after full pytest suite run, verify zero credentials in `alembic.ini`.
- Add `argon2-cffi`, `pyjwt`, and `email-validator` dependencies to `pyproject.toml` and `uv.lock`.
- Extend `Settings` with `jwt_secret_key` (`SecretStr`, >= 32 chars, forbids `change_me`), `access_token_minutes` (1..60), `registration_enabled`, and immutable code constants (`HS256`, `kestrel`, `kestrel-api`).
- Append random 64-character URL-safe `JWT_SECRET_KEY` to local `.env` and configure dynamic session generation in `tests/conftest.py`.
- Implement `WorkspaceScopedRepository` (`app/core/tenancy.py`) as central multi-tenant isolation mechanism (ADR-022).
- Implement cryptographic utilities (`app/modules/auth/security.py`): Argon2id password hashing, timing-equalized dummy hash verification, JWT access token generation, and secure token decoding.
- Implement Pydantic auth schemas (`app/modules/auth/schemas.py`) with `extra="forbid"` for mass-assignment protection.
- Implement `UserRepository` and scoped/unscoped lookup functions (`app/modules/auth/repository.py`).
- Implement registration and authentication services (`app/modules/auth/service.py`) with domain exceptions and secure structlog events.
- Implement route dependencies (`app/modules/auth/dependencies.py`): `CurrentUser` and `AdminUser` with database-backed live authorization (ADR-021).
- Implement FastAPI routers (`/api/v1/auth` and `/api/v1/users`) and register domain exception handlers in `app/main.py`.
- Author comprehensive test suites covering security utilities, tenant isolation, and API endpoints (53 passing tests).
- Author `docs/SECURITY.md` and ADR-020 through ADR-022.

### Files Created & Modified
- `backend/app/core/tenancy.py`: `WorkspaceScopedRepository` multi-tenant base class.
- `backend/app/modules/auth/security.py`: Argon2id password hashing and JWT token handlers.
- `backend/app/modules/auth/schemas.py`: Pydantic request/response schemas with extra="forbid".
- `backend/app/modules/auth/repository.py`: Tenant-scoped `UserRepository` and unscoped auth lookups.
- `backend/app/modules/auth/service.py`: Registration and authentication services with timing mitigation.
- `backend/app/modules/auth/dependencies.py`: `get_current_user` and `require_admin` FastAPI dependencies.
- `backend/app/modules/auth/router.py`: Endpoints for `/register`, `/login`, and `/me`.
- `backend/app/modules/auth/users_router.py`: Administrative `/users` endpoint.
- `backend/app/main.py`: Domain exception handlers and `/api/v1` router inclusion.
- `backend/app/core/config.py`: Settings model with JWT secret validator and immutable constants.
- `backend/app/modules/auth/models.py`: Added relationship to `Workspace`.
- `backend/alembic.ini`: Added `path_separator = os` to eliminate deprecation warning.
- `backend/pyproject.toml` & `backend/uv.lock`: Pinned argon2-cffi, pyjwt, email-validator.
- `backend/tests/conftest.py`: Configured ephemeral dynamic JWT secret for test sessions.
- `backend/tests/test_config.py`: Added JWT secret validation and bounds tests.
- `backend/tests/test_auth_security.py`: Unit tests for password hashing and token claims.
- `backend/tests/test_tenancy.py`: Multi-tenant isolation and repository scoping tests.
- `backend/tests/test_auth_api.py`: Integration tests for auth routes, RBAC, and error mappings.
- `docs/SECURITY.md`: Comprehensive security architecture, threat model, and gap roadmap.
- `docs/ARCHITECTURE_DECISIONS.md`: Added ADR-020, ADR-021, and ADR-022.
- `backend/README.md` & `README.md`: Updated architecture layout, endpoints table, and status.
- `docs/PROJECT_STATUS.md` & `docs/PROJECT_CONTEXT.md`: Marked Milestone 4 complete.
- `docs/LEARNING_NOTES.md` & `docs/TODO.md`: Added Milestone 4 learning notes and next milestone tasks.

### Decisions & Deviations
- *ImmatureSignatureError on Token Decoding*: Fixed `test_create_access_token_claims_and_exclusion` to use `datetime.now(UTC) - timedelta(seconds=1)` so pyjwt doesn't reject future-dated timestamps against system clock during `iat` validation.
- *Ruff N818 and S105/S106 Exceptions*: Applied `# noqa: N818` to domain exceptions `RegistrationDisabled`, `EmailAlreadyRegistered`, and `InvalidCredentials` as specified by prompt requirements, and `# noqa: S105/S106` to standard OAuth2 `token_type="bearer"` schema attributes.

---

## 2026-11-26 — Milestone 3: Database Schema Design, Alembic Migrations & Identity Models

### Objectives
- Perform Milestone 2 review housekeeping: diagnose Starlette deprecation warning, add `test_docs_exposure.py` verifying `/docs` and `/redoc` return 404 in prod, and update ADR-004 to reflect SQLAlchemy 2.x typed API.
- Author complete database schema design document (`docs/DATABASE_SCHEMA.md`) cataloging all 11 relational tables, conventions, constraints, and Mermaid ERD.
- Initialize Alembic migration framework (`alembic.ini`, `migrations/env.py`, `script.py.mako`) integrated with dynamic Pydantic configuration.
- Implement SQLAlchemy 2.0 base architecture (`Base`, `NAMING_CONVENTION`, `UUIDPrimaryKeyMixin`, `TimestampMixin`).
- Implement `Workspace` and `User` models with `Role` enum, strict check constraints, foreign keys, and indexes.
- Author centralized metadata discovery in `app/core/models_registry.py` and generate first migration `0001_create_workspaces_and_users.py`.
- Establish test database fixtures in `tests/conftest.py` with automatic `kestrel_test` provisioning, migration to `head`, and transactional savepoint rollback per test.
- Author model constraint tests (`tests/test_models_workspaces_users.py`) and migration lifecycle tests (`tests/test_migrations.py`) using throwaway database `kestrel_migration_test`.
- Execute verification drills: `alembic upgrade head`, `alembic current`, `alembic history`, `alembic check` (0 drift), schema inspection via psql, and `downgrade base` / `upgrade head` cycle.
- Author ADR-016 (UUIDv4), ADR-017 (VARCHAR+CHECK), ADR-018 (Alembic & Test DB), and ADR-019 (SHA-256 vs Argon2id).

### Files Created & Modified
- `docs/DATABASE_SCHEMA.md`: Full catalog of 11 tables, constraints, index strategy, and ERD.
- `backend/alembic.ini`: Alembic migration configuration.
- `backend/migrations/env.py`: Environment script with programmatic URL injection bypassing interpolation bugs.
- `backend/migrations/script.py.mako`: Migration template.
- `backend/migrations/versions/0001_create_workspaces_and_users.py`: First migration script.
- `backend/app/core/base.py`: Declarative base with explicit PostgreSQL naming conventions and mixins.
- `backend/app/core/models_registry.py`: Central registry importing all models for Alembic discovery.
- `backend/app/modules/workspaces/models.py`: Workspace SQLAlchemy model.
- `backend/app/modules/auth/models.py`: User SQLAlchemy model and Role enum.
- `backend/tests/conftest.py`: Test fixtures for `kestrel_test` and transactional savepoint rollback.
- `backend/tests/test_docs_exposure.py`: API docs route exposure tests across environments.
- `backend/tests/test_models_workspaces_users.py`: Constraint, relationship, and default tests for Workspace and User.
- `backend/tests/test_migrations.py`: Migration lifecycle and drift tests with throwaway DB.
- `backend/pyproject.toml` & `backend/uv.lock`: Added `alembic` (v1.20.1) dependency.
- `backend/README.md`: Documented Alembic migration commands and test DB strategy.
- `README.md`: Added database migration instructions and updated status.
- `docs/ARCHITECTURE_DECISIONS.md`: Added ADR-016 through ADR-019.
- `docs/PROJECT_STATUS.md`: Marked Milestone 3 complete.
- `docs/PROJECT_CONTEXT.md`: Updated milestone status and backend layout.
- `docs/LEARNING_NOTES.md`: Added Milestone 3 learning notes.
- `docs/TODO.md`: Ticked Milestone 3 and refined Milestone 4.

### Decisions & Deviations
- *Alembic URL Escaping*: Instead of setting `config.set_main_option("sqlalchemy.url", ...)`, which fails when passwords contain `%` characters due to ConfigParser interpolation, we pass the URL via `config.attributes["sqlalchemy_url"] = ...` and read it in `env.py`.
- *Savepoint Test Nesting*: When testing constraint violations with `pytest.raises(IntegrityError)`, `db_session.add()` and `db_session.flush()` must occur inside `with pytest.raises(IntegrityError), db_session.begin_nested():` so that `begin_nested()` creates the savepoint before the auto-flush and safely catches the constraint error.
- *Native UUID Default*: Used native PostgreSQL 13+ `gen_random_uuid()` as server default, avoiding additional extensions like `pgcrypto` or `uuid-ossp`.

---

## 2026-11-26 — Milestone 2: Backend Skeleton & Operational Probes

### Objectives
- Transition development workflow to direct-to-main with milestone tags and automated pre-push quality gates (ADR-015).
- Establish `uv` tooling with `pyproject.toml` and deterministic `uv.lock` for backend dependencies (ADR-013).
- Implement FastAPI application factory (`create_app`), Pydantic Settings with `SecretStr` password masking, and Structlog logging.
- Implement `RequestIdAndLoggingMiddleware` extracting, validating, and generating `X-Request-ID`, and logging access duration.
- Implement lazy database connection module (`app/core/db.py`) with connection pooling and `get_db` session dependency.
- Expose unversioned liveness (`GET /health`) and readiness (`GET /health/ready`) probes at the server root (ADR-014).
- Author automated pytest suite running against real PostgreSQL container with 100% pass rate.
- Execute live server verification and failure drill (stopping/starting PostgreSQL) with explicit timeouts.

### Files Created & Modified
- `backend/pyproject.toml`: Project metadata, dependencies, ruff, and pytest configurations.
- `backend/uv.lock`: Deterministic dependency lockfile.
- `backend/app/main.py`: `create_app()` factory, middleware registration, and router inclusion.
- `backend/app/core/config.py`: Settings model loading from environment and root `.env` with secret masking.
- `backend/app/core/db.py`: Lazy SQLAlchemy engine, sessionmaker, and `get_db` generator.
- `backend/app/core/logging.py`: Structlog configuration supporting JSON (prod) and console (dev/test) formatters.
- `backend/app/core/middleware.py`: Request-ID propagation and structured access duration logging.
- `backend/app/modules/platform/schemas.py`: Response schemas for `/health` and `/health/ready`.
- `backend/app/modules/platform/router.py`: Liveness and readiness probe implementations using sync `def`.
- `backend/tests/conftest.py`: Fixtures with cache clearing and dependency override teardown.
- `backend/tests/test_config.py`: Configuration and secret masking test cases.
- `backend/tests/test_health.py`: Live and unreachable database probe test cases.
- `backend/tests/test_request_id.py`: Request-ID generation and validation test cases.
- `backend/README.md`: Backend documentation, layout, commands, and endpoint table.
- `README.md`: Added backend running instructions and updated status to Milestone 2.
- `docs/ARCHITECTURE_DECISIONS.md`: Added ADR-013 (`uv`), ADR-014 (probe routing conventions), and ADR-015 (direct-to-main workflow).
- `docs/PROJECT_STATUS.md`: Marked Milestone 2 complete.
- `docs/PROJECT_CONTEXT.md`: Recorded direct-to-main workflow, package versions, and Milestone 3 next action.
- `docs/LEARNING_NOTES.md`: Added Milestone 2 learning notes (< 45 lines).
- `docs/TODO.md`: Ticked Milestone 2 tasks and added Milestone 3.

### Decisions & Deviations
- Fast-forward merged Milestone 1 to `main`, pushed to `origin/main`, and tagged `m1-docker-postgres`.
- Switched to direct-to-main workflow without milestone feature branches, enforcing pre-push quality gates.
- Resolved Ruff rule B008 by using modern `Annotated[Session, Depends(get_db)]` parameter typing in platform router.
- Configured Ruff per-file-ignores for `tests/*` covering `S101` (assert), `S105` (hardcoded password strings in test data), and `S106`.
- Live failure drill executed with detached uvicorn process and `--max-time 5` curl timeouts; verified 503 during outage and recovery to 200 after container restart. Zero secrets leaked in logs.

---

## 2026-11-26 — Milestone 1: Docker Environment & PostgreSQL Development Database

### Objectives
- Verify Docker daemon and Docker Compose availability on Windows 11 host.
- Author `.env.example` template with placeholder values for PostgreSQL configuration.
- Generate local `.env` with a 36-character cryptographically secure password (alphanumeric).
- Create `compose.yaml` with pinned `postgres:17` image, localhost-only binding (`127.0.0.1:5432`), named volume `kestrel_pgdata`, and `pg_isready` healthcheck.
- Verify container startup, healthy status, `SELECT version()`, volume persistence across `down`/`up` cycles, and complete table cleanup.
- Enforce strict secret hygiene: ensure `.env` remains ignored and real secrets never leak into git.

---

## 2026-11-25 — Milestone 0: Repository Bootstrap and Documentation System

### Objectives
- Initialize empty Git repository with branch safety on `main`.
- Configure robust `.gitignore` and `.gitattributes` to prevent secret leaks and handle cross-platform line endings.
- Establish monorepo skeleton (`backend/`, `frontend/`, `infra/`, `docs/`, `.github/`).
- Author core project documentation (PRD, Architecture, ADRs, Context, Status, Learning Notes, TODO).
- Verify secret exclusion and branch tracking on remote.
