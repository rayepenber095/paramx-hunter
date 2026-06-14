"""
ParamX Hunter - Targets API Endpoints
"""

import uuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user, require_roles
from backend.database.models import Target, Project, User
from backend.database.session import get_db

router = APIRouter()


class TargetCreate(BaseModel):
    project_id: uuid.UUID
    url: str = Field(..., description="Base URL of the target application")
    scope_urls: list[str] = Field(default_factory=list)
    excluded_urls: list[str] = Field(default_factory=list)
    headers: dict = Field(default_factory=dict, description="Custom request headers")
    cookies: dict = Field(default_factory=dict)
    auth_config: dict = Field(default_factory=dict)


class TargetResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    url: str
    domain: str
    scope_urls: list[str]
    excluded_urls: list[str]
    headers: dict
    cookies: dict
    auth_config: dict
    created_at: str

    class Config:
        from_attributes = True


def _extract_domain(url: str) -> str:
    from urllib.parse import urlparse
    return urlparse(url).netloc


@router.post("/", response_model=TargetResponse, status_code=201)
async def create_target(
    body: TargetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager", "analyst"])),
):
    proj = await db.execute(select(Project).where(Project.id == body.project_id))
    if not proj.scalar_one_or_none():
        raise HTTPException(404, "Project not found")

    target = Target(
        id=uuid.uuid4(),
        project_id=body.project_id,
        url=str(body.url),
        domain=_extract_domain(str(body.url)),
        scope_urls=body.scope_urls,
        excluded_urls=body.excluded_urls,
        headers=body.headers,
        cookies=body.cookies,
        auth_config=body.auth_config,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return _to_response(target)


@router.get("/", response_model=list[TargetResponse])
async def list_targets(
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Target)
    if project_id:
        stmt = stmt.where(Target.project_id == project_id)
    result = await db.execute(stmt.order_by(Target.created_at.desc()))
    return [_to_response(t) for t in result.scalars().all()]


@router.get("/{target_id}", response_model=TargetResponse)
async def get_target(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "Target not found")
    return _to_response(target)


@router.delete("/{target_id}", status_code=204)
async def delete_target(
    target_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager"])),
):
    result = await db.execute(select(Target).where(Target.id == target_id))
    target = result.scalar_one_or_none()
    if not target:
        raise HTTPException(404, "Target not found")
    await db.delete(target)
    await db.commit()


def _to_response(t: Target) -> TargetResponse:
    return TargetResponse(
        id=t.id,
        project_id=t.project_id,
        url=t.url,
        domain=t.domain,
        scope_urls=t.scope_urls or [],
        excluded_urls=t.excluded_urls or [],
        headers=t.headers or {},
        cookies=t.cookies or {},
        auth_config={k: "***" if "key" in k.lower() or "secret" in k.lower() else v
                     for k, v in (t.auth_config or {}).items()},
        created_at=t.created_at.isoformat(),
    )
