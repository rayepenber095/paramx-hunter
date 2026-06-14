"""
ParamX Hunter - FastAPI Application Entry Point
"""

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, make_asgi_app

from backend.api.v1 import router as api_v1_router
from backend.database.session import engine
from backend.config import settings

logger = structlog.get_logger(__name__)

# ── Metrics ────────────────────────────────────────────────────────────────────

REQUEST_COUNT = Counter(
    "paramx_http_requests_total",
    "Total HTTP requests",
    ["method", "path", "status"]
)
REQUEST_LATENCY = Histogram(
    "paramx_http_request_duration_seconds",
    "HTTP request duration",
    ["method", "path"]
)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("paramx_hunter_starting", version=settings.VERSION)
    # NOTE: Schema management is handled exclusively by Alembic migrations
    # (`alembic upgrade head`), run as a separate step before starting the
    # app. Calling Base.metadata.create_all() here as well would create
    # tables/enum types directly from the ORM models, bypassing Alembic
    # and causing "type already exists" errors on the first `alembic
    # upgrade head` run.
    yield
    logger.info("paramx_hunter_shutting_down")
    await engine.dispose()


# ── App Factory ────────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title="ParamX Hunter API",
        description="Enterprise Web Parameter Discovery & Attack Surface Mapping",
        version=settings.VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ── Middleware ─────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(GZipMiddleware, minimum_size=1000)

    @app.middleware("http")
    async def request_metrics(request: Request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start
        REQUEST_COUNT.labels(
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        ).inc()
        REQUEST_LATENCY.labels(
            method=request.method,
            path=request.url.path,
        ).observe(duration)
        return response

    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        response = await call_next(request)
        logger.info(
            "http_request",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
        )
        return response

    # ── Exception Handlers ─────────────────────────────────────────────────────
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        return JSONResponse(
            status_code=404,
            content={"detail": "Not found", "path": request.url.path}
        )

    @app.exception_handler(500)
    async def server_error_handler(request: Request, exc):
        logger.error("unhandled_exception", error=str(exc))
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    # ── Routes ─────────────────────────────────────────────────────────────────
    app.include_router(api_v1_router, prefix="/api/v1")

    # Prometheus metrics endpoint
    metrics_app = make_asgi_app()
    app.mount("/metrics", metrics_app)

    @app.get("/health", tags=["system"])
    async def health_check():
        return {
            "status": "healthy",
            "version": settings.VERSION,
            "timestamp": time.time(),
        }

    return app


app = create_app()
