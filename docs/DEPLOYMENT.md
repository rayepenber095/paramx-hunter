# ParamX Hunter — Deployment Guide

## Local Development (Docker Compose)

```bash
cp .env.example .env
# Edit .env and set SECRET_KEY:
python -c "import secrets; print(secrets.token_urlsafe(32))"

docker-compose up -d --build

# Run migrations
docker-compose exec backend alembic upgrade head

# Seed an admin user
docker-compose exec backend python -m backend.scripts.seed \
  --email admin@yourcompany.com --password 'ChangeMe123!'
```

Access:
- Frontend: http://localhost (via nginx) or http://localhost:3000 (direct)
- API docs: http://localhost/docs
- Metrics: http://localhost/metrics

## Manual Development Setup

```bash
# Backend
python -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
playwright install --with-deps chromium

# Start Postgres + Redis (or use docker-compose for just these)
docker-compose up -d postgres redis

# Run migrations & seed
alembic upgrade head
python -m backend.scripts.seed

# Run API
uvicorn backend.main:app --reload

# Run Celery worker (separate terminal)
celery -A backend.workers.scan_worker.celery_app worker --loglevel=info

# Frontend (separate terminal)
cd frontend
npm install --legacy-peer-deps
npm run dev
```

## Production — Kubernetes

### Prerequisites
- Kubernetes 1.27+
- nginx-ingress controller
- cert-manager (for TLS via Let's Encrypt)
- Container registry access (GHCR images built by CI)

### Steps

```bash
# 1. Update secrets with production values
#    Edit k8s/00-namespace-config.yaml:
#    - SECRET_KEY (256-bit random)
#    - POSTGRES_PASSWORD
#    - CORS_ORIGINS in ConfigMap

# 2. Apply manifests in order
kubectl apply -f k8s/00-namespace-config.yaml
kubectl apply -f k8s/01-postgres.yaml
kubectl apply -f k8s/02-redis.yaml
kubectl apply -f k8s/03-backend.yaml
kubectl apply -f k8s/04-celery.yaml
kubectl apply -f k8s/05-frontend-ingress.yaml

# 3. Run migrations (one-off job)
kubectl run paramx-migrate --rm -it --restart=Never \
  --image=ghcr.io/your-org/paramx-hunter/backend:latest \
  --namespace=paramx-hunter \
  -- alembic upgrade head

# 4. Seed admin user
kubectl run paramx-seed --rm -it --restart=Never \
  --image=ghcr.io/your-org/paramx-hunter/backend:latest \
  --namespace=paramx-hunter \
  -- python -m backend.scripts.seed --email admin@yourcompany.com --password 'SecureP@ss!'

# 5. Verify rollout
kubectl get pods -n paramx-hunter
kubectl logs -f deployment/paramx-backend -n paramx-hunter
```

### Update DNS

Point `paramxhunter.example.com` (set in `k8s/05-frontend-ingress.yaml`) at your ingress controller's external IP/load balancer.

### Scaling

- Backend API: HPA scales 3→12 pods on CPU 70% / memory 80%.
- Celery workers: HPA scales 4→20 pods on CPU 75%.
- For very large scans (500k+ requests), increase `MAX_REQUESTS_PER_SCAN` and `concurrency` in scan config, and consider a dedicated worker node pool.

## CI/CD

GitHub Actions (`.github/workflows/ci-cd.yml`) runs on every push to `main`/`develop`:

1. Backend lint (ruff, black, mypy) + unit/integration tests with coverage.
2. Frontend type-check, lint, build.
3. Trivy filesystem scan + `pip-audit`.
4. On `main`: build & push Docker images to GHCR, then roll out to Kubernetes via `kubectl set image`.

Required repository secrets:
- `KUBE_CONFIG` — base64-encoded kubeconfig for the target cluster.

## Backup & Disaster Recovery

- **PostgreSQL**: schedule `pg_dump` via CronJob or use managed Postgres (RDS/Cloud SQL) with automated snapshots. The `parameters` table can grow large — consider partitioning by `scan_id` or `first_seen` for very large deployments.
- **Redis**: AOF persistence enabled (`--appendonly yes`); used for scan state, rate limiting, and pub/sub — not a primary data store, safe to lose on restart (active scans would need to be re-launched).
- **Reports**: `REPORTS_DIR` (`/tmp/paramx_reports`) is ephemeral by default; mount a persistent volume or upload generated reports to object storage (S3/GCS) for retention.
