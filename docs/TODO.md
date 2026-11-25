# Project TODO & Remaining Planning

## Completed Tasks
- [x] **Milestone 0**: Repository bootstrap, folder structure, git safety, PR template, PRD, Architecture, and ADRs.
- [x] **Milestone 1**: Docker Desktop installation, Docker Compose setup with pinned PostgreSQL 17, `127.0.0.1` binding, named volume persistence, and `pg_isready` healthcheck.

## Remaining Planning Tasks
- [ ] **Database Schema & ERD**: Detailed entity-relationship model covering workspaces, users, api_keys, providers, events, pricing, alerts, incidents, and audit_logs.
- [ ] **API Specification**: OpenAPI 3.1 specification for all endpoints across auth, workspaces, api_keys, providers, ingest, analytics, pricing, alerts, and platform.
- [ ] **Detailed Folder Structure**: Complete file tree layout for `backend/app/` (modules, schemas, models, repositories) and `frontend/src/` (components, hooks, pages).
- [ ] **Security Architecture & Key Management**: Fernet master key rotation policy, Argon2 parameter configuration, and JWT signing key management.
- [ ] **Monitoring Architecture**: Prometheus metric definitions (counters, histograms for ingest and worker) and Grafana dashboard provisioning.
- [ ] **Testing Strategy**: Comprehensive plan for unit tests, repository tenant-isolation suites, integration tests with real PostgreSQL, and Playwright E2E flows.
- [ ] **Deployment Architecture**: Production Dockerfile builds, multi-stage optimization, Nginx reverse proxy configuration, and volume backup strategies.
- [ ] **Roadmap & Milestone Schedule**: Detailed breakdown of Milestones 2 through 9 with explicit acceptance criteria.
- [ ] **Risk Register & Mitigations**: Analysis of technical risks (e.g., ingestion write amplification, provider rate limits) and corresponding fallbacks.
- [ ] **Phase 2 UI/UX Design System**: Token definitions (typography, spacing, colors) matching Minia aesthetic without asset copying.

## Next Milestone Action
- **Milestone 2**: FastAPI skeleton, Pydantic settings/config, `/health` endpoint, and synchronous SQLAlchemy 2.0 database connectivity check against PostgreSQL container.
