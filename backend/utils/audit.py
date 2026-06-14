"""
ParamX Hunter - Audit Logging
Records security-relevant actions (auth, scan lifecycle, exports, RBAC changes)
to the audit_logs table for compliance and forensics.
"""

import uuid
from typing import Any

import structlog
from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.models import AuditLog, User

logger = structlog.get_logger(__name__)


# ── Standard Action Names ──────────────────────────────────────────────────────

class AuditAction:
    LOGIN = "auth.login"
    LOGIN_FAILED = "auth.login_failed"
    LOGOUT = "auth.logout"
    REGISTER = "auth.register"
    PASSWORD_CHANGE = "auth.password_change"
    TOKEN_REFRESH = "auth.token_refresh"

    PROJECT_CREATE = "project.create"
    PROJECT_UPDATE = "project.update"
    PROJECT_DELETE = "project.delete"

    TARGET_CREATE = "target.create"
    TARGET_DELETE = "target.delete"

    SCAN_CREATE = "scan.create"
    SCAN_PAUSE = "scan.pause"
    SCAN_RESUME = "scan.resume"
    SCAN_CANCEL = "scan.cancel"
    SCAN_DELETE = "scan.delete"

    PARAMETER_UPDATE = "parameter.update"
    PARAMETER_DELETE = "parameter.delete"
    PARAMETER_EXPORT = "parameter.export"

    REPORT_GENERATE = "report.generate"
    REPORT_DOWNLOAD = "report.download"

    USER_ROLE_CHANGE = "user.role_change"
    USER_DEACTIVATE = "user.deactivate"


async def log_audit_event(
    db: AsyncSession,
    action: str,
    user: User | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
    request: Request | None = None,
    commit: bool = True,
) -> AuditLog:
    """
    Record an audit log entry. Call this for any security-relevant action.

    Example:
        await log_audit_event(
            db, AuditAction.SCAN_CREATE,
            user=current_user,
            resource_type="scan", resource_id=str(scan.id),
            details={"target_url": target.url},
            request=request,
        )
    """
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        # Honor X-Forwarded-For if behind a proxy
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            ip_address = forwarded.split(",")[0].strip()
        user_agent = request.headers.get("user-agent")

    entry = AuditLog(
        id=uuid.uuid4(),
        user_id=user.id if user else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    if commit:
        await db.commit()

    logger.info(
        "audit_event",
        action=action,
        user_id=str(user.id) if user else None,
        resource_type=resource_type,
        resource_id=resource_id,
        ip=ip_address,
    )

    return entry


# ── Query Helpers ──────────────────────────────────────────────────────────────

async def get_user_activity(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 100,
) -> list[AuditLog]:
    from sqlalchemy import select
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def get_resource_history(
    db: AsyncSession,
    resource_type: str,
    resource_id: str,
    limit: int = 50,
) -> list[AuditLog]:
    from sqlalchemy import select, and_
    result = await db.execute(
        select(AuditLog)
        .where(and_(
            AuditLog.resource_type == resource_type,
            AuditLog.resource_id == resource_id,
        ))
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
    )
    return list(result.scalars().all())
