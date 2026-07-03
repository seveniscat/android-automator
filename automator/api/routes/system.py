"""系统/健康检查路由。"""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import APIRouter

from ...config import PROJECT_ROOT, settings
from ...flow.steps import list_steps
from ...storage.db import init_db

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


@router.get("/env")
async def env_info():
    """环境信息(用于排错)。"""
    return {
        "db_url": settings.db_url,
        "screenshot_dir": str(settings.screenshot_dir),
        "device_serial": settings.device_serial or "(auto)",
        "atx_port": settings.atx_port,
        "executor_workers": settings.executor_workers,
        "available_steps": list_steps(),
        "is_packaged": False,
    }


@router.post("/init-db")
async def init_db_route():
    """强制初始化数据库表。"""
    init_db()
    return {"ok": True, "msg": "数据库表已创建"}


@router.get("/disk-usage")
async def disk_usage():
    """data 目录占用。"""
    data_dir = PROJECT_ROOT / "data"
    usage = 0
    if data_dir.exists():
        for p in data_dir.rglob("*"):
            if p.is_file():
                usage += p.stat().st_size
    return {"bytes": usage, "human": _human(usage)}


def _human(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
