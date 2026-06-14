"""
ParamX Hunter - High-Speed Async Crawler
Supports: aiohttp, Playwright SPA rendering, sitemap, robots.txt
Target: 100,000+ requests/hour
"""

import asyncio
import hashlib
import re
import time
import urllib.parse
import urllib.robotparser
from collections import defaultdict
from dataclasses import dataclass, field
from typing import AsyncGenerator, Callable
from urllib.parse import urljoin, urlparse

import aiohttp
import structlog
from bs4 import BeautifulSoup
from playwright.async_api import Browser, BrowserContext, Page, async_playwright

logger = structlog.get_logger(__name__)


# ── Config ─────────────────────────────────────────────────────────────────────

@dataclass
class CrawlConfig:
    target_url: str
    max_depth: int = 5
    max_requests: int = 50_000
    concurrency: int = 50
    request_delay_ms: int = 0  # 0 = no delay
    timeout_seconds: int = 30
    follow_redirects: bool = True
    respect_robots_txt: bool = True
    crawl_subdomains: bool = False
    javascript_rendering: bool = True
    user_agent: str = "ParamXHunter/1.0 (+https://paramxhunter.io/bot)"
    custom_headers: dict = field(default_factory=dict)
    cookies: dict = field(default_factory=dict)
    scope_regex: list[str] = field(default_factory=list)
    excluded_extensions: set[str] = field(default_factory=lambda: {
        ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff",
        ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".pdf", ".zip"
    })


@dataclass
class CrawlResult:
    url: str
    method: str
    status_code: int | None
    headers: dict
    response_headers: dict
    body: bytes | None
    content_type: str
    response_time_ms: int
    depth: int
    referrer: str | None
    links_found: list[str] = field(default_factory=list)
    forms_found: list[dict] = field(default_factory=list)
    websocket_urls: list[str] = field(default_factory=list)
    js_endpoints: list[str] = field(default_factory=list)
    framework: str | None = None
    error: str | None = None


# ── URL Normalizer ─────────────────────────────────────────────────────────────

class URLNormalizer:
    def __init__(self, base_url: str):
        self.base = urlparse(base_url)
        self.base_domain = self.base.netloc

    def normalize(self, url: str, referrer: str | None = None) -> str | None:
        try:
            if url.startswith(("javascript:", "mailto:", "tel:", "#")):
                return None
            if referrer:
                url = urljoin(referrer, url)
            else:
                url = urljoin(f"{self.base.scheme}://{self.base.netloc}", url)
            parsed = urlparse(url)
            # Remove fragments
            normalized = parsed._replace(fragment="").geturl()
            return normalized
        except Exception:
            return None

    def is_in_scope(self, url: str, allow_subdomains: bool = False) -> bool:
        try:
            parsed = urlparse(url)
            if allow_subdomains:
                return parsed.netloc.endswith(self.base_domain)
            return parsed.netloc == self.base_domain
        except Exception:
            return False


# ── Link Extractor ─────────────────────────────────────────────────────────────

class LinkExtractor:
    JS_URL_PATTERN = re.compile(
        r'(?:fetch|axios\.get|axios\.post|\.get|\.post|\.put|\.delete|\.patch)'
        r'\s*\(\s*["\']([^"\']+)["\']',
        re.IGNORECASE,
    )
    WS_PATTERN = re.compile(r'new WebSocket\s*\(\s*["\']([^"\']+)["\']', re.IGNORECASE)
    SRC_HREF_PATTERN = re.compile(r'(?:href|src|action)\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)

    @classmethod
    def extract_from_html(
        cls,
        html: str,
        base_url: str,
        normalizer: URLNormalizer,
    ) -> tuple[list[str], list[dict], list[str], list[str]]:
        """Returns (links, forms, websocket_urls, js_endpoints)."""
        soup = BeautifulSoup(html, "lxml")
        links = []
        websocket_urls = []
        js_endpoints = []

        # <a href>
        for tag in soup.find_all("a", href=True):
            url = normalizer.normalize(tag["href"], base_url)
            if url and normalizer.is_in_scope(url):
                links.append(url)

        # <link>, <script src>, <img src>
        for tag in soup.find_all(["link", "script", "img", "iframe", "frame"]):
            src = tag.get("href") or tag.get("src")
            if src:
                url = normalizer.normalize(src, base_url)
                if url and normalizer.is_in_scope(url):
                    links.append(url)

        # Forms
        forms = []
        for form in soup.find_all("form"):
            action = form.get("action", "")
            method = form.get("method", "GET").upper()
            action_url = normalizer.normalize(action, base_url) if action else base_url
            inputs = []
            for inp in form.find_all(["input", "select", "textarea"]):
                inputs.append({
                    "name": inp.get("name", ""),
                    "type": inp.get("type", "text"),
                    "value": inp.get("value", ""),
                    "required": inp.has_attr("required"),
                })
            forms.append({
                "action": action_url,
                "method": method,
                "inputs": inputs,
            })
            if action_url:
                links.append(action_url)

        # JavaScript analysis
        for script in soup.find_all("script"):
            code = script.get_text()
            # API endpoints in JS
            for match in cls.JS_URL_PATTERN.finditer(code):
                url = normalizer.normalize(match.group(1), base_url)
                if url:
                    js_endpoints.append(url)
            # WebSocket connections
            for match in cls.WS_PATTERN.finditer(code):
                websocket_urls.append(match.group(1))

        return list(set(links)), forms, list(set(websocket_urls)), list(set(js_endpoints))

    @classmethod
    def detect_framework(cls, html: str, headers: dict) -> str | None:
        if "x-powered-by" in headers:
            pw = headers["x-powered-by"].lower()
            if "next" in pw:
                return "Next.js"
            if "express" in pw:
                return "Express.js"

        if "__next" in html or "_next/" in html:
            return "Next.js"
        if "ng-version" in html or "ng-app" in html:
            return "Angular"
        if "__vue" in html or "vue.min.js" in html:
            return "Vue.js"
        if "react" in html.lower() and ("__react" in html or "data-reactroot" in html):
            return "React"
        if "wp-content" in html or "wp-includes" in html:
            return "WordPress"
        if "laravel" in html.lower() or "csrf-token" in html:
            return "Laravel"
        return None


# ── Robots.txt Parser ──────────────────────────────────────────────────────────

class RobotsParser:
    def __init__(self):
        self._parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    async def can_fetch(
        self, url: str, user_agent: str, session: aiohttp.ClientSession
    ) -> bool:
        domain = urlparse(url).netloc
        if domain not in self._parsers:
            robots_url = f"{urlparse(url).scheme}://{domain}/robots.txt"
            try:
                async with session.get(robots_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    content = await resp.text()
                    rp = urllib.robotparser.RobotFileParser()
                    rp.parse(content.splitlines())
                    self._parsers[domain] = rp
            except Exception:
                # If robots.txt fails, assume allowed
                self._parsers[domain] = None
                return True

        rp = self._parsers.get(domain)
        if rp is None:
            return True
        return rp.can_fetch(user_agent, url)

    async def discover_sitemap(
        self, base_url: str, session: aiohttp.ClientSession
    ) -> list[str]:
        """Try to find and parse sitemap URLs."""
        parsed = urlparse(base_url)
        candidates = [
            f"{parsed.scheme}://{parsed.netloc}/sitemap.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap_index.xml",
            f"{parsed.scheme}://{parsed.netloc}/sitemap.txt",
        ]
        urls = []
        for sitemap_url in candidates:
            try:
                async with session.get(
                    sitemap_url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        content = await resp.text()
                        # Parse XML sitemap
                        loc_re = re.compile(r"<loc>(.*?)</loc>", re.IGNORECASE)
                        urls.extend(loc_re.findall(content))
                        logger.info("sitemap_discovered", url=sitemap_url, count=len(urls))
            except Exception:
                continue
        return urls


# ── Main Crawler ───────────────────────────────────────────────────────────────

class AsyncCrawler:
    """
    High-performance async web crawler.
    - aiohttp for speed
    - Playwright for JS rendering
    - Smart deduplication
    - Respect robots.txt
    - Sitemap seeding
    """

    def __init__(
        self,
        config: CrawlConfig,
        result_callback: Callable[[CrawlResult], None] | None = None,
    ):
        self.config = config
        self.result_callback = result_callback
        self.normalizer = URLNormalizer(config.target_url)
        self.robots = RobotsParser()

        # State
        self._queue: asyncio.Queue = asyncio.Queue()
        self._visited: set[str] = set()
        self._fingerprints: set[str] = set()
        self._request_count: int = 0
        self._start_time: float = 0
        self._running: bool = False

        # Stats
        self.stats: dict = defaultdict(int)

        # Compiled scope regex
        self._scope_patterns = [
            re.compile(p) for p in config.scope_regex
        ] if config.scope_regex else []

    def _url_fingerprint(self, url: str) -> str:
        """Normalized URL hash for deduplication."""
        parsed = urlparse(url)
        # Sort query params for normalization
        params = sorted(urllib.parse.parse_qs(parsed.query).items())
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}?{'&'.join(f'{k}={v[0]}' for k, v in params)}"
        return hashlib.md5(normalized.encode()).hexdigest()

    def _is_excluded(self, url: str) -> bool:
        ext = "." + url.split(".")[-1].lower().split("?")[0]
        if ext in self.config.excluded_extensions:
            return True
        if self._scope_patterns:
            return not any(p.search(url) for p in self._scope_patterns)
        return False

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        url: str,
        method: str = "GET",
        depth: int = 0,
        referrer: str | None = None,
    ) -> CrawlResult:
        start = time.monotonic()
        try:
            headers = {
                "User-Agent": self.config.user_agent,
                **self.config.custom_headers,
            }
            if referrer:
                headers["Referer"] = referrer

            timeout = aiohttp.ClientTimeout(total=self.config.timeout_seconds)
            async with session.request(
                method, url,
                headers=headers,
                allow_redirects=self.config.follow_redirects,
                timeout=timeout,
            ) as resp:
                body = await resp.read()
                resp_time = int((time.monotonic() - start) * 1000)
                ct = resp.headers.get("Content-Type", "")

                return CrawlResult(
                    url=str(resp.url),
                    method=method,
                    status_code=resp.status,
                    headers=dict(resp.request_info.headers),
                    response_headers=dict(resp.headers),
                    body=body,
                    content_type=ct,
                    response_time_ms=resp_time,
                    depth=depth,
                    referrer=referrer,
                )
        except asyncio.TimeoutError:
            return CrawlResult(
                url=url, method=method, status_code=None,
                headers={}, response_headers={}, body=None,
                content_type="", response_time_ms=self.config.timeout_seconds * 1000,
                depth=depth, referrer=referrer, error="timeout"
            )
        except Exception as e:
            return CrawlResult(
                url=url, method=method, status_code=None,
                headers={}, response_headers={}, body=None,
                content_type="", response_time_ms=0,
                depth=depth, referrer=referrer, error=str(e)
            )

    async def _process_result(
        self,
        result: CrawlResult,
        session: aiohttp.ClientSession,
    ) -> None:
        """Parse response, extract links, queue new URLs."""
        self._request_count += 1
        self.stats["total_requests"] += 1

        if result.error:
            self.stats["errors"] += 1
            return

        if result.body and "html" in result.content_type.lower():
            try:
                html = result.body.decode("utf-8", errors="replace")
                links, forms, ws_urls, js_eps = LinkExtractor.extract_from_html(
                    html, result.url, self.normalizer
                )
                result.links_found = links
                result.forms_found = forms
                result.websocket_urls = ws_urls
                result.js_endpoints = js_eps
                result.framework = LinkExtractor.detect_framework(
                    html, result.response_headers
                )

                # Queue new links
                if result.depth < self.config.max_depth:
                    for link in links + js_eps:
                        if not self.normalizer.is_in_scope(link, self.config.crawl_subdomains):
                            continue
                        if self._is_excluded(link):
                            continue
                        fp = self._url_fingerprint(link)
                        if fp not in self._fingerprints:
                            self._fingerprints.add(fp)
                            await self._queue.put((link, result.depth + 1, result.url))
            except Exception as e:
                logger.warning("html_parse_error", url=result.url, error=str(e))

        # Callback for parameter extraction
        if self.result_callback:
            await asyncio.get_event_loop().run_in_executor(
                None, self.result_callback, result
            )

    async def crawl(
        self,
        resume_urls: list[str] | None = None,
    ) -> AsyncGenerator[CrawlResult, None]:
        """Main crawl generator."""
        self._running = True
        self._start_time = time.monotonic()

        connector = aiohttp.TCPConnector(
            limit=self.config.concurrency * 2,
            limit_per_host=self.config.concurrency,
            ssl=False,
            enable_cleanup_closed=True,
        )
        session_kwargs = {
            "connector": connector,
            "cookies": self.config.cookies,
        }

        async with aiohttp.ClientSession(**session_kwargs) as session:
            # Seed queue
            seed_urls = [self.config.target_url]

            # Sitemap discovery
            sitemap_urls = await self.robots.discover_sitemap(
                self.config.target_url, session
            )
            seed_urls.extend(sitemap_urls[:1000])  # cap sitemap seeds

            # Resume from checkpoint
            if resume_urls:
                seed_urls.extend(resume_urls)

            for url in seed_urls:
                fp = self._url_fingerprint(url)
                if fp not in self._fingerprints:
                    self._fingerprints.add(fp)
                    await self._queue.put((url, 0, None))

            # Worker pool
            results_buffer = []

            async def worker():
                while self._running:
                    try:
                        url, depth, referrer = await asyncio.wait_for(
                            self._queue.get(), timeout=5.0
                        )
                    except asyncio.TimeoutError:
                        break

                    if self._request_count >= self.config.max_requests:
                        break

                    if self.config.respect_robots_txt:
                        allowed = await self.robots.can_fetch(
                            url, self.config.user_agent, session
                        )
                        if not allowed:
                            self.stats["robots_blocked"] += 1
                            self._queue.task_done()
                            continue

                    if self.config.request_delay_ms > 0:
                        await asyncio.sleep(self.config.request_delay_ms / 1000)

                    result = await self._fetch(session, url, depth=depth, referrer=referrer)
                    await self._process_result(result, session)
                    results_buffer.append(result)
                    self._queue.task_done()

                    logger.debug(
                        "crawled",
                        url=url[:100],
                        status=result.status_code,
                        depth=depth,
                        queue_size=self._queue.qsize(),
                    )

            # Launch workers
            tasks = [asyncio.create_task(worker()) for _ in range(self.config.concurrency)]
            await asyncio.gather(*tasks, return_exceptions=True)

            elapsed = time.monotonic() - self._start_time
            rps = self._request_count / elapsed if elapsed > 0 else 0
            logger.info(
                "crawl_complete",
                total_requests=self._request_count,
                elapsed_seconds=round(elapsed, 1),
                rps=round(rps, 1),
                stats=dict(self.stats),
            )

            for result in results_buffer:
                yield result

    async def crawl_with_playwright(
        self, url: str
    ) -> CrawlResult:
        """
        JavaScript-rendered crawl using Playwright.
        Used for SPAs (React, Angular, Vue).
        """
        async with async_playwright() as pw:
            browser: Browser = await pw.chromium.launch(headless=True)
            context: BrowserContext = await browser.new_context(
                user_agent=self.config.user_agent,
                extra_http_headers=self.config.custom_headers,
            )

            # Capture all network requests
            requests_captured = []
            page: Page = await context.new_page()
            page.on("request", lambda req: requests_captured.append({
                "url": req.url,
                "method": req.method,
                "headers": dict(req.headers),
                "post_data": req.post_data,
            }))

            start = time.monotonic()
            response = await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            resp_time = int((time.monotonic() - start) * 1000)

            await browser.close()

            return CrawlResult(
                url=url,
                method="GET",
                status_code=response.status if response else None,
                headers={},
                response_headers=dict(response.headers) if response else {},
                body=html.encode(),
                content_type="text/html",
                response_time_ms=resp_time,
                depth=0,
                referrer=None,
                framework=LinkExtractor.detect_framework(html, {}),
            )

    def get_stats(self) -> dict:
        elapsed = time.monotonic() - self._start_time if self._start_time else 0
        return {
            **dict(self.stats),
            "elapsed_seconds": round(elapsed, 1),
            "requests_per_second": round(self._request_count / max(elapsed, 0.001), 1),
            "queue_remaining": self._queue.qsize(),
        }
