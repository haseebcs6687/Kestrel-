# Project Context — Kestrel AI Control Center

## Current State
- **Current Phase**: Phase 1 implementation underway.
- **Completed Milestones**:
  - Milestone 0: Repository bootstrap and documentation system.
  - Milestone 1: Docker Compose PostgreSQL 17 environment (Tag: `m1-docker-postgres`).
  - Milestone 2: FastAPI backend skeleton, configuration, logging, request IDs, database connectivity, and health probes (Tag: `m2-backend-skeleton`).
  - Milestone 3: Database schema design, Alembic migrations, `workspaces` and `users` models, and dedicated test databases (Tag: `m3-alembic-identity`).
  - Milestone 4: Authentication core, Argon2id password hashing, JWT bearer tokens, RBAC, and workspace-scoped repository isolation (Tag: `m4-auth-core`).
  - Milestone 5: Sessions and audit: DB-backed opaque refresh tokens with rotation and reuse detection, HttpOnly cookies, and append-only audit trail (Tag: `m5-sessions-audit`).
  - Milestone 5b: Corrective rebuild of `audit_logs` via migration 0003, request-ID 64-character fix, model and repository updates, and full constraint test coverage (Tag: `m5b-schema-fix`).
- **Current Milestone**: Milestone 5b complete; preparing Milestone 6.
- **Known Bugs**: None.
- **Next Action**: Milestone 6 (API keys & Ingestion API `POST /api/v1/ingest/events`).

## Development Workflow
- **Direct-to-Main**: Development proceeds directly on branch `main` using Conventional Commits. No feature branch overhead or pull request delays for solo implementation.
- **Milestone Tags**: Each completed milestone is tagged on `main` (e.g. `m1-docker-postgres`, `m2-backend-skeleton`, `m5-sessions-audit`) to provide immutable rollback points.
- **Pre-Push Quality Gate**: Before pushing to `main`, four automated checks must pass:
  1. `uv run ruff check .`
  2. `uv run ruff format --check .`
  3. `uv run pytest -v` (against real PostgreSQL container, 106 tests passing)
  4. `uv run alembic check` (zero drift)
  5. Secret audit (`git grep -F` for real database password, JWT secrets, and regex for key patterns `sk-`, `AIza`, `gsk_`).

## Architecture & Technology Summary
1. Modular monolith architecture with a separate worker process sharing database models and code.
2. Ingest-API-first telemetry model (`POST /api/v1/ingest/events`) using workspace API key authentication.
3. Backend powered by Python 3.13, FastAPI, SQLAlchemy 2.0 (synchronous), Alembic, and PostgreSQL 17.
4. Dependency management driven by `uv` using `pyproject.toml` and `uv.lock`.
5. Frontend single-page application built with React, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query, and Apache ECharts.
6. Observability driven by Prometheus metrics scraping (`/metrics`) and Grafana operational dashboards.

## Backend Structure
```
backend/
  app/
    main.py                 # Application factory create_app() and entrypoint
    core/
      base.py               # DeclarativeBase, naming conventions, and common mixins
      config.py             # Pydantic Settings loading from env and root .env
      db.py                 # Lazy SQLAlchemy engine, sessionmaker, and get_db dependency
      logging.py            # Structlog configuration (JSON for prod, console for dev)
      middleware.py         # Request-ID tracking and structured access logging
      models_registry.py    # Centralized model registry for Alembic discovery
      tenancy.py            # WorkspaceScopedRepository multi-tenant base class
    modules/
      audit/                # Operational and security audit logging
        models.py           # AuditLog model with composite indexing
        repository.py       # Workspace-scoped audit log querying
        router.py           # /audit-logs administrative endpoint
        schemas.py          # AuditLogRead Pydantic schema
        service.py          # Audit recording service with defense-in-depth sanitization
      auth/                 # User model, authentication and role definitions
        dependencies.py     # CurrentUser and AdminUser token dependencies
        models.py           # User and RefreshToken SQLAlchemy models and Role enum
        repository.py       # Scoped UserRepository and unscoped lookups
        router.py           # /auth endpoints (register, login, refresh, logout, me)
        schemas.py          # Pydantic schemas for auth and profile
        security.py         # Argon2id password hashing and JWT/refresh token helpers
        service.py          # Registration, login authentication workflows
        sessions.py         # Refresh token rotation, reuse detection, and revocation
        users_router.py     # /users administrative listing endpoint
      platform/             # Liveness (/health) and readiness (/health/ready) probes
        router.py
        schemas.py
      workspaces/           # Workspace model and multi-tenant management
        models.py
  migrations/               # Alembic database migrations environment
    versions/
      0001_create_workspaces_and_users.py
      0002_create_refresh_tokens_and_audit_logs.py
  tests/
    conftest.py             # TestClient, kestrel_test DB engine, and savepoint fixtures
    test_audit.py           # Audit service, sanitization, and endpoint RBAC/isolation tests
    test_auth_api.py        # Registration, login, profile, and RBAC endpoint tests
    test_auth_security.py   # Argon2id and JWT unit tests
    test_config.py          # Configuration loading and secret masking tests
    test_docs_exposure.py   # Swagger/OpenAPI exposure tests across environments
    test_health.py          # /health and /health/ready liveness and readiness tests
    test_migrations.py      # Alembic upgrade/downgrade/upgrade lifecycle and drift tests
    test_models_workspaces_users.py # Workspace and User ORM models & constraint tests
    test_request_id.py      # X-Request-ID propagation, validation, and generation tests
    test_sessions.py        # Refresh token rotation, reuse detection, cookie, and logout tests
    test_tenancy.py         # WorkspaceScopedRepository isolation tests
```
