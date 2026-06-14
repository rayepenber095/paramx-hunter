"""
ParamX Hunter - Browser Engine
Playwright-based JavaScript rendering for SPAs (React, Angular, Vue)
Captures all network traffic including XHR/fetch for parameter discovery.
"""

import asyncio
import re
from dataclasses import dataclass, field

import structlog
from playwright.async_api import Request as PWRequest
from playwright.async_api import async_playwright

logger = structlog.get_logger(__name__)


@dataclass
class CapturedRequest:
    url: str
    method: str
    headers: dict
    post_data: str | None
    resource_type: str  # xhr, fetch, document, script, etc.


@dataclass
class CapturedResponse:
    url: str
    status: int
    headers: dict
    body: str | None


@dataclass
class BrowserScanResult:
    url: str
    html: str
    title: str
    framework: str | None
    captured_requests: list[CapturedRequest] = field(default_factory=list)
    captured_responses: list[CapturedResponse] = field(default_factory=list)
    websocket_connections: list[str] = field(default_factory=list)
    console_errors: list[str] = field(default_factory=list)
    local_storage: dict = field(default_factory=dict)
    session_storage: dict = field(default_factory=dict)


# ── Framework Detection Signatures ─────────────────────────────────────────────

FRAMEWORK_SIGNATURES = {
    "React": [
        r"react(?:-dom)?[\.\-]\w*\.js",
        r"__REACT_DEVTOOLS",
        r"data-reactroot",
        r"_reactRootContainer",
    ],
    "Next.js": [
        r"__NEXT_DATA__",
        r"/_next/static/",
        r"__next_f",
    ],
    "Angular": [
        r"ng-version",
        r"ng-app",
        r"angular(?:\.min)?\.js",
        r"__ngContext__",
    ],
    "Vue.js": [
        r"__VUE__",
        r"vue(?:\.min)?\.js",
        r"data-v-[a-f0-9]{8}",
    ],
    "Nuxt.js": [
        r"__NUXT__",
        r"/_nuxt/",
    ],
    "Svelte": [
        r"svelte-[a-z0-9]+",
        r"__SVELTE__",
    ],
}


class BrowserEngine:
    """
    Playwright-based browser automation for JS-heavy SPAs.
    Captures all XHR/fetch traffic that the crawler would otherwise miss.
    """

    def __init__(
        self,
        user_agent: str = "ParamXHunter/1.0 (+https://paramxhunter.io/bot)",
        headers: dict | None = None,
        cookies: list[dict] | None = None,
        timeout_ms: int = 30000,
        headless: bool = True,
    ):
        self.user_agent = user_agent
        self.headers = headers or {}
        self.cookies = cookies or []
        self.timeout_ms = timeout_ms
        self.headless = headless

    async def scan_page(self, url: str) -> BrowserScanResult:
        """
        Load a page with full JS execution, capturing all network activity.
        """
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=self.user_agent,
                extra_http_headers=self.headers,
                viewport={"width": 1920, "height": 1080},
            )

            if self.cookies:
                await context.add_cookies(self.cookies)

            page = await context.new_page()

            captured_requests: list[CapturedRequest] = []
            captured_responses: list[CapturedResponse] = []
            websocket_urls: list[str] = []
            console_errors: list[str] = []

            # ── Network listeners ────────────────────────────────────────────
            def on_request(req: PWRequest):
                if req.resource_type in ("xhr", "fetch", "document", "websocket"):
                    captured_requests.append(
                        CapturedRequest(
                            url=req.url,
                            method=req.method,
                            headers=dict(req.headers),
                            post_data=req.post_data,
                            resource_type=req.resource_type,
                        )
                    )

            async def on_response(resp):
                try:
                    ct = resp.headers.get("content-type", "")
                    body = None
                    if "json" in ct or "text" in ct:
                        try:
                            body = await resp.text()
                        except Exception:
                            body = None
                    captured_responses.append(
                        CapturedResponse(
                            url=resp.url,
                            status=resp.status,
                            headers=dict(resp.headers),
                            body=body[:50000] if body else None,  # cap response body
                        )
                    )
                except Exception:
                    pass

            def on_websocket(ws):
                websocket_urls.append(ws.url)

            def on_console(msg):
                if msg.type == "error":
                    console_errors.append(msg.text)

            page.on("request", on_request)
            page.on("response", lambda resp: asyncio.create_task(on_response(resp)))
            page.on("websocket", on_websocket)
            page.on("console", on_console)

            # ── Navigate ──────────────────────────────────────────────────────
            try:
                await page.goto(url, wait_until="networkidle", timeout=self.timeout_ms)
            except Exception as e:
                logger.warning("page_load_timeout", url=url, error=str(e))
                # Try domcontentloaded as fallback
                try:
                    await page.goto(
                        url, wait_until="domcontentloaded", timeout=self.timeout_ms
                    )
                except Exception:
                    pass

            # Give SPAs a moment to fire async requests
            await page.wait_for_timeout(1500)

            html = await page.content()
            title = await page.title()

            # ── Storage extraction ───────────────────────────────────────────
            local_storage = await page.evaluate(
                """() => {
                const items = {};
                for (let i = 0; i < localStorage.length; i++) {
                    const key = localStorage.key(i);
                    items[key] = localStorage.getItem(key);
                }
                return items;
            }"""
            )

            session_storage = await page.evaluate(
                """() => {
                const items = {};
                for (let i = 0; i < sessionStorage.length; i++) {
                    const key = sessionStorage.key(i);
                    items[key] = sessionStorage.getItem(key);
                }
                return items;
            }"""
            )

            framework = self._detect_framework(html, captured_requests)

            await browser.close()

            return BrowserScanResult(
                url=url,
                html=html,
                title=title,
                framework=framework,
                captured_requests=captured_requests,
                captured_responses=captured_responses,
                websocket_connections=list(set(websocket_urls)),
                console_errors=console_errors,
                local_storage=local_storage,
                session_storage=session_storage,
            )

    def _detect_framework(
        self, html: str, requests: list[CapturedRequest]
    ) -> str | None:
        combined = html + " ".join(r.url for r in requests)
        for framework, patterns in FRAMEWORK_SIGNATURES.items():
            for pattern in patterns:
                if re.search(pattern, combined, re.IGNORECASE):
                    return framework
        return None

    async def extract_xhr_endpoints(self, result: BrowserScanResult) -> list[dict]:
        """Extract unique API endpoints from captured XHR/fetch requests."""
        endpoints = {}
        for req in result.captured_requests:
            if req.resource_type in ("xhr", "fetch"):
                key = f"{req.method}:{req.url.split('?')[0]}"
                if key not in endpoints:
                    endpoints[key] = {
                        "url": req.url,
                        "method": req.method,
                        "headers": req.headers,
                        "post_data": req.post_data,
                    }
        return list(endpoints.values())
