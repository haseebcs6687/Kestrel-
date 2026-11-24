# Backend — Kestrel AI Control Center

## Purpose
Backend API and background worker process for Kestrel AI Control Center, providing ingestion endpoints, telemetry analytics, provider health checks, alert management, and administrative services for LLM-powered applications.

## Planned Layout & Architecture
- **Framework & Runtime**: Python 3.13, FastAPI, Pydantic v2, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL.
- **Outbound HTTP**: Async `httpx` for external provider calls (health checks, model listing).
- **Background Worker**: Separate Python process executing APScheduler for health monitoring, alert evaluations, periodic aggregation rollups, and data retention.
- **Modular Monolith**:
  - `backend/app/modules/auth/`
  - `backend/app/modules/workspaces/`
  - `backend/app/modules/api_keys/`
  - `backend/app/modules/providers/`
  - `backend/app/modules/ingest/`
  - `backend/app/modules/analytics/` (usage, cost, performance)
  - `backend/app/modules/pricing/`
  - `backend/app/modules/alerts/`
  - `backend/app/modules/audit/`
  - `backend/app/modules/settings/`
  - `backend/app/modules/platform/` (health checks, Prometheus metrics, structured logging)
- **Module Layering**: Every domain module enforces a 3-layer pattern: `router -> service -> repository` with Pydantic schemas validating inputs and outputs at API boundaries.
- **Tenant Isolation**: Every database interaction passes through workspace-scoped repositories requiring explicit `workspace_id`.
