"""
ParamX Hunter - Performance Benchmarks
Measures crawler throughput and extraction engine performance.

Usage:
    python -m backend.tests.benchmarks.run_benchmarks
    python -m backend.tests.benchmarks.run_benchmarks --target https://example.com
"""

import argparse
import asyncio
import json
import time
from statistics import mean, median

from backend.core.crawlers import AsyncCrawler, CrawlConfig
from backend.core.extractors import ExtractionOrchestrator

# ── Extraction Engine Benchmark ────────────────────────────────────────────────

SAMPLE_URL = "https://example.com/api/v1/search?q=test&page=2&limit=50&sort=created_at&ref=homepage"
SAMPLE_HEADERS = {
    "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjMiLCJyb2xlIjoiYWRtaW4ifQ.sig",
    "User-Agent": "Mozilla/5.0",
    "X-Api-Key": "sk-live-abc123def456",
    "X-Request-Id": "req-abc-123",
}
SAMPLE_COOKIES = {
    "sessionid": "sess_abc123xyz",
    "theme": "dark",
    "csrftoken": "tok_xyz",
}
SAMPLE_BODY = json.dumps(
    {
        "username": "admin",
        "password": "supersecret",
        "profile": {
            "name": "Test User",
            "settings": {
                "locale": "en-US",
                "debug": True,
                "feature_flags": ["new_ui", "beta_api"],
            },
        },
        "items": [{"id": 1, "qty": 2}, {"id": 2, "qty": 1}],
    }
)
SAMPLE_HTML = """
<form action="/login" method="POST">
  <input type="hidden" name="_csrf" value="tok_abc123">
  <input type="hidden" name="return_url" value="/dashboard">
  <input type="text" name="username">
  <input type="password" name="password">
</form>
"""


def benchmark_extraction(iterations: int = 10_000) -> dict:
    """Benchmark the parameter extraction engine throughput."""
    durations = []

    for _ in range(iterations):
        start = time.perf_counter()

        orchestrator = ExtractionOrchestrator(SAMPLE_URL, "POST")
        orchestrator.process_request(
            url=SAMPLE_URL,
            headers=SAMPLE_HEADERS,
            cookies=SAMPLE_COOKIES,
            body=SAMPLE_BODY,
            content_type="application/json",
        )
        orchestrator.process_response_html(SAMPLE_HTML)

        durations.append(time.perf_counter() - start)

    total_time = sum(durations)
    return {
        "iterations": iterations,
        "total_seconds": round(total_time, 3),
        "mean_ms": round(mean(durations) * 1000, 4),
        "median_ms": round(median(durations) * 1000, 4),
        "p99_ms": round(sorted(durations)[int(iterations * 0.99)] * 1000, 4),
        "extractions_per_second": round(iterations / total_time, 1),
        "extrapolated_requests_per_hour": round((iterations / total_time) * 3600, 0),
    }


# ── Crawler Throughput Benchmark ───────────────────────────────────────────────


async def benchmark_crawler(target_url: str, duration_seconds: int = 30) -> dict:
    """
    Run a real crawl against a target for `duration_seconds` and report
    the achieved requests-per-second / requests-per-hour rate.

    NOTE: Only run against targets you are authorized to test.
    """
    config = CrawlConfig(
        target_url=target_url,
        max_depth=10,
        max_requests=100_000,
        concurrency=50,
        request_delay_ms=0,
        javascript_rendering=False,
        respect_robots_txt=True,
    )

    crawler = AsyncCrawler(config)

    start = time.monotonic()
    count = 0

    async def stop_after_duration():
        await asyncio.sleep(duration_seconds)
        crawler._running = False

    stopper = asyncio.create_task(stop_after_duration())

    async for _ in crawler.crawl():
        count += 1
        if time.monotonic() - start > duration_seconds:
            break

    stopper.cancel()
    elapsed = time.monotonic() - start

    return {
        "target": target_url,
        "duration_seconds": round(elapsed, 1),
        "total_requests": count,
        "requests_per_second": round(count / elapsed, 1) if elapsed > 0 else 0,
        "extrapolated_requests_per_hour": (
            round((count / elapsed) * 3600, 0) if elapsed > 0 else 0
        ),
        "target_met": (count / elapsed) * 3600 >= 100_000 if elapsed > 0 else False,
        "crawler_stats": crawler.get_stats(),
    }


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ParamX Hunter performance benchmarks")
    parser.add_argument(
        "--target", help="Target URL for crawl benchmark (authorized only)"
    )
    parser.add_argument(
        "--duration", type=int, default=30, help="Crawl benchmark duration (seconds)"
    )
    parser.add_argument(
        "--iterations", type=int, default=10_000, help="Extraction benchmark iterations"
    )
    args = parser.parse_args()

    print("=" * 60)
    print("ParamX Hunter — Extraction Engine Benchmark")
    print("=" * 60)
    extraction_results = benchmark_extraction(args.iterations)
    for k, v in extraction_results.items():
        print(f"  {k:35s}: {v}")

    target_met = extraction_results["extrapolated_requests_per_hour"] >= 100_000
    print(f"\n  Target (100k req/hr): {'✅ MET' if target_met else '❌ NOT MET'}")

    if args.target:
        print("\n" + "=" * 60)
        print(f"ParamX Hunter — Live Crawler Benchmark ({args.target})")
        print("=" * 60)
        crawl_results = asyncio.run(benchmark_crawler(args.target, args.duration))
        for k, v in crawl_results.items():
            if k != "crawler_stats":
                print(f"  {k:35s}: {v}")
        print(
            f"\n  Target (100k req/hr): {'✅ MET' if crawl_results['target_met'] else '❌ NOT MET (network/server bound)'}"
        )


if __name__ == "__main__":
    main()
