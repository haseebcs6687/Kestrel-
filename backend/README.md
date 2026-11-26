# Backend — Kestrel AI Control Center

## Purpose
FastAPI application and background worker process providing telemetry ingestion, health monitoring, operational alerts, and analytical query interfaces for LLM-powered applications.

## Folder Layout
```
backend/
  app/
    __init__.py
    main.py                 # Application factory create_app() and entrypoint
    core/
      __init__.py
      base.py               # DeclarativeBase, naming conventions, and common mixins
      config.py             # Pydantic Settings loading from env and root .env
      db.py                 # Lazy SQLAlchemy engine, sessionmaker, and get_db dependency
      logging.py            # Structlog configuration (JSON for prod, console for dev)
      middleware.py         # Request-ID tracking and structured access logging
      models_registry.py    # Centralized model registry for Alembic discovery
      tenancy.py            # WorkspaceScopedRepository multi-tenant base class
    modules/
      __init__.py
      auth/                 # User model, authentication and role definitions
        __init__.py
        dependencies.py     # CurrentUser and AdminUser token dependencies
        models.py           # User SQLAlchemy model and Role enum
        repository.py       # Scoped UserRepository and unscoped lookups
        router.py           # /auth endpoints (register, login, me)
        schemas.py          # Pydantic schemas for auth and profile
        security.py         # Argon2id password hashing and JWT token handlers
        service.py          # Registration, login authentication workflows
        users_router.py     # /users administrative listing endpoint
      platform/             # Liveness (/health) and readiness (/health/ready) probes
        __init__.py
        router.py
        schemas.py
      workspaces/           # Workspace model and multi-tenant management
        __init__.py
        models.py
  migrations/               # Alembic database migrations environment
    env.py
    script.py.mako
    versions/
      0001_create_workspaces_and_users.py
  tests/
    __init__.py
    conftest.py             # TestClient, kestrel_test DB engine, and savepoint fixtures
    test_auth_api.py        # Registration, login, profile, and RBAC endpoint tests
    test_auth_security.py   # Argon2id and JWT unit tests
    test_config.py          # Configuration loading and secret masking tests
    test_docs_exposure.py   # Swagger/OpenAPI exposure tests across environments
    test_health.py          # /health and /health/ready liveness and readiness tests
    test_migrations.py      # Alembic upgrade/downgrade/upgrade lifecycle and drift tests
    test_models_workspaces_users.py # Workspace and User ORM models & constraint tests
    test_request_id.py      # X-Request-ID propagation, validation, and generation tests
    test_tenancy.py         # WorkspaceScopedRepository isolation tests
  alembic.ini               # Alembic migration configuration
  pyproject.toml            # Project definition, runtime/dev dependencies, ruff, and pytest config
  uv.lock                   # Deterministic dependency lockfile
```

## Commands & Workflows
All commands run from the `backend/` directory using `uv`:
- **Install dependencies**: `uv sync`
- **Run development server**: `uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload`
- **Run automated test suite**: `uv run pytest -v`
- **Lint codebase**: `uv run ruff check .`
- **Format check**: `uv run ruff format --check .`
- **Format codebase**: `uv run ruff format .`

## Database Migrations
Alembic manages all schema evolution against PostgreSQL:
- **Apply migrations**: `uv run alembic upgrade head`
- **Rollback single migration**: `uv run alembic downgrade -1`
- **Rollback to base**: `uv run alembic downgrade base`
- **Current revision**: `uv run alembic current`
- **Migration history**: `uv run alembic history --verbose`
- **Check schema drift**: `uv run alembic check`

## Test Database Strategy
- **Isolation**: Tests run against a dedicated `kestrel_test` database (auto-provisioned from the maintenance database if absent) rather than the development database (`kestrel`).
- **Transactional Savepoints**: Each test function runs within a nested transaction (`join_transaction_mode="create_savepoint"`). On fixture teardown, the transaction rolls back, leaving the database completely clean without slow table re-creation.
- **Migration Verification**: `test_migrations.py` creates an isolated throwaway database (`kestrel_migration_test`), exercises the full upgrade/downgrade/upgrade lifecycle, checks for drift with `alembic check`, and automatically drops the throwaway database on completion.
- **Safety Guard**: Test fixtures assert that database names must end with `_test` before performing any database drops or migrations.

## Endpoints
| Method | Path | Description | Versioning | Auth |
|---|---|---|---|---|
| `GET` | `/health` | Liveness probe returning `200 {"status": "ok"}` | Unversioned root | Public |
| `GET` | `/health/ready` | Readiness probe verifying DB ping via `SELECT 1` | Unversioned root | Public |
| `POST`| `/api/v1/auth/register` | Register admin user and create workspace | Versioned `/api/v1` | Public |
| `POST`| `/api/v1/auth/login` | Authenticate credentials and issue bearer JWT | Versioned `/api/v1` | Public |
| `GET` | `/api/v1/auth/me` | Fetch authenticated user profile & workspace | Versioned `/api/v1` | Bearer Token |
| `GET` | `/api/v1/users` | List users in caller's workspace (paginated) | Versioned `/api/v1` | Admin Only |
| `GET` | `/docs` | Interactive Swagger API documentation (disabled in prod) | Unversioned root | Public |
| `GET` | `/openapi.json`| OpenAPI 3.1 specification schema (disabled in prod) | Unversioned root | Public |

> [!NOTE]
> Infrastructure health and readiness probes are unversioned at the root (`/health`, `/health/ready`), whereas domain product APIs will reside under `/api/v1` in upcoming milestones.
