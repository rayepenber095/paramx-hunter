"""
ParamX Hunter - Unit Tests: Parameter Extraction Engine
"""

import json

from backend.core.extractors import (
    URLExtractor,
    HeaderExtractor,
    CookieExtractor,
    JSONExtractor,
    XMLExtractor,
    FormExtractor,
    HiddenFieldExtractor,
    JWTExtractor,
    GraphQLExtractor,
    ExtractionOrchestrator,
)

ENDPOINT = "https://example.com/api/v1/test"


# ── URL Extractor ──────────────────────────────────────────────────────────────

class TestURLExtractor:
    def test_query_params(self):
        url = "https://example.com/search?q=test&page=2&limit=50"
        params = list(URLExtractor(ENDPOINT).extract(url))
        names = {p.name for p in params}
        assert "q" in names
        assert "page" in names
        assert "limit" in names

    def test_pagination_classified(self):
        url = "https://example.com/api?page=1&limit=20"
        params = list(URLExtractor(ENDPOINT).extract(url))
        page_p = next(p for p in params if p.name == "page")
        assert page_p.param_type == "pagination"

    def test_redirect_classified(self):
        url = "https://example.com/login?redirect=https://evil.com"
        params = list(URLExtractor(ENDPOINT).extract(url))
        redir = next(p for p in params if p.name == "redirect")
        assert redir.param_type == "redirect"
        assert "open-redirect-candidate" in redir.risk_tags

    def test_fragment_params(self):
        url = "https://example.com/app#token=abc123&state=xyz"
        params = list(URLExtractor(ENDPOINT).extract(url))
        frag = [p for p in params if p.source == "url_fragment"]
        assert len(frag) >= 1

    def test_path_integer_param(self):
        url = "https://example.com/users/42/profile"
        params = list(URLExtractor(ENDPOINT).extract(url))
        path_params = [p for p in params if p.source == "url_path"]
        assert any(p.value == "42" for p in path_params)

    def test_empty_query(self):
        url = "https://example.com/page"
        params = list(URLExtractor(ENDPOINT).extract(url))
        assert len(params) == 0


# ── Header Extractor ───────────────────────────────────────────────────────────

class TestHeaderExtractor:
    def test_standard_header(self):
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        params = list(HeaderExtractor(ENDPOINT).extract(headers))
        assert any(p.param_type == "header_standard" for p in params)

    def test_auth_header(self):
        headers = {"Authorization": "Bearer eyJhbGciOiJSUzI1NiJ9..."}
        params = list(HeaderExtractor(ENDPOINT).extract(headers))
        auth_p = next(p for p in params if p.name == "Authorization")
        assert auth_p.param_type == "header_auth"

    def test_custom_header(self):
        headers = {"X-Correlation-Id": "abc-123", "X-Tenant-Id": "tenant42"}
        params = list(HeaderExtractor(ENDPOINT).extract(headers))
        assert all(p.param_type == "header_custom" for p in params)

    def test_api_key_header_sensitive(self):
        headers = {"x-api-key": "sk-live-123abc"}
        params = list(HeaderExtractor(ENDPOINT).extract(headers))
        assert params[0].is_sensitive is True


# ── Cookie Extractor ───────────────────────────────────────────────────────────

class TestCookieExtractor:
    def test_session_cookie(self):
        cookies = {"sessionid": "abc123xyz", "csrftoken": "xyz"}
        params = list(CookieExtractor(ENDPOINT).extract(cookies))
        session_p = next(p for p in params if p.name == "sessionid")
        assert session_p.param_type == "session"

    def test_regular_cookie(self):
        cookies = {"theme": "dark", "lang": "en"}
        params = list(CookieExtractor(ENDPOINT).extract(cookies))
        assert all(p.param_type == "cookie" for p in params)


# ── JSON Extractor ─────────────────────────────────────────────────────────────

class TestJSONExtractor:
    def test_flat_json(self):
        body = json.dumps({"username": "admin", "password": "secret"})
        params = list(JSONExtractor(ENDPOINT, "POST").extract(body))
        names = {p.name for p in params}
        assert "username" in names
        assert "password" in names

    def test_nested_json(self):
        body = json.dumps({"user": {"id": 1, "profile": {"name": "Ahmad"}}})
        params = list(JSONExtractor(ENDPOINT, "POST").extract(body))
        names = {p.name for p in params}
        assert "user.id" in names
        assert "user.profile.name" in names

    def test_sensitive_password(self):
        body = json.dumps({"email": "test@test.com", "password": "pass123"})
        params = list(JSONExtractor(ENDPOINT, "POST").extract(body))
        pwd = next(p for p in params if "password" in p.name)
        assert pwd.is_sensitive is True

    def test_invalid_json(self):
        params = list(JSONExtractor(ENDPOINT, "POST").extract("not json {{"))
        assert len(params) == 0

    def test_array_json(self):
        body = json.dumps([{"id": 1}, {"id": 2}])
        params = list(JSONExtractor(ENDPOINT, "POST").extract(body))
        assert any("id" in p.name for p in params)


# ── XML Extractor ──────────────────────────────────────────────────────────────

class TestXMLExtractor:
    def test_simple_xml(self):
        xml = "<request><username>admin</username><role>user</role></request>"
        params = list(XMLExtractor(ENDPOINT, "POST").extract(xml))
        names = {p.name for p in params}
        assert "request/username" in names
        assert "request/role" in names

    def test_xml_attributes(self):
        xml = '<user id="42" type="admin"><name>Ahmad</name></user>'
        params = list(XMLExtractor(ENDPOINT).extract(xml))
        names = {p.name for p in params}
        assert any("@id" in n for n in names)

    def test_malformed_xml(self):
        params = list(XMLExtractor(ENDPOINT).extract("<unclosed>"))
        assert len(params) == 0


# ── Form Extractor ─────────────────────────────────────────────────────────────

class TestFormExtractor:
    def test_url_encoded(self):
        body = "username=admin&password=secret&remember=1"
        params = list(FormExtractor(ENDPOINT, "POST").extract(body))
        names = {p.name for p in params}
        assert "username" in names and "password" in names

    def test_csrf_detected(self):
        body = "email=test@test.com&_csrf=abc123token&submit=1"
        params = list(FormExtractor(ENDPOINT, "POST").extract(body))
        csrf_p = next((p for p in params if p.name == "_csrf"), None)
        assert csrf_p is not None
        assert csrf_p.param_type == "csrf_token"


# ── Hidden Field Extractor ─────────────────────────────────────────────────────

class TestHiddenFieldExtractor:
    def test_detects_hidden_inputs(self):
        html = """
        <form>
          <input type="hidden" name="_token" value="abc123">
          <input type="hidden" name="return_url" value="/dashboard">
          <input type="text" name="username">
        </form>
        """
        params = list(HiddenFieldExtractor(ENDPOINT).extract(html))
        names = {p.name for p in params}
        assert "_token" in names
        assert "return_url" in names
        assert "username" not in names

    def test_no_hidden_fields(self):
        html = "<form><input type='text' name='q'></form>"
        params = list(HiddenFieldExtractor(ENDPOINT).extract(html))
        assert len(params) == 0


# ── JWT Extractor ──────────────────────────────────────────────────────────────

class TestJWTExtractor:
    # A real HS256 JWT: header.payload.sig
    SAMPLE_JWT = (
        "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        ".eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkFobWFkIiwicm9sZSI6ImFkbWluIiwiaWF0IjoxNTE2MjM5MDIyfQ"
        ".SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    )

    def test_extracts_claims(self):
        params = list(JWTExtractor(ENDPOINT).extract(self.SAMPLE_JWT))
        names = {p.name for p in params}
        assert "jwt.sub" in names
        assert "jwt.name" in names
        assert "jwt.role" in names

    def test_extracts_header(self):
        params = list(JWTExtractor(ENDPOINT).extract(self.SAMPLE_JWT))
        hdr_params = [p for p in params if "header" in p.source]
        assert any("alg" in p.name for p in hdr_params)

    def test_invalid_jwt(self):
        params = list(JWTExtractor(ENDPOINT).extract("not.a.jwt.at.all"))
        assert len(params) == 0


# ── GraphQL Extractor ──────────────────────────────────────────────────────────

class TestGraphQLExtractor:
    def test_variables_extracted(self):
        body = json.dumps({
            "query": "query GetUser($id: ID!, $role: String) { user(id: $id) { name } }",
            "variables": {"id": "42", "role": "admin"},
            "operationName": "GetUser",
        })
        params = list(GraphQLExtractor(ENDPOINT, "POST").extract(body))
        names = {p.name for p in params}
        assert "id" in names
        assert "role" in names

    def test_operation_name_extracted(self):
        body = json.dumps({
            "query": "mutation Login($email: String!, $password: String!) { login(email: $email) { token } }",
            "variables": {"email": "a@b.com", "password": "xxx"},
        })
        params = list(GraphQLExtractor(ENDPOINT, "POST").extract(body))
        assert any(p.param_type == "graphql_variable" for p in params)


# ── Orchestrator ───────────────────────────────────────────────────────────────

class TestExtractionOrchestrator:
    def test_full_request(self):
        orch = ExtractionOrchestrator("https://example.com/api/login", "POST")
        params = orch.process_request(
            url="https://example.com/api/login?ref=homepage",
            headers={
                "Content-Type": "application/json",
                "Authorization": "Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abc",
                "X-Forwarded-For": "1.2.3.4",
            },
            cookies={"sessionid": "sess_abc123"},
            body=json.dumps({"email": "a@b.com", "password": "pass"}),
            content_type="application/json",
        )
        names = {p.name for p in params}
        assert "ref" in names
        assert "email" in names
        assert "password" in names
        assert "sessionid" in names

    def test_deduplication(self):
        orch = ExtractionOrchestrator("https://example.com/api", "GET")
        # Process same URL twice
        orch.process_request("https://example.com/api?x=1", {}, {}, None)
        orch.process_request("https://example.com/api?x=1", {}, {}, None)
        x_params = [p for p in orch.results if p.name == "x"]
        assert len(x_params) == 1

    def test_hidden_fields_from_html(self):
        orch = ExtractionOrchestrator("https://example.com/form", "GET")
        orch.process_response_html(
            '<input type="hidden" name="_token" value="abc">'
        )
        assert any(p.name == "_token" for p in orch.results)
