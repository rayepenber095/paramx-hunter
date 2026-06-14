"""
ParamX Hunter - Endpoints API
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.database.models import Endpoint, Parameter, User
from backend.database.session import get_db

router = APIRouter()


class EndpointResponse(BaseModel):
    id: uuid.UUID
    scan_id: uuid.UUID
    url: str
    normalized_url: str
    path: str
    domain: str
    method: str
    status_code: int | None
    content_type: str | None
    response_size: int | None
    response_time_ms: int | None
    is_api: bool
    is_graphql: bool
    is_websocket: bool
    framework_detected: str | None
    tags: list[str]
    parameter_count: int = 0
    first_seen: str
    last_seen: str

    class Config:
        from_attributes = True


class EndpointListResponse(BaseModel):
    items: list[EndpointResponse]
    total: int
    page: int
    per_page: int


@router.get("/", response_model=EndpointListResponse)
async def list_endpoints(
    scan_id: uuid.UUID | None = None,
    domain: str | None = None,
    is_api: bool | None = None,
    is_graphql: bool | None = None,
    is_websocket: bool | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conditions = []
    if scan_id:
        conditions.append(Endpoint.scan_id == scan_id)
    if domain:
        conditions.append(Endpoint.domain.ilike(f"%{domain}%"))
    if is_api is not None:
        conditions.append(Endpoint.is_api == is_api)
    if is_graphql is not None:
        conditions.append(Endpoint.is_graphql == is_graphql)
    if is_websocket is not None:
        conditions.append(Endpoint.is_websocket == is_websocket)
    if search:
        conditions.append(Endpoint.path.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(Endpoint)
    if conditions:
        count_stmt = count_stmt.where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = select(Endpoint)
    if conditions:
        stmt = stmt.where(and_(*conditions))
    stmt = stmt.order_by(Endpoint.first_seen.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(stmt)
    endpoints = result.scalars().all()

    # Param counts per endpoint
    items = []
    for ep in endpoints:
        count_res = await db.execute(
            select(func.count()).where(Parameter.endpoint_id == ep.id)
        )
        param_count = count_res.scalar_one()
        r = EndpointResponse(
            id=ep.id,
            scan_id=ep.scan_id,
            url=ep.url,
            normalized_url=ep.normalized_url,
            path=ep.path,
            domain=ep.domain,
            method=str(ep.method),
            status_code=ep.status_code,
            content_type=ep.content_type,
            response_size=ep.response_size,
            response_time_ms=ep.response_time_ms,
            is_api=ep.is_api,
            is_graphql=ep.is_graphql,
            is_websocket=ep.is_websocket,
            framework_detected=ep.framework_detected,
            tags=ep.tags or [],
            parameter_count=param_count,
            first_seen=ep.first_seen.isoformat(),
            last_seen=ep.last_seen.isoformat(),
        )
        items.append(r)

    return EndpointListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{endpoint_id}", response_model=EndpointResponse)
async def get_endpoint(
    endpoint_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Endpoint).where(Endpoint.id == endpoint_id))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(404, "Endpoint not found")

    count_res = await db.execute(
        select(func.count()).where(Parameter.endpoint_id == ep.id)
    )
    param_count = count_res.scalar_one()

    return EndpointResponse(
        id=ep.id, scan_id=ep.scan_id, url=ep.url, normalized_url=ep.normalized_url,
        path=ep.path, domain=ep.domain, method=str(ep.method),
        status_code=ep.status_code, content_type=ep.content_type,
        response_size=ep.response_size, response_time_ms=ep.response_time_ms,
        is_api=ep.is_api, is_graphql=ep.is_graphql, is_websocket=ep.is_websocket,
        framework_detected=ep.framework_detected, tags=ep.tags or [],
        parameter_count=param_count,
        first_seen=ep.first_seen.isoformat(), last_seen=ep.last_seen.isoformat(),
    )
