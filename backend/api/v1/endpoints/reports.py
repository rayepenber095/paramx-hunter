"""
ParamX Hunter - Reports API
Generate PDF, HTML, JSON, and Excel reports for scans.
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from backend.auth.dependencies import get_current_user
from backend.config import settings
from backend.database.models import (
    Endpoint, Parameter, Scan, Target, User, RiskLevel
)
from backend.database.session import get_db
from backend.reporting.generators import (
    generate_pdf_report,
    generate_html_report,
    generate_excel_report,
)

router = APIRouter()

os.makedirs(settings.REPORTS_DIR, exist_ok=True)


class ReportRequest(BaseModel):
    scan_id: uuid.UUID
    format: str = "pdf"   # pdf | html | json | excel
    include_values: bool = False
    include_low_risk: bool = True
    title: str | None = None


class ReportJob(BaseModel):
    job_id: str
    scan_id: str
    format: str
    status: str
    download_url: str | None = None
    created_at: str


@router.post("/generate", response_model=ReportJob, status_code=202)
async def generate_report(
    body: ReportRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Kick off async report generation."""
    result = await db.execute(select(Scan).where(Scan.id == body.scan_id))
    scan = result.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")

    job_id = str(uuid.uuid4())
    background_tasks.add_task(
        _run_report_job,
        job_id=job_id,
        scan_id=str(body.scan_id),
        fmt=body.format,
        include_values=body.include_values,
        include_low_risk=body.include_low_risk,
        title=body.title or scan.name,
    )

    return ReportJob(
        job_id=job_id,
        scan_id=str(body.scan_id),
        format=body.format,
        status="generating",
        created_at=datetime.utcnow().isoformat(),
    )


@router.get("/download/{job_id}")
async def download_report(job_id: str):
    """Download a generated report by job ID."""
    # Search for the file
    for ext in ("pdf", "html", "json", "xlsx"):
        path = Path(settings.REPORTS_DIR) / f"{job_id}.{ext}"
        if path.exists():
            media_types = {
                "pdf": "application/pdf",
                "html": "text/html",
                "json": "application/json",
                "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            }
            return FileResponse(
                str(path),
                media_type=media_types[ext],
                filename=f"paramx_report_{job_id}.{ext}",
            )
    raise HTTPException(404, "Report not found or still generating")


@router.get("/quick-json/{scan_id}")
async def quick_json_report(
    scan_id: uuid.UUID,
    include_values: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Stream a JSON report directly without file generation."""
    scan_res = await db.execute(select(Scan).where(Scan.id == scan_id))
    scan = scan_res.scalar_one_or_none()
    if not scan:
        raise HTTPException(404, "Scan not found")

    params_res = await db.execute(
        select(Parameter).where(Parameter.scan_id == scan_id).order_by(Parameter.name)
    )
    params = params_res.scalars().all()

    eps_res = await db.execute(
        select(Endpoint).where(Endpoint.scan_id == scan_id)
    )
    endpoints = eps_res.scalars().all()

    report = {
        "report_generated_at": datetime.utcnow().isoformat(),
        "scan": {
            "id": str(scan.id),
            "name": scan.name,
            "status": str(scan.status),
            "total_requests": scan.total_requests,
            "total_endpoints": scan.total_endpoints,
            "total_parameters": scan.total_parameters,
            "unique_parameters": scan.unique_parameters,
            "started_at": scan.started_at.isoformat() if scan.started_at else None,
            "completed_at": scan.completed_at.isoformat() if scan.completed_at else None,
        },
        "summary": {
            "total_endpoints": len(endpoints),
            "total_parameters": len(params),
            "sensitive_parameters": sum(1 for p in params if p.is_sensitive),
            "hidden_parameters": sum(1 for p in params if p.is_hidden),
            "by_risk": {},
            "by_type": {},
        },
        "endpoints": [
            {
                "url": ep.url,
                "method": str(ep.method),
                "status_code": ep.status_code,
                "is_api": ep.is_api,
                "is_graphql": ep.is_graphql,
                "is_websocket": ep.is_websocket,
                "framework": ep.framework_detected,
            }
            for ep in endpoints
        ],
        "parameters": [
            {
                "name": p.name,
                **({"value": p.value} if include_values else {}),
                "type": str(p.param_type),
                "source": p.source,
                "risk_level": str(p.risk_level),
                "risk_tags": p.risk_tags,
                "is_sensitive": p.is_sensitive,
                "is_hidden": p.is_hidden,
                "frequency": p.frequency,
                "endpoint": str(p.endpoint_id),
            }
            for p in params
        ],
    }

    # Fill summary
    for p in params:
        risk = str(p.risk_level)
        ptype = str(p.param_type)
        report["summary"]["by_risk"][risk] = report["summary"]["by_risk"].get(risk, 0) + 1
        report["summary"]["by_type"][ptype] = report["summary"]["by_type"].get(ptype, 0) + 1

    return StreamingResponse(
        iter([json.dumps(report, indent=2, default=str)]),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename=report_{scan_id}.json"},
    )


async def _run_report_job(
    job_id: str,
    scan_id: str,
    fmt: str,
    include_values: bool,
    include_low_risk: bool,
    title: str,
):
    """Background task that builds the report file."""
    from backend.database.session import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            output_path = str(Path(settings.REPORTS_DIR) / f"{job_id}.{fmt}")
            if fmt == "pdf":
                await generate_pdf_report(db, scan_id, output_path, title, include_values)
            elif fmt == "html":
                await generate_html_report(db, scan_id, output_path, title, include_values)
            elif fmt == "excel":
                await generate_excel_report(db, scan_id, output_path, include_values)
        except Exception as e:
            import structlog
            structlog.get_logger().error("report_generation_failed", job_id=job_id, error=str(e))
