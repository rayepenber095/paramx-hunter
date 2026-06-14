"""
ParamX Hunter - API v1 Router
All REST endpoints
"""

from fastapi import APIRouter

from backend.api.v1.endpoints import auth, dashboard
from backend.api.v1.endpoints import endpoints as ep_router
from backend.api.v1.endpoints import parameters, projects, reports, scans, targets
from backend.api.v1.endpoints import websocket as ws_router

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
router.include_router(projects.router, prefix="/projects", tags=["Projects"])
router.include_router(targets.router, prefix="/targets", tags=["Targets"])
router.include_router(scans.router, prefix="/scans", tags=["Scans"])
router.include_router(parameters.router, prefix="/parameters", tags=["Parameters"])
router.include_router(ep_router.router, prefix="/endpoints", tags=["Endpoints"])
router.include_router(reports.router, prefix="/reports", tags=["Reports"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard"])
router.include_router(ws_router.router, prefix="/ws", tags=["WebSocket"])
