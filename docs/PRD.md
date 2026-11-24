# Product Requirements Document (PRD) — Kestrel AI Control Center

## 1. Vision
A centralized observability and operations platform for LLM-powered applications that gives engineering teams complete transparency into token consumption, inference cost, latency distributions, error frequencies, and upstream provider health.

## 2. Target Users
- **Admin**: Configures upstream provider connections, workspace API keys, alert rules, and pricing tables; inspects audit logs and full system telemetry.
- **Viewer**: Read-only user monitoring usage trends, cost aggregations, latency percentiles, error rates, and alert statuses.
- **Developer / Application**: Instruments LLM calls in external client applications via workspace API keys without requiring provider credentials.

## 3. Functional Requirements

### Authentication, Tenancy & Security
- **FR-01**: User registration and login using email and password with `argon2` password hashing; authenticated sessions managed via JWT.
- **FR-02**: Role-based access control with `admin` and `viewer` roles, strictly enforced server-side on all endpoints.
- **FR-03**: Multi-tenancy model with one workspace per account; `workspace_id` enforced on all tenant data tables and queries.
- **FR-04**: Workspace API keys: generation, display-once policy, revocation, and secure storage (hashed with SHA-256).

### Ingestion & Client Telemetry
- **FR-05**: Ingestion endpoint `POST /ingest/events` accepting provider, model, application identifier, input/output token counts, latency (ms), status, error type, client timestamp, token source (`measured` | `estimated`), and idempotency key.
- **FR-06**: Thin Python client wrapper library to instrument LLM calls (first deployed on the author's RAG application).

### Provider Health & Integration
- **FR-07**: Provider connection management (add, edit, delete); credentials encrypted at rest with Fernet and never returned by the API after saving.
- **FR-08**: Provider connection testing, dynamic model listing, and scheduled health checks storing status and latency history.

### Analytics & Cost Intelligence
- **FR-09**: Usage analytics broken down by time range, provider, model, and application; measured and estimated token counts displayed separately.
- **FR-10**: Editable pricing table with provider, model, cost per 1k input/output tokens, source URL, and effective date; price is snapshotted onto each ingested event.
- **FR-11**: Cost analysis views: daily/monthly aggregations, breakdowns by provider and model, and most expensive applications and requests.
- **FR-12 (Should)**: Spend-spike anomaly detection calculated against a rolling baseline.
- **FR-13**: Performance metrics: average latency, percentiles (`p50`, `p95`, `p99`), error rate, and requests per minute (RPM) per provider and model.

### Alerts, Incidents & Operations
- **FR-14**: Alert rules engine supporting provider-down, error-rate, latency-threshold, and spend-threshold triggers; full lifecycle (`firing`, `resolved`), deduplication, history log, and in-app notification bell.
- **FR-15**: Comprehensive audit log recording authentication events, API key actions, provider updates, alert rule modifications, and pricing changes.
- **FR-16**: Main dashboard view featuring primary KPI stat cards, time-series charts, date range selector (`24h`, `7d`, `30d`), recent requests table, and active alerts feed.
- **FR-17**: Explicit loading, empty, and error boundary states implemented on every page and visualization.
- **FR-18**: Operational endpoints: `/health` readiness/liveness checks, Prometheus `/metrics` endpoint, and structured JSON logs with correlation request IDs.
- **FR-19 (Should)**: Background data retention job deleting raw event records after scheduled aggregation rollups.

## 4. Non-Functional Requirements
- **Secret Hygiene**: Zero secrets, API keys, or raw provider tokens stored in repository, application logs, or client-facing responses.
- **Tenant Isolation**: Mandatory repository-level tenant scoping verified through automated isolation test suites.
- **Privacy & Compliance**: Metadata-only telemetry; prompt text and raw completion responses are strictly never collected or stored.
- **Realistic Performance Expectations**: Telemetry ingest targets (e.g., sub-50ms ingestion latency) are performance goals to be measured under load tests, never assumed claims.
- **Fault Isolation**: Outbound provider downtime or background worker crashes must never disrupt telemetry ingestion or API availability.
- **Production-Grade Testing**: Test suite executes against real PostgreSQL instances (no SQLite mocks for integration tests).
- **Automated CI**: GitHub Actions runs linting, formatting, type checking, and test suites on every pull request.
- **Zero-Friction Startup**: Fresh repository clone initializes all services with a single Docker Compose command.
- **Accessibility & UX**: Conforms to WCAG AA standards with full keyboard navigability across all views.

## 5. Deferred Scope (Post-MVP)
- Team invitation workflows and multi-user workspace memberships.
- Direct Anthropic and OpenAI adapter implementations (Groq, Gemini, and Ollama prioritized for MVP).
- External notification channels (Slack, Discord, Email webhooks).
- Reverse-proxy / gateway routing mode for LLM calls.
- Full prompt/response payload logging and evaluation.
- Terraform or cloud infrastructure-as-code automation.
- Redis cache layer.

## 6. MVP Definition of Done
The MVP is complete when:
1. Live telemetry from the author's RAG application flows via the Python wrapper and renders on the dashboard.
2. Every supported alert type (provider down, error rate, latency, spend) triggers and resolves during a live demo.
3. Automated tenant isolation test suite passes with 100% compliance.
4. Clean checkout starts successfully with a single `docker compose up` command.
5. GitHub Actions CI pipeline is fully green across all checks.
