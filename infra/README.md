# Infrastructure — Kestrel AI Control Center

## Purpose
Container orchestration, reverse proxy, monitoring, and continuous integration definitions for local development and production deployments.

## Planned Layout & Components
- **Docker Compose**: Orchestration of API service, background worker, PostgreSQL database, Prometheus, Grafana, and Nginx.
- **Nginx**: Reverse proxy routing external traffic to frontend assets and FastAPI backend endpoints, handling SSL termination.
- **Prometheus**: Metrics collection scraping `/metrics` endpoints from both API and worker processes.
- **Grafana**: Operational dashboards for infrastructure metrics, process health, and error rates.
- **GitHub Actions**: Automated CI pipelines executing linting, type checks, unit tests, and integration tests against real PostgreSQL instances on every pull request.
