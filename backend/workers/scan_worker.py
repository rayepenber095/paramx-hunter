"""
ParamX Hunter - Celery Scan Workers
Handles async scan execution, pause/resume, progress tracking
"""

import asyncio
import uuid
from datetime import datetime

import redis.asyncio as aioredis
import structlog
from celery import Celery

from backend.config import settings
from backend.core.crawlers import AsyncCrawler, CrawlConfig, CrawlResult
from backend.core.extractors import ExtractionOrchestrator

logger = structlog.get_logger(__name__)

celery_app = Celery(
    "paramx_hunter",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)


# ── Scan State Keys ────────────────────────────────────────────────────────────

def scan_state_key(scan_id: str) -> str:
    return f"paramx:scan:{scan_id}:state"

def scan_queue_key(scan_id: str) -> str:
    return f"paramx:scan:{scan_id}:queue"

def scan_visited_key(scan_id: str) -> str:
    return f"paramx:scan:{scan_id}:visited"


# ── Scan Orchestration ─────────────────────────────────────────────────────────

async def launch_scan(scan_id: str) -> None:
    """Main scan orchestration coroutine."""
    from backend.database.session import AsyncSessionLocal
    from backend.database.models import Scan, Endpoint, Parameter, Request, ScanStatus

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select
        result = await db.execute(select(Scan).where(Scan.id == uuid.UUID(scan_id)))
        scan = result.scalar_one_or_none()
        if not scan:
            logger.error("scan_not_found", scan_id=scan_id)
            return

        # Update status
        scan.status = ScanStatus.RUNNING
        scan.started_at = datetime.utcnow()
        await db.commit()

        config = scan.config or {}
        crawl_config = CrawlConfig(
            target_url=scan.target.url if scan.target else config.get("target_url", ""),
            max_depth=config.get("max_depth", 5),
            max_requests=config.get("max_requests", 50_000),
            concurrency=config.get("concurrency", 50),
            request_delay_ms=config.get("request_delay_ms", 0),
            javascript_rendering=config.get("javascript_rendering", True),
            respect_robots_txt=config.get("respect_robots_txt", True),
            custom_headers=config.get("custom_headers", {}),
            cookies=config.get("cookies", {}),
        )

        # Track endpoints we've created
        endpoint_map: dict[str, uuid.UUID] = {}
        param_signatures: set[str] = set()
        total_params = 0

        async def process_result(result: CrawlResult):
            nonlocal total_params

            # Upsert endpoint
            normalized_url = result.url.split("?")[0].split("#")[0]
            if normalized_url not in endpoint_map:
                from backend.database.models import Endpoint, HttpMethod
                from urllib.parse import urlparse
                parsed = urlparse(result.url)
                ep = Endpoint(
                    scan_id=scan.id,
                    url=result.url,
                    normalized_url=normalized_url,
                    path=parsed.path,
                    domain=parsed.netloc,
                    method=HttpMethod.GET,
                    status_code=result.status_code,
                    content_type=result.content_type,
                    response_size=len(result.body) if result.body else 0,
                    response_time_ms=result.response_time_ms,
                    framework_detected=result.framework,
                )
                db.add(ep)
                await db.flush()
                endpoint_map[normalized_url] = ep.id

            ep_id = endpoint_map[normalized_url]

            # Extract parameters
            orchestrator = ExtractionOrchestrator(result.url, result.method)
            html = result.body.decode("utf-8", errors="replace") if result.body else ""

            orchestrator.process_request(
                url=result.url,
                headers=result.headers,
                cookies={},
                body=None,
                content_type=result.content_type,
            )

            if html:
                orchestrator.process_response_html(html)

            # Persist new parameters
            from backend.database.models import Parameter
            for p in orchestrator.results:
                sig = p.signature()
                if sig in param_signatures:
                    continue
                param_signatures.add(sig)
                param = Parameter(
                    scan_id=scan.id,
                    endpoint_id=ep_id,
                    name=p.name,
                    value=str(p.value)[:500] if p.value else None,
                    param_type=p.param_type,
                    source=p.source,
                    confidence_score=p.confidence_score,
                    is_sensitive=p.is_sensitive,
                    is_hidden=p.is_hidden,
                    data_type=p.data_type,
                    risk_tags=p.risk_tags,
                    tags=p.tags,
                    extra=p.extra,
                )
                db.add(param)
                total_params += 1

            await db.flush()

            # Update scan stats every 100 requests
            scan.total_requests += 1
            scan.total_parameters = total_params
            scan.queue_size = 0  # updated by crawler
            if scan.total_requests % 100 == 0:
                await db.commit()

        # Run crawler
        crawler = AsyncCrawler(crawl_config)
        try:
            async for result in crawler.crawl():
                await process_result(result)

            scan.status = ScanStatus.COMPLETED
            scan.completed_at = datetime.utcnow()
            scan.progress_percent = 100.0
            scan.total_endpoints = len(endpoint_map)
            scan.unique_parameters = len(param_signatures)
        except Exception as e:
            scan.status = ScanStatus.FAILED
            scan.error_message = str(e)
            logger.error("scan_failed", scan_id=scan_id, error=str(e))

        await db.commit()
        logger.info("scan_complete", scan_id=scan_id, total_params=total_params)


async def pause_scan(scan_id: str) -> None:
    """Signal crawler to pause via Redis."""
    r = aioredis.from_url(settings.REDIS_URL)
    await r.set(scan_state_key(scan_id), "paused", ex=86400)
    await r.close()


async def resume_scan(scan_id: str) -> None:
    """Resume a paused scan."""
    r = aioredis.from_url(settings.REDIS_URL)
    await r.delete(scan_state_key(scan_id))
    await r.close()
    await launch_scan(scan_id)


async def cancel_scan(scan_id: str) -> None:
    """Cancel a running scan."""
    r = aioredis.from_url(settings.REDIS_URL)
    await r.set(scan_state_key(scan_id), "cancelled", ex=86400)
    await r.close()


# ── Celery Tasks ───────────────────────────────────────────────────────────────

@celery_app.task(name="run_scan", bind=True, max_retries=3)
def run_scan_task(self, scan_id: str):
    """Celery task wrapper for scan execution."""
    try:
        asyncio.run(launch_scan(scan_id))
    except Exception as exc:
        logger.error("scan_task_failed", scan_id=scan_id, error=str(exc))
        raise self.retry(exc=exc, countdown=60)
