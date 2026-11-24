# Frontend — Kestrel AI Control Center

## Purpose
Web-based user interface for Kestrel AI Control Center, presenting real-time telemetry, cost intelligence, provider status, alert feeds, and management settings for LLM operations.

## Planned Layout & Stack
- **Framework & Build**: React 18+, TypeScript, Vite.
- **Styling & Components**: Tailwind CSS, shadcn/ui accessible component primitives.
- **State & Data Fetching**: TanStack Query (React Query) for server state caching and optimistic updates.
- **Data Visualization**: Apache ECharts for interactive usage, cost, token, and latency time-series charts.
- **Visual Direction**: Modern, high-density dashboard inspired by the layout, spacing, and color feel of the Minia admin design language (no third-party code or assets copied).
- **Views**:
  - Overview / KPI stat cards (requests, tokens, spend, error rate)
  - Usage analytics (time, provider, model, application)
  - Cost analytics & pricing tables
  - Performance analytics (avg, p50, p95, p99 latency)
  - Provider health & status monitors
  - Alerts & incident management feed
  - Workspace, API keys, and audit logs
