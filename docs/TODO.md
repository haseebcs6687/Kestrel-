# Project TODO & Remaining Planning

## Completed Tasks
- [x] **Milestone 0**: Repository bootstrap, folder structure, git safety, PR template, PRD, Architecture, and ADRs.
- [x] **Milestone 1**: Docker Desktop installation, Docker Compose setup with pinned PostgreSQL 17, `127.0.0.1` binding, named volume persistence, and `pg_isready` healthcheck.
- [x] **Milestone 2**: FastAPI backend skeleton, configuration with secret masking, structlog with request IDs, database connection module, unversioned `/health` and `/health/ready` probes, pytest test suite, and direct-to-main workflow.
- [x] **Milestone 3**: Database schema design (`docs/DATABASE_SCHEMA.md`), Alembic migration environment (`0001_create_workspaces_and_users.py`), SQLAlchemy 2.0 `Workspace` and `User` models, and test database infrastructure with transactional savepoints.

## Remaining Planning Tasks
- [x] **Database Schema & ERD**: Detailed entity-relationship model covering all 11 tables, constraints, indexes, and Mermaid ERD in `docs/DATABASE_SCHEMA.md`.
- [ ] **API Specification**: OpenAPI 3.1 specification for all endpoints across auth, workspaces, api_keys, providers, ingest, analytics, pricing, alerts, and platform.
- [ ] **Detailed Folder Structure**: Complete file tree layout for `backend/app/` (modules, schemas, models, repositories) and `frontend/src/` (components, hooks, pages).
- [ ] **Security Architecture & Key Management**: Fernet master key rotation policy, Argon2 parameter configuration, and JWT signing key management.
- [ ] **Monitoring Architecture**: Prometheus metric definitions (counters, histograms for ingest and worker) and Grafana dashboard provisioning.
- [ ] **Testing Strategy**: Comprehensive plan for unit tests, repository tenant-isolation suites, integration tests with real PostgreSQL, and Playwright E2E flows.
- [ ] **Deployment Architecture**: Production Dockerfile builds, multi-stage optimization, Nginx reverse proxy configuration, and volume backup strategies.
- [ ] **Roadmap & Milestone Schedule**: Detailed breakdown of Milestones 4 through 10 with explicit acceptance criteria.
- [ ] **Risk Register & Mitigations**: Analysis of technical risks (e.g., ingestion write amplification, provider rate limits) and corresponding fallbacks.
- [ ] **Phase 2 UI/UX Design System**: Token definitions (typography, spacing, colors) matching Minia aesthetic without asset copying.

## Upcoming Milestones
- **Milestone 4**: Authentication, user session management, password hashing (Argon2id), JWT issuance, and workspace API key management.
- **Milestone 5**: Ingestion API endpoint (`POST /ingest/events`) and thin Python client wrapper library.
- **Milestone 6**: Provider adapters, connection test endpoints, and health monitoring probes.
- **Milestone 7**: Analytics engine (usage, costs, latency percentiles).
- **Milestone 8**: Alert rules engine and incident lifecycle management.
- **Milestone 9**: Frontend dashboard, charts, and shadcn/ui components.
- **Milestone 10**: End-to-end integration, load validation, and demo polish.
- **Milestone 11 (CI/CD)**: GitHub Actions continuous integration pipelines (lint, test, build).
