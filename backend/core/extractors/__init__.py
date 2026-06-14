"""
ParamX Hunter - Parameter Extraction Engine
Modular extractor framework supporting 40+ parameter types
"""

import base64
import hashlib
import json
import re
import urllib.parse
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generator
from xml.etree import ElementTree as ET

import defusedxml.ElementTree as DefusedET

# ── Extracted Parameter Dataclass ─────────────────────────────────────────────


@dataclass
class ExtractedParameter:
    name: str
    value: Any
    param_type: str
    source: str
    endpoint: str
    method: str
    confidence_score: float = 1.0
    is_sensitive: bool = False
    is_hidden: bool = False
    data_type: str | None = None
    risk_tags: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    extra: dict = field(default_factory=dict)
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)

    def signature(self) -> str:
        """Unique fingerprint for deduplication."""
        key = f"{self.endpoint}:{self.name}:{self.param_type}:{self.source}"
        return hashlib.md5(key.encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "value": str(self.value)[:500] if self.value else None,
            "param_type": self.param_type,
            "source": self.source,
            "endpoint": self.endpoint,
            "method": self.method,
            "confidence_score": self.confidence_score,
            "is_sensitive": self.is_sensitive,
            "is_hidden": self.is_hidden,
            "data_type": self.data_type,
            "risk_tags": self.risk_tags,
            "tags": self.tags,
            "extra": self.extra,
        }


# ── Sensitive patterns ─────────────────────────────────────────────────────────

SENSITIVE_PARAM_PATTERNS = re.compile(
    r"(password|passwd|pwd|secret|token|api[_-]?key|auth|credential|"
    r"access[_-]?key|private[_-]?key|client[_-]?secret|session|"
    r"ssn|social[_-]?security|credit[_-]?card|cvv|pin|dob|birth)",
    re.IGNORECASE,
)

API_KEY_PATTERNS = re.compile(
    r"(api[_-]?key|apikey|x-api-key|authorization|bearer|token|access[_-]?token)",
    re.IGNORECASE,
)

REDIRECT_PATTERNS = re.compile(
    r"(redirect|return[_-]?url|next|callback|goto|url|redir|forward|dest|destination)",
    re.IGNORECASE,
)

PAGINATION_PATTERNS = re.compile(
    r"^(page|per[_-]?page|limit|offset|start|end|cursor|after|before|from|size|count)$",
    re.IGNORECASE,
)

SORT_PATTERNS = re.compile(
    r"^(sort|sort[_-]?by|order|order[_-]?by|dir|direction|asc|desc)$",
    re.IGNORECASE,
)

SEARCH_PATTERNS = re.compile(
    r"^(q|query|search|s|term|keyword|keywords|find|filter)$",
    re.IGNORECASE,
)

DEBUG_PATTERNS = re.compile(
    r"^(debug|verbose|trace|log|logging|test|dev|development|sandbox)$",
    re.IGNORECASE,
)

VERSION_PATTERNS = re.compile(
    r"^(v|version|ver|api[_-]?version|api[_-]?v)$",
    re.IGNORECASE,
)

FEATURE_FLAG_PATTERNS = re.compile(
    r"^(feature[_-]?flag|flag|ff[_-]?\w+|enable[_-]?\w+|disable[_-]?\w+|ab[_-]?test)$",
    re.IGNORECASE,
)


def classify_parameter(name: str, base_type: str) -> tuple[str, list[str], bool]:
    """Returns (refined_type, risk_tags, is_sensitive)."""
    risk_tags = []
    is_sensitive = bool(SENSITIVE_PARAM_PATTERNS.search(name))

    if is_sensitive:
        risk_tags.append("sensitive-data")

    # API key exposure risk tag applies regardless of base type
    if API_KEY_PATTERNS.search(name):
        risk_tags.append("api-key-exposure")
        is_sensitive = True

    # Generic base types can be reclassified into more specific
    # functional categories. Already-specific types (header_auth,
    # cookie, session, jwt_claim, csrf_token, etc.) are preserved.
    GENERIC_TYPES = {
        "url_query",
        "fragment",
        "form_urlencoded",
        "json_body",
        "json_nested",
        "header_custom",
        "path",
    }
    if base_type not in GENERIC_TYPES:
        return base_type, risk_tags, is_sensitive

    if REDIRECT_PATTERNS.search(name):
        return "redirect", risk_tags + ["open-redirect-candidate"], is_sensitive
    if PAGINATION_PATTERNS.match(name):
        return "pagination", risk_tags, is_sensitive
    if SORT_PATTERNS.match(name):
        return "sorting", risk_tags, is_sensitive
    if SEARCH_PATTERNS.match(name):
        return "search", risk_tags, is_sensitive
    if DEBUG_PATTERNS.match(name):
        return "debug", risk_tags + ["debug-exposure"], is_sensitive
    if VERSION_PATTERNS.match(name):
        return "version", risk_tags, is_sensitive
    if FEATURE_FLAG_PATTERNS.match(name):
        return "feature_flag", risk_tags, is_sensitive
    if API_KEY_PATTERNS.search(name):
        return "api_key", risk_tags, True

    return base_type, risk_tags, is_sensitive


def infer_data_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    val_str = str(value).strip()
    if val_str.lower() in ("true", "false"):
        return "boolean"
    try:
        int(val_str)
        return "integer"
    except ValueError:
        pass
    try:
        float(val_str)
        return "float"
    except ValueError:
        pass
    try:
        json.loads(val_str)
        return "json"
    except (json.JSONDecodeError, ValueError):
        pass
    return "string"


# ── Base Extractor ─────────────────────────────────────────────────────────────


class BaseExtractor(ABC):
    """Abstract base for all parameter extractors."""

    extractor_name: str = "base"

    def __init__(self, endpoint: str, method: str = "GET"):
        self.endpoint = endpoint
        self.method = method

    @abstractmethod
    def extract(self, data: Any) -> Generator[ExtractedParameter, None, None]:
        """Yield extracted parameters."""
        ...

    def _make_param(
        self,
        name: str,
        value: Any,
        param_type: str,
        source: str,
        confidence: float = 1.0,
        extra: dict | None = None,
    ) -> ExtractedParameter:
        refined_type, risk_tags, is_sensitive = classify_parameter(name, param_type)
        return ExtractedParameter(
            name=name,
            value=value,
            param_type=refined_type,
            source=source,
            endpoint=self.endpoint,
            method=self.method,
            confidence_score=confidence,
            is_sensitive=is_sensitive,
            data_type=infer_data_type(value),
            risk_tags=risk_tags,
            extra=extra or {},
        )


# ── URL Extractor ──────────────────────────────────────────────────────────────


class URLExtractor(BaseExtractor):
    """Extracts query, path, and fragment parameters from URLs."""

    extractor_name = "url"

    def extract(self, data: str) -> Generator[ExtractedParameter, None, None]:
        """data = raw URL string."""
        parsed = urllib.parse.urlparse(data)

        # Query parameters
        query_params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        for name, values in query_params.items():
            for val in values:
                yield self._make_param(name, val, "url_query", "url_query")

        # Fragment parameters
        if parsed.fragment and "=" in parsed.fragment:
            frag_params = urllib.parse.parse_qs(parsed.fragment, keep_blank_values=True)
            for name, values in frag_params.items():
                for val in values:
                    yield self._make_param(name, val, "fragment", "url_fragment")

        # Path parameters (detect /:id/ style or /123/ style)
        path_segments = [s for s in parsed.path.split("/") if s]
        for i, seg in enumerate(path_segments):
            if re.match(r"^\d+$", seg):
                yield self._make_param(
                    f"path_segment_{i}",
                    seg,
                    "path",
                    "url_path",
                    confidence=0.7,
                    extra={"position": i},
                )
            elif re.match(r"^[0-9a-f-]{32,}$", seg, re.IGNORECASE):
                yield self._make_param(
                    f"path_id_{i}",
                    seg,
                    "path",
                    "url_path",
                    confidence=0.9,
                    extra={"position": i, "pattern": "uuid_like"},
                )


# ── Header Extractor ───────────────────────────────────────────────────────────

STANDARD_HEADERS = {
    "accept",
    "accept-encoding",
    "accept-language",
    "cache-control",
    "connection",
    "content-length",
    "content-type",
    "host",
    "origin",
    "referer",
    "user-agent",
}

AUTH_HEADERS = {
    "authorization",
    "x-api-key",
    "x-auth-token",
    "x-access-token",
    "x-session-token",
    "api-key",
    "token",
    "x-csrf-token",
    "x-xsrf-token",
}


class HeaderExtractor(BaseExtractor):
    extractor_name = "header"

    def extract(
        self, data: dict[str, str]
    ) -> Generator[ExtractedParameter, None, None]:
        for name, value in data.items():
            lname = name.lower()

            if lname in STANDARD_HEADERS:
                ptype = "header_standard"
            elif lname in AUTH_HEADERS:
                ptype = "header_auth"
            else:
                ptype = "header_custom"

            yield self._make_param(name, value, ptype, "http_header")


# ── Cookie Extractor ───────────────────────────────────────────────────────────

SESSION_COOKIE_PATTERNS = re.compile(
    r"(session|sess|sid|sessionid|phpsessid|jsessionid|asp\.net_sessionid)",
    re.IGNORECASE,
)


class CookieExtractor(BaseExtractor):
    extractor_name = "cookie"

    def extract(
        self, data: dict[str, str]
    ) -> Generator[ExtractedParameter, None, None]:
        for name, value in data.items():
            is_session = bool(SESSION_COOKIE_PATTERNS.search(name))
            ptype = "session" if is_session else "cookie"

            # Detect JWT in cookies
            if value and value.count(".") == 2:
                try:
                    parts = value.split(".")
                    base64.urlsafe_b64decode(parts[0] + "==")
                    ptype = "jwt_claim"
                except Exception:
                    pass

            param = self._make_param(name, value, ptype, "cookie")
            if is_session:
                param.tags.append("session-cookie")
            yield param


# ── JSON Extractor ─────────────────────────────────────────────────────────────


class JSONExtractor(BaseExtractor):
    extractor_name = "json"

    def extract(self, data: str | dict) -> Generator[ExtractedParameter, None, None]:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return

        yield from self._extract_recursive(data, path="")

    def _extract_recursive(
        self, data: Any, path: str
    ) -> Generator[ExtractedParameter, None, None]:
        if isinstance(data, dict):
            for key, value in data.items():
                full_path = f"{path}.{key}" if path else key
                ptype = "json_nested" if "." in full_path else "json_body"

                if isinstance(value, (dict, list)):
                    yield self._make_param(
                        full_path,
                        json.dumps(value)[:200],
                        ptype,
                        "request_body",
                        extra={"json_path": full_path},
                    )
                    yield from self._extract_recursive(value, full_path)
                else:
                    yield self._make_param(
                        full_path,
                        value,
                        ptype,
                        "request_body",
                        extra={"json_path": full_path},
                    )
        elif isinstance(data, list):
            for i, item in enumerate(data[:10]):  # cap array inspection
                yield from self._extract_recursive(item, f"{path}[{i}]")


# ── XML Extractor ──────────────────────────────────────────────────────────────


class XMLExtractor(BaseExtractor):
    extractor_name = "xml"

    def extract(self, data: str) -> Generator[ExtractedParameter, None, None]:
        try:
            root = DefusedET.fromstring(data)
            yield from self._walk(root, "")
        except ET.ParseError:
            return

    def _walk(self, element, path: str) -> Generator[ExtractedParameter, None, None]:
        tag = re.sub(r"\{.*?\}", "", element.tag)  # strip namespace
        current_path = f"{path}/{tag}" if path else tag

        # Element text
        if element.text and element.text.strip():
            yield self._make_param(
                current_path,
                element.text.strip(),
                "xml",
                "request_body",
                extra={"xml_path": current_path},
            )

        # Attributes
        for attr_name, attr_val in element.attrib.items():
            yield self._make_param(
                f"{current_path}/@{attr_name}",
                attr_val,
                "xml",
                "request_body",
                extra={"xml_path": current_path, "is_attribute": True},
            )

        for child in element:
            yield from self._walk(child, current_path)


# ── SOAP Extractor ─────────────────────────────────────────────────────────────


class SOAPExtractor(XMLExtractor):
    extractor_name = "soap"

    SOAP_NS = {
        "env": "http://schemas.xmlsoap.org/soap/envelope/",
        "env12": "http://www.w3.org/2003/05/soap-envelope",
    }

    def extract(self, data: str) -> Generator[ExtractedParameter, None, None]:
        try:
            root = DefusedET.fromstring(data)
            for item in self._walk(root, ""):
                item.param_type = "soap"
                item.source = "soap_body"
                yield item
        except ET.ParseError:
            return


# ── GraphQL Extractor ──────────────────────────────────────────────────────────


class GraphQLExtractor(BaseExtractor):
    extractor_name = "graphql"

    OPERATION_RE = re.compile(
        r"(query|mutation|subscription)\s+(\w+)?\s*\(([^)]*)\)", re.DOTALL
    )
    FIELD_RE = re.compile(r"\$(\w+)\s*:\s*(\w+[!?]*)")

    def extract(self, data: str | dict) -> Generator[ExtractedParameter, None, None]:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return

        query = data.get("query", "")
        variables = data.get("variables", {})
        operation_name = data.get("operationName")

        # Extract declared variables from query
        for match in self.FIELD_RE.finditer(query):
            var_name, var_type = match.group(1), match.group(2)
            value = variables.get(var_name) if variables else None
            yield self._make_param(
                var_name,
                value,
                "graphql_variable",
                "graphql",
                extra={"gql_type": var_type, "operation": operation_name},
            )

        # Detect operation type
        op_match = self.OPERATION_RE.search(query)
        if op_match:
            yield self._make_param(
                "operationName",
                operation_name,
                "graphql_query",
                "graphql",
                extra={"operation_type": op_match.group(1)},
            )

        # Extract variables payload
        if variables and isinstance(variables, dict):
            json_extractor = JSONExtractor(self.endpoint, self.method)
            for param in json_extractor.extract(variables):
                param.param_type = "graphql_variable"
                param.source = "graphql"
                yield param


# ── Form Extractor ─────────────────────────────────────────────────────────────


class FormExtractor(BaseExtractor):
    extractor_name = "form"

    CSRF_PATTERNS = re.compile(
        r"(csrf|xsrf|_token|authenticity[_-]token|verify[_-]token|antiforgery)",
        re.IGNORECASE,
    )

    def extract(self, data: str) -> Generator[ExtractedParameter, None, None]:
        """data = URL-encoded form body string."""
        params = urllib.parse.parse_qs(data, keep_blank_values=True)
        for name, values in params.items():
            for val in values:
                if self.CSRF_PATTERNS.search(name):
                    ptype = "csrf_token"
                else:
                    ptype = "form_urlencoded"
                yield self._make_param(name, val, ptype, "form_body")


class HiddenFieldExtractor(BaseExtractor):
    """Extracts hidden form fields from HTML."""

    extractor_name = "hidden_field"

    HIDDEN_FIELD_RE = re.compile(
        r'<input[^>]+type=["\']hidden["\'][^>]*name=["\']([^"\']+)["\'][^>]*(?:value=["\']([^"\']*)["\'])?[^>]*>',
        re.IGNORECASE,
    )
    HIDDEN_FIELD_RE2 = re.compile(
        r'<input[^>]+name=["\']([^"\']+)["\'][^>]*type=["\']hidden["\'][^>]*(?:value=["\']([^"\']*)["\'])?[^>]*>',
        re.IGNORECASE,
    )

    def extract(self, html: str) -> Generator[ExtractedParameter, None, None]:
        seen = set()
        for pattern in (self.HIDDEN_FIELD_RE, self.HIDDEN_FIELD_RE2):
            for match in pattern.finditer(html):
                name = match.group(1)
                value = match.group(2) or ""
                if name in seen:
                    continue
                seen.add(name)
                yield self._make_param(
                    name,
                    value,
                    "hidden_field",
                    "html_form",
                    extra={"is_hidden_input": True},
                )


# ── JWT Extractor ──────────────────────────────────────────────────────────────


class JWTExtractor(BaseExtractor):
    extractor_name = "jwt"

    def extract(self, token: str) -> Generator[ExtractedParameter, None, None]:
        """data = raw JWT string."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return

            # Decode header
            header_raw = base64.urlsafe_b64decode(parts[0] + "==").decode()
            header = json.loads(header_raw)
            for key, val in header.items():
                yield self._make_param(
                    f"jwt.header.{key}",
                    val,
                    "jwt_claim",
                    "jwt_header",
                    confidence=0.95,
                    extra={"jwt_section": "header"},
                )

            # Decode payload
            payload_raw = base64.urlsafe_b64decode(parts[1] + "==").decode()
            payload = json.loads(payload_raw)
            for key, val in payload.items():
                yield self._make_param(
                    f"jwt.{key}",
                    val,
                    "jwt_claim",
                    "jwt_payload",
                    confidence=0.95,
                    extra={"jwt_section": "payload", "claim": key},
                )
        except Exception:
            return


# ── WebSocket Extractor ────────────────────────────────────────────────────────


class WebSocketExtractor(BaseExtractor):
    extractor_name = "websocket"

    def extract(self, data: str | dict) -> Generator[ExtractedParameter, None, None]:
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                yield self._make_param(
                    "ws_raw_message", data, "websocket", "websocket", confidence=0.5
                )
                return

        if isinstance(data, dict):
            json_ext = JSONExtractor(self.endpoint, self.method)
            for param in json_ext.extract(data):
                param.param_type = "websocket"
                param.source = "websocket"
                yield param


# ── gRPC Metadata Extractor ─────────────────────────────────────────────────────


class GRPCExtractor(BaseExtractor):
    """
    Extracts gRPC-Web / gRPC metadata from HTTP headers and trailers.
    """

    extractor_name = "grpc"

    GRPC_RESERVED_HEADERS = {
        "grpc-timeout",
        "grpc-encoding",
        "grpc-accept-encoding",
        "grpc-status",
        "grpc-message",
        "grpc-status-details-bin",
        "content-type",
        "te",
        "grpc-trace-bin",
    }

    def extract(
        self, headers: dict[str, str]
    ) -> Generator[ExtractedParameter, None, None]:
        ct = headers.get("content-type", headers.get("Content-Type", ""))
        if "grpc" not in ct.lower():
            return

        for name, value in headers.items():
            lname = name.lower()
            if lname in self.GRPC_RESERVED_HEADERS:
                continue
            confidence = 0.9 if lname.endswith("-bin") else 0.8
            yield self._make_param(
                name,
                value,
                "grpc_metadata",
                "grpc_header",
                confidence=confidence,
                extra={"binary": lname.endswith("-bin")},
            )


# ── Mobile API Extractor ────────────────────────────────────────────────────────


class MobileAPIExtractor(BaseExtractor):
    """
    Detects mobile-app-specific API parameters: device IDs, app versions,
    platform identifiers, push tokens commonly sent by iOS/Android clients.
    """

    extractor_name = "mobile_api"

    MOBILE_HEADER_PATTERNS = re.compile(
        r"(x-device-id|x-app-version|x-platform|x-os-version|x-client-version|"
        r"x-device-model|x-push-token|x-app-build|x-installation-id|"
        r"x-advertising-id|x-idfa|x-idfv|user-agent)",
        re.IGNORECASE,
    )

    MOBILE_BODY_FIELDS = re.compile(
        r"(device_id|push_token|fcm_token|apns_token|device_model|"
        r"os_version|app_version|build_number|advertising_id|idfa|idfv|"
        r"platform)",
        re.IGNORECASE,
    )

    def extract(self, data: dict | str) -> Generator[ExtractedParameter, None, None]:
        if isinstance(data, dict):
            for name, value in data.items():
                if self.MOBILE_HEADER_PATTERNS.search(
                    name
                ) or self.MOBILE_BODY_FIELDS.search(name):
                    is_id = "id" in name.lower() or "token" in name.lower()
                    yield self._make_param(
                        name,
                        value,
                        "mobile_api",
                        "mobile_header_or_body",
                        confidence=0.85,
                        extra={"is_device_identifier": is_id},
                    )


# ── Custom / OpenAPI Extractor ─────────────────────────────────────────────────


class OpenAPIExtractor(BaseExtractor):
    """Extracts parameters from OpenAPI/Swagger spec."""

    extractor_name = "openapi"

    def extract(self, spec: dict) -> Generator[ExtractedParameter, None, None]:
        paths = spec.get("paths", {})
        for path, path_item in paths.items():
            for method, operation in path_item.items():
                if method not in ("get", "post", "put", "patch", "delete"):
                    continue
                params = operation.get("parameters", [])
                for param in params:
                    name = param.get("name", "")
                    loc = param.get("in", "query")  # query, path, header, cookie
                    required = param.get("required", False)
                    schema = param.get("schema", {})

                    p = self._make_param(
                        name,
                        schema.get("example"),
                        f"openapi_{loc}",
                        "openapi_spec",
                        confidence=1.0,
                        extra={"openapi_in": loc, "schema": schema},
                    )
                    p.is_required = required
                    yield p

                # Request body
                req_body = operation.get("requestBody", {})
                for media_type, media_obj in req_body.get("content", {}).items():
                    body_schema = media_obj.get("schema", {})
                    for prop_name, prop_schema in body_schema.get(
                        "properties", {}
                    ).items():
                        yield self._make_param(
                            prop_name,
                            prop_schema.get("example"),
                            "openapi",
                            "openapi_request_body",
                            extra={"media_type": media_type, "schema": prop_schema},
                        )


# ── Extraction Orchestrator ────────────────────────────────────────────────────


class ExtractionOrchestrator:
    """Routes request data to appropriate extractors and deduplicates results."""

    def __init__(self, endpoint: str, method: str = "GET"):
        self.endpoint = endpoint
        self.method = method
        self._seen: set[str] = set()
        self._params: list[ExtractedParameter] = []

    def process_request(
        self,
        url: str,
        headers: dict,
        cookies: dict,
        body: str | None,
        content_type: str = "",
    ) -> list[ExtractedParameter]:
        """Full request analysis pipeline."""

        # URL parameters
        for p in URLExtractor(self.endpoint, self.method).extract(url):
            self._add(p)

        # Headers
        for p in HeaderExtractor(self.endpoint, self.method).extract(headers):
            self._add(p)

        # Cookies
        for p in CookieExtractor(self.endpoint, self.method).extract(cookies):
            self._add(p)

        # Body parsing
        if body:
            ct = content_type.lower()

            if "application/json" in ct:
                for p in JSONExtractor(self.endpoint, self.method).extract(body):
                    self._add(p)

            elif "application/x-www-form-urlencoded" in ct:
                for p in FormExtractor(self.endpoint, self.method).extract(body):
                    self._add(p)

            elif (
                "text/xml" in ct or "application/xml" in ct or "application/soap" in ct
            ):
                if "<soap" in body.lower() or "Envelope" in body:
                    for p in SOAPExtractor(self.endpoint, self.method).extract(body):
                        self._add(p)
                else:
                    for p in XMLExtractor(self.endpoint, self.method).extract(body):
                        self._add(p)

            elif "application/graphql" in ct:
                for p in GraphQLExtractor(self.endpoint, self.method).extract(body):
                    self._add(p)

            # Detect JWT in Authorization header
            auth = headers.get("Authorization", headers.get("authorization", ""))
            if auth.startswith("Bearer "):
                token = auth[7:]
                for p in JWTExtractor(self.endpoint, self.method).extract(token):
                    self._add(p)

        # gRPC metadata (content-type: application/grpc*)
        for p in GRPCExtractor(self.endpoint, self.method).extract(headers):
            self._add(p)

        # Mobile API indicators in headers
        for p in MobileAPIExtractor(self.endpoint, self.method).extract(headers):
            self._add(p)

        return self._params

    def process_response_html(self, html: str) -> list[ExtractedParameter]:
        """Extract hidden fields from response HTML."""
        new_params = []
        for p in HiddenFieldExtractor(self.endpoint, self.method).extract(html):
            added = self._add(p)
            if added:
                new_params.append(p)
        return new_params

    def process_websocket(
        self, message: str, direction: str = "send"
    ) -> list[ExtractedParameter]:
        new_params = []
        for p in WebSocketExtractor(self.endpoint, self.method).extract(message):
            p.extra["ws_direction"] = direction
            added = self._add(p)
            if added:
                new_params.append(p)
        return new_params

    def _add(self, param: ExtractedParameter) -> bool:
        sig = param.signature()
        if sig in self._seen:
            # Update frequency
            for existing in self._params:
                if existing.signature() == sig:
                    existing.last_seen = datetime.utcnow()
                    break
            return False
        self._seen.add(sig)
        self._params.append(param)
        return True

    @property
    def results(self) -> list[ExtractedParameter]:
        return self._params
