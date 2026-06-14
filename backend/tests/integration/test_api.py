"""
ParamX Hunter - Integration Tests
Tests full HTTP API flow with an in-memory test database.
"""

import uuid
import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from backend.main import app
from backend.database.models import Base, User, UserRole
from backend.database.session import get_db
from backend.auth.dependencies import hash_password

# ── Test DB Setup ──────────────────────────────────────────────────────────────

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True, scope="function")
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_user():
    async with TestSession() as db:
        user = User(
            id=uuid.uuid4(),
            email="admin@paramx.io",
            username="admin",
            hashed_password=hash_password("AdminPass123!"),
            role=UserRole.ADMIN,
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        await db.commit()
        return user


@pytest_asyncio.fixture
async def auth_headers(client, admin_user):
    resp = await client.post("/api/v1/auth/token", data={
        "username": "admin@paramx.io",
        "password": "AdminPass123!",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ── Auth Tests ─────────────────────────────────────────────────────────────────

class TestAuth:
    @pytest.mark.asyncio
    async def test_login_success(self, client, admin_user):
        resp = await client.post("/api/v1/auth/token", data={
            "username": "admin@paramx.io",
            "password": "AdminPass123!",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_wrong_password(self, client, admin_user):
        resp = await client.post("/api/v1/auth/token", data={
            "username": "admin@paramx.io",
            "password": "wrongpassword",
        })
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_register(self, client):
        resp = await client.post("/api/v1/auth/register", json={
            "email": "analyst@paramx.io",
            "username": "analyst1",
            "password": "Analyst123!",
            "role": "analyst",
        })
        assert resp.status_code == 201
        assert resp.json()["email"] == "analyst@paramx.io"

    @pytest.mark.asyncio
    async def test_protected_endpoint_no_token(self, client):
        resp = await client.get("/api/v1/projects/")
        assert resp.status_code == 401


# ── Project Tests ──────────────────────────────────────────────────────────────

class TestProjects:
    @pytest.mark.asyncio
    async def test_create_project(self, client, auth_headers):
        resp = await client.post("/api/v1/projects/", json={
            "name": "Test Project",
            "description": "Integration test project",
        }, headers=auth_headers)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Test Project"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_list_projects(self, client, auth_headers):
        # Create two projects
        for i in range(2):
            await client.post("/api/v1/projects/", json={"name": f"Project {i}"},
                              headers=auth_headers)
        resp = await client.get("/api/v1/projects/", headers=auth_headers)
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_get_nonexistent_project(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/api/v1/projects/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404


# ── Target Tests ───────────────────────────────────────────────────────────────

class TestTargets:
    @pytest_asyncio.fixture
    async def project_id(self, client, auth_headers):
        resp = await client.post("/api/v1/projects/", json={"name": "TargetTestProj"},
                                 headers=auth_headers)
        return resp.json()["id"]

    @pytest.mark.asyncio
    async def test_create_target(self, client, auth_headers, project_id):
        resp = await client.post("/api/v1/targets/", json={
            "project_id": project_id,
            "url": "https://example.com",
            "scope_urls": ["https://example.com/api"],
        }, headers=auth_headers)
        assert resp.status_code == 201
        assert resp.json()["domain"] == "example.com"

    @pytest.mark.asyncio
    async def test_target_auth_config_masked(self, client, auth_headers, project_id):
        resp = await client.post("/api/v1/targets/", json={
            "project_id": project_id,
            "url": "https://example.com",
            "auth_config": {"api_key": "sk-secret-abc123"},
        }, headers=auth_headers)
        assert resp.status_code == 201
        # api_key value should be masked
        assert resp.json()["auth_config"]["api_key"] == "***"


# ── Parameter Tests ────────────────────────────────────────────────────────────

class TestParameters:
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
