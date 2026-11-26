# Kestrel Engineering Roadmap

## Phased Build Philosophy

Kestrel AI Control Center is built according to a layered, defense-in-depth architectural roadmap. The engineering sequence prioritizes:
1. **Foundational Reliability & Security**: Establishing containerized data stores, modular monolith structure, strict typing, cryptographic identity, and tenant isolation before domain data arrives.
2. **Data Plane & Telemetry**: Hardened ingestion pipelines, cryptographic API key authentication, upstream provider management, and exact cost computation.
3. **Analytics & Automated Governance**: High-throughput time-series rollups, threshold monitoring, and incident alerting.
4. **User Interface & Client Experience**: Responsive React/TypeScript web client with strict in-memory token hygiene and real-time observability charts.
5. **Advanced Evaluation & Production Hardening**: Model benchmarking, prompt sandbox, multi-step tracing, and containerized production deployment.

---

## Milestone Breakdown (1–19)

| Milestone | Title | Scope Summary | Status |
|---|---|---|---|
| **M1** | Docker Environment & PostgreSQL | Docker Compose PostgreSQL 17, 127.0.0.1 binding, volume persistence, and health checks. | **Complete** |
| **M2** | Backend Skeleton & Probes | FastAPI application skeleton, Pydantic settings, Structlog with request IDs, and `/health` probes. | **Complete** |
| **M3** | Database Schema & Identity Migrations | Alembic migration framework, `workspaces` and `users` models, and dedicated test databases. | **Complete** |
| **M4** | Authentication Core & Multi-Tenancy | Argon2id hashing, 15-minute JWT tokens, `/register`, `/login`, `/me`, RBAC, and `WorkspaceScopedRepository`. | **Complete** |
| **M5** | Sessions & Audit Logging | DB-backed opaque refresh tokens with rotation and reuse detection, HttpOnly cookies, and append-only audit trail. | **Complete** |
| **M6** | API Keys & Telemetry Ingestion | `api_keys` model with SHA-256 hashes, prefix display, and high-throughput `POST /api/v1/ingest/events` endpoint. | Pending |
| **M7** | Thin Python Client SDK | Asynchronous and synchronous Python telemetry wrapper library with local queueing and batch flush. | Pending |
| **M8** | Provider Connections & Probes | `provider_connections` table, Fernet credential encryption, automated provider health checks, and latency probes. | Pending |
| **M9** | Model Pricing & Cost Engine | `model_prices` table with versioned rate cards; automated token calculation and USD cost accounting on ingestion. | Pending |
| **M10** | Usage Analytics & Rollups | `usage_hourly` pre-aggregated summaries, time-series rollups, spend velocity, and percentile latency queries. | Pending |
| **M11** | Alert Rules & Incident Engine | Threshold condition evaluation for spend, error rate, and latency spikes; deduplicated incident lifecycle. | Pending |
| **M12** | Alert Webhooks & Dispatcher | Outbound webhook delivery system (Slack, Discord, generic webhooks) with retry policies and signature headers. | Pending |
| **M13** | Rate Limiting & Edge Hardening | Redis sliding-window rate limiting on auth and ingestion routes, CORS policy, and security headers. | Pending |
| **M14** | Frontend Foundations & Design System | Vite, React 19, TypeScript, Tailwind CSS, shadcn/ui primitives, and shared API client architecture. | Pending |
| **M15** | Frontend Auth & Session Flow | Auth views (Login/Register), in-memory access token storage, silent background refresh, and route guards. | Pending |
| **M16** | Dashboard & Analytics UI | Observability overview, live token throughput, cost breakdown charts, and provider status indicators. | Pending |
| **M17** | Alerts, Logs & Audit Explorer UI | Incident resolution view, real-time audit log explorer with filters, and API key management console. | Pending |
| **M18** | Evaluation Sandbox & Benchmarking | Side-by-side prompt evaluation, multi-provider model comparison, latency/cost benchmarking tool. | Pending |
| **M19** | Production Packaging & CI/CD | Multi-stage Docker production images, GitHub Actions CI/CD workflows, automated backup runbooks. | Pending |
