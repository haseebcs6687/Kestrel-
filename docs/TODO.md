# Project TODO & Remaining Planning

## Completed Tasks
- [x] **Milestone 0**: Repository bootstrap, folder structure, git safety, PR template, PRD, Architecture, and ADRs.
- [x] **Milestone 1**: Docker Desktop installation, Docker Compose setup with pinned PostgreSQL 17, `127.0.0.1` binding, named volume persistence, and `pg_isready` healthcheck.
- [x] **Milestone 2**: FastAPI backend skeleton, configuration with secret masking, structlog with request IDs, database connection module, unversioned `/health` and `/health/ready` probes, pytest test suite, and direct-to-main workflow.
- [x] **Milestone 3**: Database schema design (`docs/DATABASE_SCHEMA.md`), Alembic migration environment (`0001_create_workspaces_and_users.py`), SQLAlchemy 2.0 `Workspace` and `User` models, and test database infrastructure with transactional savepoints.
- [x] **Milestone 4**: Authentication core: Argon2id password hashing, JWT bearer tokens, registration (`/register`), authentication (`/login`), profile (`/me`), RBAC (admin/viewer), workspace-scoped repository isolation (`WorkspaceScopedRepository`), and security architecture (`docs/SECURITY.md`).
- [x] **Milestone 5**: Sessions and audit: DB-backed opaque refresh tokens with rotation and reuse detection, HttpOnly cookies, append-only audit trail (`audit_logs`), and `/api/v1/audit-logs` endpoint.

## Remaining Planning Tasks
- [x] **Database Schema & ERD**: Detailed entity-relationship model covering all 12 tables, constraints, indexes, and Mermaid ERD in `docs/DATABASE_SCHEMA.md`.
- [ ] **API Specification**: OpenAPI 3.1 specification for all endpoints across auth, workspaces, api_keys, providers, ingest, analytics, pricing, alerts, and platform.
- [ ] **Detailed Folder Structure**: Complete file tree layout for `backend/app/` (modules, schemas, models, repositories) and `frontend/src/` (components, hooks, pages).
- [x] **Security Architecture & Key Management**: Argon2id configuration, JWT token security constants, dynamic database-backed authorization, session rotation, audit logging, and secret hygiene in `docs/SECURITY.md` and ADR-020..026.
- [ ] **Monitoring Architecture**: Prometheus metric definitions (counters, histograms for ingest and worker) and Grafana dashboard provisioning.
- [ ] **Testing Strategy**: Comprehensive plan for unit tests, repository tenant-isolation suites, integration tests with real PostgreSQL, and Playwright E2E flows.
- [ ] **Deployment Architecture**: Production Dockerfile builds, multi-stage optimization, Nginx reverse proxy configuration, and volume backup strategies.
- [x] **Roadmap & Milestone Schedule**: Detailed breakdown of Milestones 1 through 19 with explicit acceptance criteria in `docs/ROADMAP.md`.
- [ ] **Risk Register & Mitigations**: Analysis of technical risks (e.g., ingestion write amplification, provider rate limits) and corresponding fallbacks.
- [ ] **Phase 2 UI/UX Design System**: Token definitions (typography, spacing, colors) matching Minia aesthetic without asset copying.

## Upcoming Milestones
- **Milestone 6**: Ingestion API endpoint (`POST /api/v1/ingest/events`), API key authentication (`api_keys`), and telemetry payload validation.
- **Milestone 7**: Thin Python telemetry client wrapper SDK (sync/async buffer queue with background thread flush).
- **Milestone 8**: Provider connections (`provider_connections`), Fernet credential encryption, and latency health probes.
- **Milestone 9**: Model pricing rate cards (`model_prices`) and real-time USD cost calculation.
- **Milestone 10**: Usage analytics engine, pre-aggregated rollups (`usage_hourly`), and latency percentiles.
- **Milestone 11**: Alert rules engine (`alert_rules`, `alerts`) and incident deduplication lifecycle.
- **Milestone 12**: Outbound notification webhooks (Slack, Discord, generic) with delivery retry policies.
- **Milestone 13**: Rate limiting (Redis sliding-window) and edge hardening (CORS, security headers).
- **Milestone 14**: Frontend foundations (Vite, React 19, TypeScript, Tailwind CSS, shadcn/ui).
- **Milestone 15**: Frontend auth flows, in-memory token storage, silent background refresh, and route guards.
- **Milestone 16**: Observability dashboard, live velocity graphs, and cost breakdown charts.
- **Milestone 17**: Incident manager, audit log viewer, and API key management console.
- **Milestone 18**: Prompt evaluation sandbox, model benchmarking, and side-by-side comparison matrix.
- **Milestone 19**: Production packaging, Docker multi-stage images, and GitHub Actions CI/CD workflows.
