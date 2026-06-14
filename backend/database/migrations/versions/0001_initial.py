"""Initial schema - ParamX Hunter

Revision ID: 0001_initial
Revises:
Create Date: 2026-06-12

Creates all core tables: users, projects, targets, scans, endpoints,
parameters, requests, cookies, graphql, websocket_messages, audit_logs.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Enums ───────────────────────────────────────────────────────────────────
    user_role = postgresql.ENUM("admin", "manager", "analyst", "viewer", name="userrole")
    scan_status = postgresql.ENUM("pending", "running", "paused", "completed", "failed", "cancelled", name="scanstatus")
    http_method = postgresql.ENUM("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS", "TRACE", name="httpmethod")
    risk_level = postgresql.ENUM("info", "low", "medium", "high", "critical", name="risklevel")

    user_role.create(op.get_bind(), checkfirst=True)
    scan_status.create(op.get_bind(), checkfirst=True)
    http_method.create(op.get_bind(), checkfirst=True)
    risk_level.create(op.get_bind(), checkfirst=True)

    # ── users ───────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("username", sa.String(100), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_superuser", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_email", "users", ["email"])
    op.create_index("ix_users_username", "users", ["username"])

    # ── projects ────────────────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("settings", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_projects_owner_id", "projects", ["owner_id"])

    # ── targets ─────────────────────────────────────────────────────────────────
    op.create_table(
        "targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("scope_urls", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("excluded_urls", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("headers", postgresql.JSONB, server_default="{}"),
        sa.Column("cookies", postgresql.JSONB, server_default="{}"),
        sa.Column("auth_config", postgresql.JSONB, server_default="{}"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_targets_project_domain", "targets", ["project_id", "domain"])

    # ── scans ───────────────────────────────────────────────────────────────────
    op.create_table(
        "scans",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id"), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("targets.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", scan_status, nullable=False, server_default="pending"),
        sa.Column("config", postgresql.JSONB, server_default="{}"),
        sa.Column("total_requests", sa.Integer, server_default="0"),
        sa.Column("total_endpoints", sa.Integer, server_default="0"),
        sa.Column("total_parameters", sa.Integer, server_default="0"),
        sa.Column("unique_parameters", sa.Integer, server_default="0"),
        sa.Column("crawl_depth", sa.Integer, server_default="0"),
        sa.Column("progress_percent", sa.Float, server_default="0.0"),
        sa.Column("queue_size", sa.Integer, server_default="0"),
        sa.Column("resume_token", sa.String(512), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_scans_project_status", "scans", ["project_id", "status"])
    op.create_index("ix_scans_target_id", "scans", ["target_id"])

    # ── endpoints ───────────────────────────────────────────────────────────────
    op.create_table(
        "endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("normalized_url", sa.String(2048), nullable=False),
        sa.Column("path", sa.String(1024), nullable=False),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("method", http_method, server_default="GET"),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("content_type", sa.String(255), nullable=True),
        sa.Column("response_size", sa.BigInteger, nullable=True),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("is_api", sa.Boolean, server_default="false"),
        sa.Column("is_graphql", sa.Boolean, server_default="false"),
        sa.Column("is_websocket", sa.Boolean, server_default="false"),
        sa.Column("is_rest", sa.Boolean, server_default="false"),
        sa.Column("framework_detected", sa.String(100), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_endpoints_scan_domain", "endpoints", ["scan_id", "domain"])
    op.create_index("ix_endpoints_normalized_url", "endpoints", ["normalized_url"])
    op.create_index("ix_endpoints_path", "endpoints", ["path"])
    op.create_index("ix_endpoints_is_api", "endpoints", ["is_api"])

    # ── parameters ──────────────────────────────────────────────────────────────
    op.create_table(
        "parameters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id"), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("param_type", sa.String(64), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("method", http_method, nullable=True),
        sa.Column("risk_level", risk_level, server_default="info"),
        sa.Column("risk_tags", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("is_sensitive", sa.Boolean, server_default="false"),
        sa.Column("is_hidden", sa.Boolean, server_default="false"),
        sa.Column("is_required", sa.Boolean, nullable=True),
        sa.Column("confidence_score", sa.Float, server_default="1.0"),
        sa.Column("frequency", sa.Integer, server_default="1"),
        sa.Column("data_type", sa.String(100), nullable=True),
        sa.Column("example_values", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("schema", postgresql.JSONB, nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.String), server_default="{}"),
        sa.Column("extra", postgresql.JSONB, server_default="{}"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scan_id", "endpoint_id", "name", "param_type", "source", name="uq_param_signature"),
    )
    op.create_index("ix_params_scan_type", "parameters", ["scan_id", "param_type"])
    op.create_index("ix_params_endpoint_name", "parameters", ["endpoint_id", "name"])
    op.create_index("ix_params_name", "parameters", ["name"])
    op.create_index("ix_params_risk", "parameters", ["scan_id", "risk_level"])
    op.create_index("ix_params_sensitive", "parameters", ["scan_id", "is_sensitive"])
    op.create_index("ix_params_hidden", "parameters", ["scan_id", "is_hidden"])

    # Trigram indexes for fast text search
    op.execute("CREATE INDEX ix_parameters_name_trgm ON parameters USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX ix_endpoints_path_trgm ON endpoints USING gin (path gin_trgm_ops)")

    # ── requests ────────────────────────────────────────────────────────────────
    op.create_table(
        "requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id"), nullable=True),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("method", http_method, server_default="GET"),
        sa.Column("headers", postgresql.JSONB, server_default="{}"),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("cookies", postgresql.JSONB, server_default="{}"),
        sa.Column("status_code", sa.Integer, nullable=True),
        sa.Column("response_headers", postgresql.JSONB, server_default="{}"),
        sa.Column("response_body", sa.Text, nullable=True),
        sa.Column("response_time_ms", sa.Integer, nullable=True),
        sa.Column("referrer", sa.String(2048), nullable=True),
        sa.Column("fingerprint", sa.String(64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_requests_scan_timestamp", "requests", ["scan_id", "timestamp"])
    op.create_index("ix_requests_endpoint_id", "requests", ["endpoint_id"])
    op.create_index("ix_requests_fingerprint", "requests", ["fingerprint"])

    # ── cookies ─────────────────────────────────────────────────────────────────
    op.create_table(
        "cookies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("name", sa.String(512), nullable=False),
        sa.Column("value", sa.Text, nullable=True),
        sa.Column("domain", sa.String(255), nullable=False),
        sa.Column("path", sa.String(512), server_default="/"),
        sa.Column("secure", sa.Boolean, server_default="false"),
        sa.Column("http_only", sa.Boolean, server_default="false"),
        sa.Column("same_site", sa.String(20), nullable=True),
        sa.Column("is_session", sa.Boolean, server_default="false"),
        sa.Column("is_tracking", sa.Boolean, server_default="false"),
        sa.Column("expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("scan_id", "name", "domain", name="uq_cookie"),
    )
    op.create_index("ix_cookies_scan_domain", "cookies", ["scan_id", "domain"])

    # ── graphql ─────────────────────────────────────────────────────────────────
    op.create_table(
        "graphql",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id"), nullable=False),
        sa.Column("operation_type", sa.String(20), nullable=False),
        sa.Column("operation_name", sa.String(255), nullable=True),
        sa.Column("query", sa.Text, nullable=True),
        sa.Column("variables", postgresql.JSONB, server_default="{}"),
        sa.Column("schema_fragment", postgresql.JSONB, nullable=True),
        sa.Column("introspection_available", sa.Boolean, server_default="false"),
        sa.Column("first_seen", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_graphql_scan_operation", "graphql", ["scan_id", "operation_type"])

    # ── websocket_messages ──────────────────────────────────────────────────────
    op.create_table(
        "websocket_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scan_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("scans.id"), nullable=False),
        sa.Column("endpoint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("endpoints.id"), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("message_type", sa.String(20), server_default="text"),
        sa.Column("raw_message", sa.Text, nullable=True),
        sa.Column("parsed_data", postgresql.JSONB, nullable=True),
        sa.Column("parameters", postgresql.JSONB, server_default="[]"),
        sa.Column("schema", postgresql.JSONB, nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_ws_scan_endpoint", "websocket_messages", ["scan_id", "endpoint_id"])

    # ── audit_logs ──────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(512), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_user_timestamp", "audit_logs", ["user_id", "timestamp"])
    op.create_index("ix_audit_action", "audit_logs", ["action"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("websocket_messages")
    op.drop_table("graphql")
    op.drop_table("cookies")
    op.drop_table("requests")
    op.drop_table("parameters")
    op.drop_table("endpoints")
    op.drop_table("scans")
    op.drop_table("targets")
    op.drop_table("projects")
    op.drop_table("users")

    sa.Enum(name="risklevel").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="httpmethod").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="scanstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="userrole").drop(op.get_bind(), checkfirst=True)
