"""
ParamX Hunter - Parameters API Endpoints
Advanced search, filtering, export, and tagging
"""

import csv
import io
import json
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user, require_roles
from backend.database.models import Parameter, RiskLevel, User
from backend.database.session import get_db

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────


class ParameterResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    endpoint_id: uuid.UUID
    name: str
    value: str | None
    param_type: str
    source: str
    method: str | None
    risk_level: str
    risk_tags: list[str]
    is_sensitive: bool
    is_hidden: bool
    is_required: bool | None
    confidence_score: float
    frequency: int
    data_type: str | None
    example_values: list[str]
    tags: list[str]
    extra: dict
    first_seen: str
    last_seen: str

    class Config:
        from_attributes = True


class ParameterUpdateRequest(BaseModel):
    risk_level: RiskLevel | None = None
    tags: list[str] | None = None
    is_sensitive: bool | None = None
    notes: str | None = None


class ParameterListResponse(BaseModel):
    items: list[ParameterResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class ParameterStats(BaseModel):
    total: int
    unique_names: int
    sensitive_count: int
    hidden_count: int
    by_type: dict[str, int]
    by_risk: dict[str, int]
    by_source: dict[str, int]
    top_names: list[dict]


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.get("/", response_model=ParameterListResponse)
async def list_parameters(
    scan_id: uuid.UUID | None = Query(None),
    endpoint_id: uuid.UUID | None = Query(None),
    search: str | None = Query(None, description="Search by name or value"),
    param_type: list[str] | None = Query(None),
    risk_level: list[str] | None = Query(None),
    source: str | None = Query(None),
    is_sensitive: bool | None = Query(None),
    is_hidden: bool | None = Query(None),
    tags: list[str] | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
    sort_by: str = Query(
        "first_seen",
        enum=["name", "first_seen", "last_seen", "frequency", "risk_level"],
    ),
    sort_dir: str = Query("desc", enum=["asc", "desc"]),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List parameters with advanced filtering.
    Supports multi-value filters for type and risk level.
    """
    conditions = []

    if scan_id:
        conditions.append(Parameter.scan_id == scan_id)
    if endpoint_id:
        conditions.append(Parameter.endpoint_id == endpoint_id)
    if search:
        conditions.append(
            or_(
                Parameter.name.ilike(f"%{search}%"),
                Parameter.value.ilike(f"%{search}%"),
            )
        )
    if param_type:
        conditions.append(Parameter.param_type.in_(param_type))
    if risk_level:
        conditions.append(Parameter.risk_level.in_(risk_level))
    if source:
        conditions.append(Parameter.source == source)
    if is_sensitive is not None:
        conditions.append(Parameter.is_sensitive == is_sensitive)
    if is_hidden is not None:
        conditions.append(Parameter.is_hidden == is_hidden)
    if tags:
        for tag in tags:
            conditions.append(Parameter.tags.contains([tag]))

    # Count query
    count_stmt = select(func.count()).select_from(Parameter)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar_one()

    # Sort
    sort_col = getattr(Parameter, sort_by, Parameter.first_seen)
    order = sort_col.desc() if sort_dir == "desc" else sort_col.asc()

    # Data query
    stmt = select(Parameter)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(order).offset((page - 1) * per_page).limit(per_page)

    result = await db.execute(stmt)
    params = result.scalars().all()

    return ParameterListResponse(
        items=[_to_response(p) for p in params],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=(total + per_page - 1) // per_page,
    )


@router.get("/stats", response_model=ParameterStats)
async def get_parameter_stats(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate statistics for parameters in a scan."""
    # Total
    total = (
        await db.execute(select(func.count()).where(Parameter.scan_id == scan_id))
    ).scalar_one()

    # Unique names
    unique_names = (
        await db.execute(
            select(func.count(func.distinct(Parameter.name))).where(
                Parameter.scan_id == scan_id
            )
        )
    ).scalar_one()

    # Sensitive
    sensitive = (
        await db.execute(
            select(func.count()).where(
                and_(Parameter.scan_id == scan_id, Parameter.is_sensitive)
            )
        )
    ).scalar_one()

    # Hidden
    hidden = (
        await db.execute(
            select(func.count()).where(
                and_(Parameter.scan_id == scan_id, Parameter.is_hidden)
            )
        )
    ).scalar_one()

    # By type
    type_counts = (
        await db.execute(
            select(Parameter.param_type, func.count())
            .where(Parameter.scan_id == scan_id)
            .group_by(Parameter.param_type)
        )
    ).all()

    # By risk
    risk_counts = (
        await db.execute(
            select(Parameter.risk_level, func.count())
            .where(Parameter.scan_id == scan_id)
            .group_by(Parameter.risk_level)
        )
    ).all()

    # By source
    source_counts = (
        await db.execute(
            select(Parameter.source, func.count())
            .where(Parameter.scan_id == scan_id)
            .group_by(Parameter.source)
        )
    ).all()

    # Top names
    top_names_result = (
        await db.execute(
            select(Parameter.name, func.count().label("count"))
            .where(Parameter.scan_id == scan_id)
            .group_by(Parameter.name)
            .order_by(func.count().desc())
            .limit(20)
        )
    ).all()

    return ParameterStats(
        total=total,
        unique_names=unique_names,
        sensitive_count=sensitive,
        hidden_count=hidden,
        by_type={str(t): c for t, c in type_counts},
        by_risk={str(r): c for r, c in risk_counts},
        by_source={str(s): c for s, c in source_counts},
        top_names=[{"name": n, "count": c} for n, c in top_names_result],
    )


@router.get("/{param_id}", response_model=ParameterResponse)
async def get_parameter(
    param_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Parameter).where(Parameter.id == param_id))
    param = result.scalar_one_or_none()
    if not param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    return _to_response(param)


@router.patch("/{param_id}", response_model=ParameterResponse)
async def update_parameter(
    param_id: uuid.UUID,
    body: ParameterUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager", "analyst"])),
):
    result = await db.execute(select(Parameter).where(Parameter.id == param_id))
    param = result.scalar_one_or_none()
    if not param:
        raise HTTPException(status_code=404, detail="Parameter not found")

    if body.risk_level is not None:
        param.risk_level = body.risk_level
    if body.tags is not None:
        param.tags = body.tags
    if body.is_sensitive is not None:
        param.is_sensitive = body.is_sensitive
    if body.notes is not None:
        param.extra["notes"] = body.notes

    await db.commit()
    await db.refresh(param)
    return _to_response(param)


@router.delete("/{param_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_parameter(
    param_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager"])),
):
    result = await db.execute(select(Parameter).where(Parameter.id == param_id))
    param = result.scalar_one_or_none()
    if not param:
        raise HTTPException(status_code=404, detail="Parameter not found")
    await db.delete(param)
    await db.commit()


@router.get("/export/csv")
async def export_csv(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export parameters as CSV."""
    stmt = (
        select(Parameter).where(Parameter.scan_id == scan_id).order_by(Parameter.name)
    )
    result = await db.execute(stmt)
    params = result.scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Name",
            "Type",
            "Source",
            "Method",
            "Value",
            "Risk Level",
            "Risk Tags",
            "Sensitive",
            "Hidden",
            "Confidence",
            "Frequency",
            "First Seen",
            "Last Seen",
        ]
    )
    for p in params:
        writer.writerow(
            [
                p.name,
                p.param_type,
                p.source,
                p.method or "",
                (p.value or "")[:200],
                p.risk_level,
                ",".join(p.risk_tags),
                p.is_sensitive,
                p.is_hidden,
                round(p.confidence_score, 2),
                p.frequency,
                p.first_seen.isoformat(),
                p.last_seen.isoformat(),
            ]
        )

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=parameters_{scan_id}.csv"
        },
    )


@router.get("/export/json")
async def export_json(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Export parameters as JSON."""
    stmt = select(Parameter).where(Parameter.scan_id == scan_id)
    result = await db.execute(stmt)
    params = result.scalars().all()

    data = {
        "scan_id": str(scan_id),
        "total": len(params),
        "parameters": [_to_response(p).model_dump() for p in params],
    }

    return StreamingResponse(
        iter([json.dumps(data, indent=2, default=str)]),
        media_type="application/json",
        headers={
            "Content-Disposition": f"attachment; filename=parameters_{scan_id}.json"
        },
    )


# ── Helper ─────────────────────────────────────────────────────────────────────


def _to_response(p: Parameter) -> ParameterResponse:
    return ParameterResponse(
        id=p.id,
        scan_id=p.scan_id,
        endpoint_id=p.endpoint_id,
        name=p.name,
        value=p.value,
        param_type=str(p.param_type),
        source=p.source,
        method=str(p.method) if p.method else None,
        risk_level=str(p.risk_level),
        risk_tags=p.risk_tags or [],
        is_sensitive=p.is_sensitive,
        is_hidden=p.is_hidden,
        is_required=p.is_required,
        confidence_score=p.confidence_score,
        frequency=p.frequency,
        data_type=p.data_type,
        example_values=p.example_values or [],
        tags=p.tags or [],
        extra=p.extra or {},
        first_seen=p.first_seen.isoformat(),
        last_seen=p.last_seen.isoformat(),
    )
