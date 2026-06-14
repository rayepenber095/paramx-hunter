"""
ParamX Hunter - Database Models
PostgreSQL + SQLAlchemy 2.0 async ORM
Optimized for millions of parameters with proper indexing
"""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    BigInteger, Boolean, DateTime, Enum as SAEnum, Float, ForeignKey,
    Index, Integer, String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(AsyncAttrs, DeclarativeBase):
    pass


# ── Enums ─────────────────────────────────────────────────────────────────────

class UserRole(str, Enum):
    ADMIN = "admin"
    MANAGER = "manager"
    ANALYST = "analyst"
    VIEWER = "viewer"


class ScanStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ParameterType(str, Enum):
    # URL-based
    URL_QUERY = "url_query"
    PATH = "path"
    FRAGMENT = "fragment"
    # Body
    FORM_URLENCODED = "form_urlencoded"
    MULTIPART_FORM = "multipart_form"
    JSON_BODY = "json_body"
    JSON_NESTED = "json_nested"
    XML = "xml"
    SOAP = "soap"
    # GraphQL
    GRAPHQL_VARIABLE = "graphql_variable"
    GRAPHQL_QUERY = "graphql_query"
    # Headers
    HEADER_STANDARD = "header_standard"
    HEADER_AUTH = "header_auth"
    HEADER_CUSTOM = "header_custom"
    # Cookies/Session
    COOKIE = "cookie"
    SESSION = "session"
    JWT_CLAIM = "jwt_claim"
    # Forms
    HIDDEN_FIELD = "hidden_field"
    CSRF_TOKEN = "csrf_token"
    ANTI_FORGERY = "anti_forgery"
    # Special
    METHOD_OVERRIDE = "method_override"
    PAGINATION = "pagination"
    SORTING = "sorting"
    SEARCH = "search"
    FILTER = "filter"
    REDIRECT = "redirect"
    RETURN_URL = "return_url"
    LOCALE = "locale"
    LANGUAGE = "language"
    VERSION = "version"
    FEATURE_FLAG = "feature_flag"
    DEBUG = "debug"
    FILE_PATH = "file_path"
    API_KEY = "api_key"
    # Realtime
    WEBSOCKET = "websocket"
    SSE = "sse"
    # API types
    MOBILE_API = "mobile_api"
    REST = "rest"
    GRPC_METADATA = "grpc_metadata"
    OPENAPI = "openapi"


class RiskLevel(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"
    HEAD = "HEAD"
    OPTIONS = "OPTIONS"
    TRACE = "TRACE"


# ── Models ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.ANALYST)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    projects = relationship("Project", back_populates="owner")
    audit_logs = relationship("AuditLog", back_populates="user")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    settings: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now(), server_default=func.now())

    owner = relationship("User", back_populates="projects")
    targets = relationship("Target", back_populates="project")
    scans = relationship("Scan", back_populates="project")

    __table_args__ = (
        Index("ix_projects_owner_id", "owner_id"),
    )


class Target(Base):
    __tablename__ = "targets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    scope_urls: Mapped[list] = mapped_column(ARRAY(String), default=list)
    excluded_urls: Mapped[list] = mapped_column(ARRAY(String), default=list)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    cookies: Mapped[dict] = mapped_column(JSONB, default=dict)
    auth_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="targets")
    scans = relationship("Scan", back_populates="target")

    __table_args__ = (
        Index("ix_targets_project_domain", "project_id", "domain"),
    )


class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("targets.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(SAEnum(ScanStatus), default=ScanStatus.PENDING)
    config: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Stats
    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_endpoints: Mapped[int] = mapped_column(Integer, default=0)
    total_parameters: Mapped[int] = mapped_column(Integer, default=0)
    unique_parameters: Mapped[int] = mapped_column(Integer, default=0)
    crawl_depth: Mapped[int] = mapped_column(Integer, default=0)
    # Progress tracking
    progress_percent: Mapped[float] = mapped_column(Float, default=0.0)
    queue_size: Mapped[int] = mapped_column(Integer, default=0)
    resume_token: Mapped[str | None] = mapped_column(String(512), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Timestamps
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    project = relationship("Project", back_populates="scans")
    target = relationship("Target", back_populates="scans")
    endpoints = relationship("Endpoint", back_populates="scan")
    requests = relationship("Request", back_populates="scan")

    __table_args__ = (
        Index("ix_scans_project_status", "project_id", "status"),
        Index("ix_scans_target_id", "target_id"),
    )


class Endpoint(Base):
    __tablename__ = "endpoints"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    normalized_url: Mapped[str] = mapped_column(String(2048), nullable=False)  # params stripped
    path: Mapped[str] = mapped_column(String(1024), nullable=False)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[HttpMethod] = mapped_column(SAEnum(HttpMethod), default=HttpMethod.GET)
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    response_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # API detection
    is_api: Mapped[bool] = mapped_column(Boolean, default=False)
    is_graphql: Mapped[bool] = mapped_column(Boolean, default=False)
    is_websocket: Mapped[bool] = mapped_column(Boolean, default=False)
    is_rest: Mapped[bool] = mapped_column(Boolean, default=False)
    framework_detected: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # Metadata
    tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("Scan", back_populates="endpoints")
    parameters = relationship("Parameter", back_populates="endpoint")
    requests = relationship("Request", back_populates="endpoint")

    __table_args__ = (
        Index("ix_endpoints_scan_domain", "scan_id", "domain"),
        Index("ix_endpoints_normalized_url", "normalized_url"),
        Index("ix_endpoints_path", "path"),
        Index("ix_endpoints_is_api", "is_api"),
    )


class Parameter(Base):
    __tablename__ = "parameters"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id"), nullable=False)
    # Core fields
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    param_type: Mapped[ParameterType] = mapped_column(SAEnum(ParameterType), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "url", "header", "body"
    method: Mapped[HttpMethod | None] = mapped_column(SAEnum(HttpMethod), nullable=True)
    # Classification
    risk_level: Mapped[RiskLevel] = mapped_column(SAEnum(RiskLevel), default=RiskLevel.INFO)
    risk_tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    is_sensitive: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_required: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    # Confidence & frequency
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)
    frequency: Mapped[int] = mapped_column(Integer, default=1)
    # Metadata
    data_type: Mapped[str | None] = mapped_column(String(100), nullable=True)  # string, int, bool, etc.
    example_values: Mapped[list] = mapped_column(ARRAY(String), default=list)
    schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list] = mapped_column(ARRAY(String), default=list)
    extra: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Timestamps
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("Scan")
    endpoint = relationship("Endpoint", back_populates="parameters")

    __table_args__ = (
        Index("ix_params_scan_type", "scan_id", "param_type"),
        Index("ix_params_endpoint_name", "endpoint_id", "name"),
        Index("ix_params_name", "name"),
        Index("ix_params_risk", "scan_id", "risk_level"),
        Index("ix_params_sensitive", "scan_id", "is_sensitive"),
        Index("ix_params_hidden", "scan_id", "is_hidden"),
        UniqueConstraint("scan_id", "endpoint_id", "name", "param_type", "source", name="uq_param_signature"),
    )


class Request(Base):
    __tablename__ = "requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    endpoint_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id"), nullable=True)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    method: Mapped[HttpMethod] = mapped_column(SAEnum(HttpMethod), default=HttpMethod.GET)
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookies: Mapped[dict] = mapped_column(JSONB, default=dict)
    # Response
    status_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Meta
    referrer: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    scan = relationship("Scan", back_populates="requests")
    endpoint = relationship("Endpoint", back_populates="requests")

    __table_args__ = (
        Index("ix_requests_scan_timestamp", "scan_id", "timestamp"),
        Index("ix_requests_endpoint_id", "endpoint_id"),
        Index("ix_requests_fingerprint", "fingerprint"),
    )


class CookieRecord(Base):
    __tablename__ = "cookies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)
    value: Mapped[str | None] = mapped_column(Text, nullable=True)
    domain: Mapped[str] = mapped_column(String(255), nullable=False)
    path: Mapped[str] = mapped_column(String(512), default="/")
    secure: Mapped[bool] = mapped_column(Boolean, default=False)
    http_only: Mapped[bool] = mapped_column(Boolean, default=False)
    same_site: Mapped[str | None] = mapped_column(String(20), nullable=True)
    is_session: Mapped[bool] = mapped_column(Boolean, default=False)
    is_tracking: Mapped[bool] = mapped_column(Boolean, default=False)
    expires: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_cookies_scan_domain", "scan_id", "domain"),
        UniqueConstraint("scan_id", "name", "domain", name="uq_cookie"),
    )


class GraphQLRecord(Base):
    __tablename__ = "graphql"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id"), nullable=False)
    operation_type: Mapped[str] = mapped_column(String(20), nullable=False)  # query, mutation, subscription
    operation_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    query: Mapped[str | None] = mapped_column(Text, nullable=True)
    variables: Mapped[dict] = mapped_column(JSONB, default=dict)
    schema_fragment: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    introspection_available: Mapped[bool] = mapped_column(Boolean, default=False)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_graphql_scan_operation", "scan_id", "operation_type"),
    )


class WebSocketMessage(Base):
    __tablename__ = "websocket_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scans.id"), nullable=False)
    endpoint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("endpoints.id"), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # "send" or "receive"
    message_type: Mapped[str] = mapped_column(String(20), default="text")  # text, binary
    raw_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    parameters: Mapped[list] = mapped_column(JSONB, default=list)
    schema: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_ws_scan_endpoint", "scan_id", "endpoint_id"),
    )


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="audit_logs")

    __table_args__ = (
        Index("ix_audit_user_timestamp", "user_id", "timestamp"),
        Index("ix_audit_action", "action"),
    )
