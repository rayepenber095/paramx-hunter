# ParamX Hunter

**Enterprise-grade web parameter discovery & attack-surface mapping platform.**

Crawls web applications, intercepts traffic, extracts and classifies 40+ parameter types (query params, JSON/XML/SOAP bodies, GraphQL, JWT claims, cookies, hidden fields, gRPC metadata, mobile API headers, and more), and builds a searchable inventory with risk scoring, visualizations, and exportable reports.

> ⚠️ **Authorized use only.** Only run this against systems you own or have explicit written permission to test. ParamX Hunter performs reconnaissance and parameter discovery — it does **not** send exploit payloads — but crawling itself can still generate significant traffic and is illegal/unethical against systems you don't have permission to scan.

---

## 1. Extract the archive

```bash
tar -xzf paramx-hunter.tar.gz
cd paramx-hunter
```

---

## 2. Quick Start (Docker — recommended)

This is the fastest path on Kali. Everything (Postgres, Redis, API, workers, frontend, nginx) runs in containers.

### Install Docker on Kali (if not already installed)

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin
sudo systemctl enable --now docker

# (Optional) run docker without sudo
sudo usermod -aG docker $USER
newgrp docker
```

### Configure environment

```bash
cp .env.example .env

# Generate a secure secret key and drop it into .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Edit .env -> SECRET_KEY=<paste the value above>
nano .env
```

### Build and start everything

```bash
docker compose up -d --build
```

First build takes a few minutes (it installs Playwright + Chromium for the browser engine). Watch progress with:

```bash
docker compose logs -f
```

### Initialize the database

```bash
# Run migrations
docker compose exec backend alembic upgrade head

# Create your admin login
docker compose exec backend python -m backend.scripts.seed \
  --email admin@local.test --password 'ChangeMe123!'
```

### Access ParamX Hunter

| Service            | URL                                                |
|--------------------|----------------------------------------------------|
| Web UI             | http://localhost                                    |
| Frontend (direct)  | http://localhost:3000                               |
| API docs (Swagger) | http://localhost/docs or http://localhost:8000/docs |
| Health check       | http://localhost:8000/health                        |
| Metrics            | http://localhost/metrics                            |

Log in with the email/password you set in the seed step above.

### Stopping / restarting

```bash
docker compose down          # stop everything
docker compose up -d         # start again (data persists in volumes)
docker compose down -v       # stop and WIPE all data (postgres + redis volumes)
```

---

## 3. Manual Setup (no Docker)

Useful if you want to run the crawler directly on Kali with full access to your network tools/wordlists.

### System dependencies

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip postgresql redis-server nodejs npm \
  build-essential libxml2-dev libxslt1-dev libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0
```

### Start Postgres & Redis

```bash
sudo systemctl enable --now postgresql redis-server

# Create the database + user
sudo -u postgres psql -c "CREATE USER paramx WITH PASSWORD 'paramx';"
sudo -u postgres psql -c "CREATE DATABASE paramx OWNER paramx;"
```

### Backend setup

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install -r backend/requirements.txt
playwright install --with-deps chromium

cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(32))"   # paste into .env as SECRET_KEY
nano .env
```

Run migrations and seed an admin user:

```bash
alembic upgrade head
python -m backend.scripts.seed --email admin@local.test --password 'ChangeMe123!'
```

### Run the backend (terminal 1)

```bash
source .venv/bin/activate
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

### Run a Celery worker (terminal 2)

```bash
source .venv/bin/activate
celery -A backend.workers.scan_worker.celery_app worker --loglevel=info --concurrency=4
```

### Run the frontend (terminal 3)

```bash
cd frontend
npm install --legacy-peer-deps
npm run dev
```

Frontend dev server runs at **http://localhost:3000** and proxies `/api` and `/ws` to the backend on port 8000.

---

## 4. Makefile shortcuts

If you set up the manual environment above, these wrappers save typing:

```bash
make install     # pip + npm install + playwright browsers
make dev-backend # uvicorn with reload
make dev-worker  # celery worker
make dev-frontend
make migrate     # alembic upgrade head
make seed        # create admin user
make test        # run backend test suite
make benchmark   # extraction engine + crawler throughput benchmarks
```

---

## 5. First Scan

1. Log in at http://localhost (or http://localhost:3000 for manual setup).
2. Go to **Scans → New Scan**.
3. Enter a target URL you're authorized to test, set crawl depth/concurrency, and launch.
4. Watch live progress on the **Dashboard** and **Scans** page.
5. Once running/complete, browse discovered parameters in **Parameter Explorer**, inspect the **Endpoint Inventory**, view relationship graphs in **Visualization**, and export a report from **Reports** (PDF, HTML, Excel, JSON).

---

## 6. Troubleshooting

- **`Cannot connect to the Docker daemon at unix:///run/user/1000/podman/podman.sock`** — Kali has shipped a `podman-docker` compatibility shim that intercepts the `docker` command. Either:
  - Quick fix: `systemctl --user enable --now podman.socket` (or `sudo systemctl enable --now podman.socket`), then retry.
  - Recommended fix (avoids podman-compose quirks with healthchecks/`depends_on`):
    ```bash
    sudo apt remove -y podman-docker
    curl -fsSL https://get.docker.com | sudo sh
    sudo systemctl enable --now docker
    sudo usermod -aG docker $USER
    newgrp docker
    docker version && docker compose version
    ```
- **`docker: permission denied`** — you ran `docker` without being in the `docker` group; either use `sudo` or run `newgrp docker` after `usermod -aG docker $USER` and re-login.
- **Port 80/3000/8000 already in use** — stop conflicting services (`sudo ss -ltnp | grep :80`) or change the port mappings in `docker-compose.yml`.
- **Playwright/Chromium fails to launch** — re-run `playwright install --with-deps chromium`; on Kali you may also need `sudo apt install -y libnss3 libatk-bridge2.0-0 libxkbcommon0 libxcomposite1 libxrandr2 libgbm1 libasound2`.
- **`pip install` refuses with "externally managed environment"** — Kali's system Python is locked down; use the venv shown above (recommended), or add `--break-system-packages` to the pip command.
- **Database connection errors** — confirm `DATABASE_URL` in `.env` matches your Postgres user/password/db, and that Postgres / `docker compose` is running.

---

## 7. Project Structure

See `docs/ARCHITECTURE.md` for the full architecture breakdown and `docs/DEPLOYMENT.md` for Kubernetes/production deployment.

```
backend/    FastAPI app, crawler, extraction engine, Celery workers, reporting
frontend/   React + TypeScript dashboard (Vite, Tailwind, ReactFlow, Recharts)
docker/     Dockerfiles + nginx configs
k8s/        Kubernetes manifests (Postgres, Redis, backend, workers, ingress)
docs/       Architecture & deployment guides
```
