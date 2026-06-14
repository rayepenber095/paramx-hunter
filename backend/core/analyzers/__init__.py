"""
ParamX Hunter - API Discovery Engine
Detects Swagger/OpenAPI docs, GraphQL endpoints, REST patterns.
"""

import json
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import aiohttp
import structlog

logger = structlog.get_logger(__name__)

# Common paths for API docs / schemas
OPENAPI_PATHS = [
    "/swagger.json",
    "/swagger.yaml",
    "/swagger/v1/swagger.json",
    "/api-docs",
    "/api-docs.json",
    "/v1/api-docs",
    "/v2/api-docs",
    "/v3/api-docs",
    "/openapi.json",
    "/openapi.yaml",
    "/api/swagger.json",
    "/api/openapi.json",
    "/.well-known/openapi.json",
]

GRAPHQL_PATHS = [
    "/graphql",
    "/graphql/v1",
    "/api/graphql",
    "/gql",
    "/query",
    "/v1/graphql",
    "/v2/graphql",
]

GRAPHQL_INTROSPECTION_QUERY = json.dumps(
    {
        "query": """
    query IntrospectionQuery {
      __schema {
        queryType { name }
        mutationType { name }
        subscriptionType { name }
        types { name kind description fields(includeDeprecated: true) { name } }
      }
    }
    """
    }
)


@dataclass
class DiscoveredAPI:
    url: str
    api_type: str  # "openapi", "swagger", "graphql", "rest"
    version: str | None = None
    title: str | None = None
    endpoints_count: int = 0
    parameters_count: int = 0
    spec: dict | None = None
    introspection: dict | None = None
    endpoints: list[dict] = field(default_factory=list)


class APIDiscoveryEngine:
    def __init__(self, base_url: str, session: aiohttp.ClientSession):
        self.base_url = base_url
        self.session = session
        self._discovered: list[DiscoveredAPI] = []

    async def discover_all(self) -> list[DiscoveredAPI]:
        await self._probe_openapi()
        await self._probe_graphql()
        logger.info(
            "api_discovery_complete",
            base_url=self.base_url,
            found=len(self._discovered),
        )
        return self._discovered

    async def _probe_openapi(self):
        for path in OPENAPI_PATHS:
            url = urljoin(self.base_url, path)
            try:
                async with self.session.get(
                    url, timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status != 200:
                        continue
                    ct = resp.headers.get("content-type", "")
                    if (
                        "json" in ct
                        or "yaml" in ct
                        or path.endswith((".json", ".yaml"))
                    ):
                        text = await resp.text()
                        spec = _parse_openapi_spec(text)
                        if spec:
                            api = _build_openapi_api(url, spec)
                            self._discovered.append(api)
                            logger.info("openapi_found", url=url, title=api.title)
            except Exception:
                pass

    async def _probe_graphql(self):
        for path in GRAPHQL_PATHS:
            url = urljoin(self.base_url, path)
            try:
                async with self.session.post(
                    url,
                    data=GRAPHQL_INTROSPECTION_QUERY,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status not in (200, 400):
                        continue
                    body = await resp.json(content_type=None)
                    if "data" in body or "errors" in body:
                        api = DiscoveredAPI(
                            url=url,
                            api_type="graphql",
                            introspection=body.get("data"),
                        )
                        # Parse schema types
                        schema = body.get("data", {}).get("__schema", {})
                        types = schema.get("types", [])
                        api.endpoints_count = len(
                            [
                                t
                                for t in types
                                if t.get("kind") not in ("SCALAR", "BUILT_IN")
                            ]
                        )
                        self._discovered.append(api)
                        logger.info("graphql_found", url=url)
            except Exception:
                pass

    async def detect_from_response(
        self, url: str, body: str, headers: dict
    ) -> DiscoveredAPI | None:
        """Detect API type from a live response body + headers."""
        ct = headers.get("content-type", "").lower()

        # Detect REST JSON APIs
        if "application/json" in ct:
            parsed = urlparse(url)
            path = parsed.path
            # Common REST patterns
            if re.search(r"/api/v?\d+/", path) or re.search(r"/v\d+/", path):
                return DiscoveredAPI(url=url, api_type="rest")

        # Detect GraphQL in body
        if '"__typename"' in body or '"errors"' in body and '"locations"' in body:
            return DiscoveredAPI(url=url, api_type="graphql")

        return None


def _parse_openapi_spec(text: str) -> dict | None:
    try:
        import yaml

        data = yaml.safe_load(text)
        if isinstance(data, dict) and ("openapi" in data or "swagger" in data):
            return data
    except Exception:
        pass
    try:
        data = json.loads(text)
        if isinstance(data, dict) and ("openapi" in data or "swagger" in data):
            return data
    except Exception:
        pass
    return None


def _build_openapi_api(url: str, spec: dict) -> DiscoveredAPI:
    info = spec.get("info", {})
    paths = spec.get("paths", {})

    endpoints = []
    param_count = 0
    for path, path_item in paths.items():
        for method, op in path_item.items():
            if method not in (
                "get",
                "post",
                "put",
                "patch",
                "delete",
                "head",
                "options",
            ):
                continue
            params = op.get("parameters", [])
            param_count += len(params)
            req_body = op.get("requestBody", {})
            for media_content in req_body.get("content", {}).values():
                schema = media_content.get("schema", {})
                param_count += len(schema.get("properties", {}))
            endpoints.append(
                {
                    "path": path,
                    "method": method.upper(),
                    "summary": op.get("summary", ""),
                    "param_count": len(params),
                }
            )

    version = spec.get("openapi") or spec.get("swagger") or "unknown"
    api_type = "openapi" if "openapi" in spec else "swagger"

    return DiscoveredAPI(
        url=url,
        api_type=api_type,
        version=str(version),
        title=info.get("title"),
        endpoints_count=len(endpoints),
        parameters_count=param_count,
        spec=spec,
        endpoints=endpoints,
    )
