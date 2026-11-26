# Implementation Log — Kestrel AI Control Center

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
