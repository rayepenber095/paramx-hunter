"""
ParamX Hunter - Dashboard Stats API
"""

import uuid
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database.models import (
    Endpoint, Parameter, Scan, ScanStatus, User
)
from backend.database.session import get_db

router = APIRouter()


class DashboardStats(BaseModel):
    total_endpoints: int
    total_parameters: int
    unique_parameters: int
    hidden_parameters: int
    sensitive_parameters: int
    apis_discovered: int
    websockets_found: int
    active_scans: int
    total_scans: int
    risk_distribution: dict[str, int]
    param_type_distribution: dict[str, int]
    top_endpoints: list[dict]


@router.get("/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    project_id: uuid.UUID | None = Query(None),
    scan_id: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ep_cond = []
    param_cond = []
    scan_cond = []

    if scan_id:
        ep_cond.append(Endpoint.scan_id == scan_id)
        param_cond.append(Parameter.scan_id == scan_id)

    async def count(model, *conds):
        stmt = select(func.count()).select_from(model)
        if conds:
            stmt = stmt.where(and_(*conds))
        return (await db.execute(stmt)).scalar_one()

    total_endpoints = await count(Endpoint, *ep_cond)
    total_parameters = await count(Parameter, *param_cond)
    unique_params = (await db.execute(
        select(func.count(func.distinct(Parameter.name))).where(and_(*param_cond)) if param_cond
        else select(func.count(func.distinct(Parameter.name)))
    )).scalar_one()
    hidden = await count(Parameter, Parameter.is_hidden, *param_cond)
    sensitive = await count(Parameter, Parameter.is_sensitive, *param_cond)
    apis = await count(Endpoint, Endpoint.is_api, *ep_cond)
    websockets = await count(Endpoint, Endpoint.is_websocket, *ep_cond)
    active_scans = await count(Scan, Scan.status == ScanStatus.RUNNING, *scan_cond)
    total_scans = await count(Scan, *scan_cond)

    # Risk distribution
    risk_stmt = select(Parameter.risk_level, func.count()).group_by(Parameter.risk_level)
    if param_cond:
        risk_stmt = risk_stmt.where(and_(*param_cond))
    risk_rows = (await db.execute(risk_stmt)).all()
    risk_dist = {str(r): c for r, c in risk_rows}

    # Type distribution
    type_stmt = select(Parameter.param_type, func.count()).group_by(Parameter.param_type)
    if param_cond:
        type_stmt = type_stmt.where(and_(*param_cond))
    type_rows = (await db.execute(type_stmt)).all()
    type_dist = {str(t): c for t, c in type_rows}

    # Top endpoints by param count
    top_stmt = (
        select(Endpoint.path, func.count(Parameter.id).label("param_count"))
        .join(Parameter, Parameter.endpoint_id == Endpoint.id)
        .group_by(Endpoint.path)
        .order_by(func.count(Parameter.id).desc())
        .limit(10)
    )
    top_rows = (await db.execute(top_stmt)).all()
    top_endpoints = [{"endpoint": path, "param_count": cnt} for path, cnt in top_rows]

    return DashboardStats(
        total_endpoints=total_endpoints,
        total_parameters=total_parameters,
        unique_parameters=unique_params,
        hidden_parameters=hidden,
        sensitive_parameters=sensitive,
        apis_discovered=apis,
        websockets_found=websockets,
        active_scans=active_scans,
        total_scans=total_scans,
        risk_distribution=risk_dist,
        param_type_distribution=type_dist,
        top_endpoints=top_endpoints,
    )
