"""
ParamX Hunter - Rate Limiting & Caching Utilities
Redis-backed token bucket rate limiter for crawl politeness,
plus generic response caching helpers.
"""

import asyncio
import hashlib
import json
import time
from functools import wraps
from typing import Any, Callable

import redis.asyncio as aioredis

from backend.config import settings

_redis_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    global _redis_pool
    if _redis_pool is None:
        _redis_pool = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            max_connections=50,
        )
    return _redis_pool


# ── Per-Domain Rate Limiter ─────────────────────────────────────────────────────

class DomainRateLimiter:
    """
    Token-bucket rate limiter scoped per target domain.
    Ensures the crawler doesn't overwhelm any single host while still
    achieving high aggregate throughput (100k+ req/hr across domains).
    """

    def __init__(self, requests_per_second: float = 10.0, burst: int = 20):
        self.rate = requests_per_second
        self.burst = burst
        self._buckets: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, domain: str) -> None:
        """Block until a token is available for this domain."""
        async with self._lock:
            bucket = self._buckets.setdefault(domain, {
                "tokens": float(self.burst),
                "last_refill": time.monotonic(),
            })

            now = time.monotonic()
            elapsed = now - bucket["last_refill"]
            bucket["tokens"] = min(self.burst, bucket["tokens"] + elapsed * self.rate)
            bucket["last_refill"] = now

            if bucket["tokens"] < 1:
                wait_time = (1 - bucket["tokens"]) / self.rate
            else:
                wait_time = 0
                bucket["tokens"] -= 1

        if wait_time > 0:
            await asyncio.sleep(wait_time)
            async with self._lock:
                self._buckets[domain]["tokens"] = max(
                    0, self._buckets[domain]["tokens"] - 1
                )

    def configure_domain(self, domain: str, requests_per_second: float) -> None:
        """Override the global rate for a specific domain (e.g., from robots.txt crawl-delay)."""
        self._buckets[domain] = {
            "tokens": float(self.burst),
            "last_refill": time.monotonic(),
            "rate_override": requests_per_second,
        }


# ── Distributed Rate Limiter (Redis-backed, for multi-worker scans) ───────────

class RedisRateLimiter:
    """
    Sliding-window rate limiter using Redis, for coordinating rate limits
    across multiple Celery workers scanning the same target.
    """

    def __init__(self, key_prefix: str = "paramx:ratelimit"):
        self.key_prefix = key_prefix

    async def is_allowed(self, identifier: str, max_requests: int, window_seconds: int) -> bool:
        r = get_redis()
        key = f"{self.key_prefix}:{identifier}"
        now = time.time()
        window_start = now - window_seconds

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zcard(key)
        pipe.zadd(key, {str(now): now})
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

        current_count = results[1]
        return current_count < max_requests

    async def wait_if_needed(self, identifier: str, max_requests: int, window_seconds: int) -> None:
        while not await self.is_allowed(identifier, max_requests, window_seconds):
            await asyncio.sleep(0.5)


# ── Response Caching ───────────────────────────────────────────────────────────

def cache_key(*parts: Any) -> str:
    raw = json.dumps(parts, sort_keys=True, default=str)
    digest = hashlib.md5(raw.encode()).hexdigest()
    return f"paramx:cache:{digest}"


async def cached_get(key: str) -> Any | None:
    r = get_redis()
    val = await r.get(key)
    if val is None:
        return None
    try:
        return json.loads(val)
    except json.JSONDecodeError:
        return val


async def cached_set(key: str, value: Any, ttl: int | None = None) -> None:
    r = get_redis()
    ttl = ttl or settings.REDIS_CACHE_TTL
    serialized = json.dumps(value, default=str)
    await r.set(key, serialized, ex=ttl)


def cached(ttl: int | None = None):
    """Decorator for caching async function results in Redis."""
    def decorator(fn: Callable):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            key = cache_key(fn.__name__, args, kwargs)
            cached_val = await cached_get(key)
            if cached_val is not None:
                return cached_val
            result = await fn(*args, **kwargs)
            await cached_set(key, result, ttl)
            return result
        return wrapper
    return decorator


# ── Crawl Deduplication (Bloom-filter-like via Redis Set) ──────────────────────

class URLDeduplicator:
    """
    Redis-backed URL fingerprint store for cross-worker deduplication
    during distributed crawls.
    """

    def __init__(self, scan_id: str):
        self.key = f"paramx:scan:{scan_id}:seen_urls"

    async def is_seen(self, fingerprint: str) -> bool:
        r = get_redis()
        return await r.sismember(self.key, fingerprint)

    async def mark_seen(self, fingerprint: str) -> None:
        r = get_redis()
        await r.sadd(self.key, fingerprint)
        await r.expire(self.key, 86400 * 7)  # 7-day TTL

    async def count(self) -> int:
        r = get_redis()
        return await r.scard(self.key)
