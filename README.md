# ParamX Hunter

**Enterprise-Grade Web Parameter Discovery & Attack Surface Mapping Platform**

---

## Overview

ParamX Hunter is a professional security research tool for crawling web applications, intercepting HTTP traffic, and building a comprehensive API and application attack-surface inventory. It extracts and classifies 40+ parameter types across REST, GraphQL, WebSocket, SOAP, and mobile APIs.

> ⚠️ **Disclaimer:** This tool is intended for authorized security assessments only. Never run against targets without explicit written permission.

---

## Architecture

```
paramx-hunter/
├── backend/                # Python 3.13 FastAPI application
│   ├── api/                # REST API routes
│   ├── core/               # Crawlers, analyzers, extractors
│   ├── database/           # SQLAlchemy models & migrations
│   ├── workers/            # Celery async workers
│   ├── auth/               # JWT + RBAC
│   └── reporting/          # PDF/HTML/JSON report generation
├── frontend/               # React + TypeScript + Tailwind
│   └── src/
│       ├── components/     # Dashboard, Explorer, Visualization
│       ├── pages/          # Route pages
│       └── stores/         # Zustand state management
├── docker/                 # Docker configs
└── k8s/                    # Kubernetes manifests
```

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/your-org/paramx-hunter
cd paramx-hunter

# Start all services
docker-compose up -d

# Access dashboard
open http://localhost:3000

# API docs
open http://localhost:8000/docs
```

---

## Tech Stack

| Layer       | Technology                                      |
|-------------|--------------------------------------------------|
| Backend     | Python 3.13, FastAPI, SQLAlchemy, Pydantic v2   |
| Database    | PostgreSQL 16, Redis 7                           |
| Workers     | Celery 5, Redis Broker                           |
| Crawler     | aiohttp, Playwright                              |
| Frontend    | React 18, TypeScript, Tailwind, ShadCN          |
| Viz         | D3.js, React Flow, Recharts                      |
| Auth        | JWT, RBAC (Admin/Manager/Analyst/Viewer)         |
| Deploy      | Docker Compose, Kubernetes                       |

---

## Parameter Types Detected (40+)

URL Query, Path, Fragment, Form URL Encoded, Multipart Form,
JSON Body, Nested JSON, XML, SOAP, GraphQL Variables,
GraphQL Query, Standard Headers, Auth Headers, Custom Headers,
Cookies, Session, JWT Claims, Hidden Form Fields, CSRF Tokens,
Anti-Forgery Tokens, Method Override, Pagination, Sorting,
Search, Filter, Redirect, Return URL, Locale, Language,
Version, Feature Flags, Debug, File Path, API Keys,
WebSocket Messages, SSE, Mobile API, REST, gRPC, OpenAPI

---

## Performance Targets

- 100,000+ requests/hour
- Async parallel crawling
- Redis caching layer
- Incremental scan resume
- Memory-optimized parameter deduplication
