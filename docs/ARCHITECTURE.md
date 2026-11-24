# Architecture Specification — Kestrel AI Control Center

## 1. Process Topology

```
  Your apps + Python wrapper -> POST /ingest/events (workspace API key) -> FastAPI API process
  Browser (React SPA) -> HTTPS + JWT -> FastAPI API process
  FastAPI API (auth, ingest, analytics, providers, alerts, pricing, audit, settings) -> PostgreSQL
  Worker process (health checks, alert evaluation, rollups, retention) -> PostgreSQL, and -> provider APIs (Groq, Gemini, Ollama)
  Prometheus scrapes /metrics on API and worker -> Grafana
```

## 2. Invariant Architectural Rules

1. **Decoupled Ingestion**: Telemetry ingestion (`POST /ingest/events`) must never depend on external LLM provider availability or responsiveness. Ingestion writes directly to PostgreSQL.
2. **Central Tenant Isolation**: Every database query must pass through a workspace-scoped repository layer that enforces `workspace_id` filtering. Multi-tenancy leaks are treated as critical security failures.
3. **Isolated Shared-Code Processes**: The FastAPI API process and APScheduler Worker process run as separate OS containers/processes sharing common domain models, schemas, and database mappings.
4. **Strict Module Layering**: Every backend domain module adheres to a three-tier architecture:
   - `Router`: HTTP request/response validation, status codes, route definitions.
   - `Service`: Business rules, validation, workflow orchestration.
   - `Repository`: Database queries, tenant scoping, transaction boundaries.
   - Pydantic schemas validate all data crossing boundaries into and out of each module.

## 3. Backend Modules

- `auth`: User registration, authentication, argon2 password hashing, JWT generation, and role checks (`admin`, `viewer`).
- `workspaces`: Tenant workspace creation, metadata, and user-workspace associations.
- `api_keys`: Ingestion API key generation, revocation, verification, and SHA-256 hash storage.
- `providers`: Upstream provider configurations, Fernet credential encryption, connection testing, and model catalogues.
- `ingest`: High-throughput telemetry event ingestion, idempotency verification, and price snapshotting.
- `analytics`: Aggregated query interfaces for usage (tokens/requests), costs, and latency performance percentiles (`p50`, `p95`, `p99`).
- `pricing`: Provider and model rate cards, historical price versioning, and pricing update tracking.
- `alerts`: Alert rule definitions, threshold evaluation triggers, incident state lifecycle (`firing`/`resolved`), and in-app notifications.
- `audit`: Immutable event logging for administrative operations (logins, key generation, provider edits, pricing adjustments).
- `settings`: Application-level configuration and workspace preferences.
- `platform`: Cross-cutting operational endpoints: `/health` liveness/readiness probes, Prometheus `/metrics` instrumentation, and structured JSON logging with request IDs.

## 4. Provider Adapters

Provider interactions (connection tests, model listings, health probes) are decoupled through an adapter pattern:
- **`ProviderAdapter` (Abstract Base Class)**:
  - `test_connection() -> ProviderCheckResult`
  - `list_models() -> list[ProviderModel]`
  - `health_check() -> ProviderCheckResult`
  - Returns standardized result models: `status` (`healthy`, `degraded`, `unreachable`), `latency_ms`, and `error_message`.
- **`OpenAICompatibleAdapter`**: Handles OpenAI-compatible endpoints (Groq, Ollama `/v1`, and future vLLM/OpenAI integrations).
- **`GeminiAdapter`**: Handles Google Gemini API integrations via REST.
- **Provider Registry**: A centralized registry maps `provider_type` to its corresponding adapter class.
- **Database Isolation**: Provider adapters never import or interact with SQLAlchemy sessions or database models; they operate purely on plain inputs and return structured Pydantic DTOs.
