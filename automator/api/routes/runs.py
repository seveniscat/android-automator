"""运行记录路由。"""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from ...config import settings
from ...storage.repository import Repository
from ..deps import get_repo

router = APIRouter(prefix="/api/runs", tags=["runs"])


@router.get("")
async def list_runs(
    task_id: int | None = None,
    limit: int = 50,
    repo: Repository = Depends(get_repo),
):
    runs = repo.list_runs(task_id=task_id, limit=limit)
    return {
        "items": [
            {
                "id": r.id,
                "task_id": r.task_id,
                "status": r.status,
                "success": r.success,
                "duration_ms": r.duration_ms,
                "error": r.error,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            }
            for r in runs
        ]
    }


@router.get("/{run_id}")
async def get_run(run_id: int, repo: Repository = Depends(get_repo)):
    run = repo.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="运行不存在")
    steps = repo.get_step_results(run_id)
    return {
        "id": run.id,
        "task_id": run.task_id,
        "status": run.status,
        "success": run.success,
        "duration_ms": run.duration_ms,
        "error": run.error,
        "extracted_data": run.extracted_data,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "steps": [
            {
                "index": s.index,
                "step_name": s.step_name,
                "step_type": s.step_type,
                "success": s.success,
                "duration_ms": s.duration_ms,
                "screenshot_path": s.screenshot_path,
                "detail": s.detail,
                "error": s.error,
                "extracted": s.extracted,
            }
            for s in steps
        ],
    }


@router.get("/{run_id}/screenshot/{step_index}")
async def get_screenshot(run_id: int, step_index: int, repo: Repository = Depends(get_repo)):
    """获取某一步的截图。"""
    steps = repo.get_step_results(run_id)
    for s in steps:
        if s.index == step_index and s.screenshot_path:
            path = Path(s.screenshot_path)
            if path.exists():
                return FileResponse(str(path), media_type="image/png")
    raise HTTPException(status_code=404, detail="截图不存在")
