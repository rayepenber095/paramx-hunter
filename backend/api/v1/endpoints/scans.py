"""
ParamX Hunter - Scans API Endpoints
Create, manage, pause, resume scans
"""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user, require_roles
from backend.database.models import Scan, ScanStatus, Target, User
from backend.database.session import get_db
from backend.workers.scan_worker import launch_scan, pause_scan, resume_scan, cancel_scan

router = APIRouter()


# ── Schemas ────────────────────────────────────────────────────────────────────

class ScanConfig(BaseModel):
    max_depth: int = Field(default=5, ge=1, le=20)
    max_requests: int = Field(default=50000, ge=100, le=500000)
    concurrency: int = Field(default=50, ge=1, le=200)
    request_delay_ms: int = Field(default=0, ge=0, le=5000)
    javascript_rendering: bool = True
    respect_robots_txt: bool = True
    crawl_subdomains: bool = False
    custom_headers: dict = Field(default_factory=dict)
    cookies: dict = Field(default_factory=dict)
    scope_regex: list[str] = Field(default_factory=list)
    excluded_urls: list[str] = Field(default_factory=list)


class ScanCreateRequest(BaseModel):
    target_id: uuid.UUID
    name: str = Field(..., min_length=1, max_length=255)
    config: ScanConfig = Field(default_factory=ScanConfig)


class ScanResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    target_id: uuid.UUID
    name: str
    status: str
    config: dict
    total_requests: int
    total_endpoints: int
    total_parameters: int
    unique_parameters: int
    progress_percent: float
    queue_size: int
    error_message: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str

    class Config:
        from_attributes = True


class ScanListResponse(BaseModel):
    items: list[ScanResponse]
    total: int


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post("/", response_model=ScanResponse, status_code=201)
async def create_scan(
    body: ScanCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager", "analyst"])),
):
    """Create and immediately launch a new scan."""
    # Validate target
    target_result = await db.execute(select(Target).where(Target.id == body.target_id))
    target = target_result.scalar_one_or_none()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")

    scan = Scan(
        id=uuid.uuid4(),
        project_id=target.project_id,
        target_id=body.target_id,
        name=body.name,
        status=ScanStatus.PENDING,
        config=body.config.model_dump(),
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    # Launch in background
    background_tasks.add_task(launch_scan, str(scan.id))

    return _to_response(scan)


@router.get("/", response_model=ScanListResponse)
async def list_scans(
    project_id: uuid.UUID | None = None,
    status: ScanStatus | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = select(Scan)
    if project_id:
        stmt = stmt.where(Scan.project_id == project_id)
    if status:
        stmt = stmt.where(Scan.status == status)
    stmt = stmt.order_by(Scan.created_at.desc())

    result = await db.execute(stmt)
    scans = result.scalars().all()

    return ScanListResponse(
        items=[_to_response(s) for s in scans],
        total=len(scans),
    )


@router.get("/{scan_id}", response_model=ScanResponse)
async def get_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    scan = await _get_or_404(db, scan_id)
    return _to_response(scan)


@router.post("/{scan_id}/pause", response_model=ScanResponse)
async def pause_scan_endpoint(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager", "analyst"])),
):
    scan = await _get_or_404(db, scan_id)
    if scan.status != ScanStatus.RUNNING:
        raise HTTPException(400, "Scan is not running")
    await pause_scan(str(scan_id))
    scan.status = ScanStatus.PAUSED
    await db.commit()
    await db.refresh(scan)
    return _to_response(scan)


@router.post("/{scan_id}/resume", response_model=ScanResponse)
async def resume_scan_endpoint(
    scan_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager", "analyst"])),
):
    scan = await _get_or_404(db, scan_id)
    if scan.status != ScanStatus.PAUSED:
        raise HTTPException(400, "Scan is not paused")
    background_tasks.add_task(resume_scan, str(scan_id))
    scan.status = ScanStatus.RUNNING
    await db.commit()
    await db.refresh(scan)
    return _to_response(scan)


@router.post("/{scan_id}/cancel", response_model=ScanResponse)
async def cancel_scan_endpoint(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager"])),
):
    scan = await _get_or_404(db, scan_id)
    if scan.status in (ScanStatus.COMPLETED, ScanStatus.CANCELLED):
        raise HTTPException(400, f"Cannot cancel scan with status: {scan.status}")
    await cancel_scan(str(scan_id))
    scan.status = ScanStatus.CANCELLED
    await db.commit()
    await db.refresh(scan)
    return _to_response(scan)


@router.delete("/{scan_id}", status_code=204)
async def delete_scan(
    scan_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_roles(["admin", "manager"])),
):
    scan = await _get_or_404(db, scan_id)
    await db.delete(scan)
    await db.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_or_404(db: AsyncSession, scan_id: uuid.UUID) -> Scan:
    result = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")
    return scan


def _to_response(s: Scan) -> ScanResponse:
    return ScanResponse(
        id=s.id,
        project_id=s.project_id,
        target_id=s.target_id,
        name=s.name,
        status=str(s.status),
        config=s.config or {},
        total_requests=s.total_requests,
        total_endpoints=s.total_endpoints,
        total_parameters=s.total_parameters,
        unique_parameters=s.unique_parameters,
        progress_percent=s.progress_percent,
        queue_size=s.queue_size,
        error_message=s.error_message,
        started_at=s.started_at.isoformat() if s.started_at else None,
        completed_at=s.completed_at.isoformat() if s.completed_at else None,
        created_at=s.created_at.isoformat(),
    )
