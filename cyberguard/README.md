# CyberGuard

CyberGuard is a modular AI-powered cybersecurity agent platform for mission-critical systems.

## Architecture

```mermaid
flowchart LR
  CLI[CLI] --> API[FastAPI API Gateway]
  Dashboard[React Dashboard] --> API
  Agent[LangGraph Agent] --> API
  API --> PG[(PostgreSQL)]
  API --> N4J[(Neo4j)]
  API --> REDIS[(Redis)]
  API --> ES[(Elasticsearch)]
  API --> KAFKA[(Kafka)]
```

## Quick start

```bash
docker compose up -d
```

## Modules

- `packages/domain-engine/` — Domain selector + standards mapper
- `integrations/cicd/github-actions/sbom-action/` — reusable SBOM CI action
- `infra/docker/docker-compose.yml` — local runtime stack

## Demo data

Sample SBOM/CVE fixtures are expected under `tests/fixtures/`.
