# ParamX Hunter — Architecture

## Overview

ParamX Hunter is split into five cooperating layers:

1. **Crawler & Browser Engine** (`backend/core/crawlers`) — async HTTP crawling via `aiohttp`, optional JS rendering via Playwright for SPA frameworks (React, Angular, Vue, Next.js, Nuxt, Svelte).
2. **Extraction Engine** (`backend/core/extractors`) — modular `BaseExtractor` subclasses, one per parameter category, orchestrated by `ExtractionOrchestrator` with deduplication and risk classification.
3. **Analyzers** (`backend/core/analyzers`) — API discovery (OpenAPI/Swagger/GraphQL introspection), WebSocket/SSE schema inference.
4. **Persistence & API** (`backend/database`, `backend/api`) — async SQLAlchemy models, FastAPI REST endpoints, JWT + RBAC.
5. **Workers** (`backend/workers`) — Celery-based scan orchestration, pause/resume via Redis state, progress published over WebSocket pub/sub.

```
┌─────────────┐     ┌──────────────┐     ┌────────────────────┐
│   Frontend  │────▶│   FastAPI    │────▶│   PostgreSQL        │
│  (React/TS) │◀────│   (REST+WS)  │◀────│  (parameters, etc.) │
└─────────────┘     └──────┬───────┘     └────────────────────┘
                            │
                     ┌──────▼───────┐     ┌────────────────────┐
                     │ Celery Worker│────▶│      Redis          │
                     │ (AsyncCrawler│◀────│ (queue, pub/sub,    │
                     │ + Extractors)│     │  rate limit, cache) │
                     └──────┬───────┘     └────────────────────┘
                            │
                     ┌──────▼───────┐
                     │ Target Web   │
                     │ Application  │
                     └──────────────┘
```

## Data Flow

1. User creates a **Project → Target → Scan** via the API/UI.
2. `launch_scan()` instantiates `AsyncCrawler` with the scan's `CrawlConfig`.
3. For each crawled response, `ExtractionOrchestrator` runs all relevant extractors (URL, headers, cookies, JSON/XML/SOAP body, GraphQL, JWT, hidden fields, gRPC, mobile).
4. Extracted parameters are deduplicated by signature (`md5(endpoint:name:type:source)`), classified for risk (`RiskLevel`), and persisted.
5. Progress and newly discovered parameters are published to `paramx:scan:{id}:events` (Redis pub/sub) and streamed to the frontend over `/api/v1/ws/scan/{id}`.
6. On completion, reports can be generated (PDF/HTML/Excel/JSON) via `backend/reporting`.

## Parameter Classification

Every extracted parameter passes through `classify_parameter()`:

- **Pattern-based typing**: redirect/return-URL params, pagination, sorting, search, debug flags, version, feature flags, API keys.
- **Sensitivity detection**: regex over common secret-bearing names (password, token, api_key, ssn, etc.).
- **Risk tagging**: e.g. `open-redirect-candidate`, `api-key-exposure`, `debug-exposure`, `sensitive-data`.

## Scaling to 100k+ requests/hour

- `AsyncCrawler` uses a bounded `asyncio.Queue` + worker pool (configurable concurrency, default 50, max 200).
- Per-domain token-bucket rate limiting (`DomainRateLimiter`) avoids hammering any single host while maximizing aggregate throughput across domains.
- Redis-backed `URLDeduplicator` allows multiple Celery workers to share crawl state for a single scan.
- PostgreSQL indexes: composite indexes on `(scan_id, param_type)`, `(scan_id, risk_level)`, plus `pg_trgm` GIN indexes for fast `ILIKE` search across millions of rows.
- Celery worker HPA scales 4→20 pods based on CPU; backend API scales 3→12 pods.

## Security Model

- **RBAC**: Admin / Manager / Analyst / Viewer, enforced via `require_roles()` FastAPI dependency.
- **JWT**: short-lived access tokens (60 min) + refresh tokens (30 days).
- **Encryption at rest**: target `auth_config` secrets encrypted with Fernet (derived from `SECRET_KEY`); production should use a KMS-backed key.
- **Audit log**: every security-relevant action (auth, scan lifecycle, exports, RBAC changes) recorded in `audit_logs` with IP/User-Agent.
- **No active exploitation**: the tool only crawls, intercepts, and classifies — it never sends attack payloads.

## Extending the Extraction Engine

To add a new parameter type:

1. Subclass `BaseExtractor` in `backend/core/extractors/__init__.py`.
2. Implement `extract(self, data) -> Generator[ExtractedParameter, None, None]`.
3. Register it in `ExtractionOrchestrator.process_request()` (or a new `process_*` method for non-HTTP sources).
4. Add classification rules to `classify_parameter()` if the new type needs custom risk tagging.
5. Add unit tests in `backend/tests/unit/test_extractors.py`.
