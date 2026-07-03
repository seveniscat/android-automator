"""任务路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ...flow.yaml_loader import parse_flow
from ...storage.repository import Repository
from ...task.executor import Executor
from ..deps import get_exec, get_repo

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


class TaskIn(BaseModel):
    """创建任务。

    方式 A:复用已保存的 flow → flow_id
    方式 B:直接传 yaml → flow_yaml
    """

    flow_id: Optional[int] = None
    flow_yaml: Optional[str] = None
    variables: dict = {}
    schedule: str = ""   # 预留:定时表达式,本期不解析


@router.get("")
async def list_tasks(repo: Repository = Depends(get_repo)):
    tasks = repo.list_tasks()
    return {
        "items": [
            {
                "id": t.id,
                "flow_id": t.flow_id,
                "flow_name": t.flow_name,
                "status": t.status,
                "device_serial": t.device_serial,
                "schedule": t.schedule,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tasks
        ]
    }


@router.post("")
async def create_task(body: TaskIn, repo: Repository = Depends(get_repo)):
    # 解析 flow yaml 与 name
    flow_yaml = ""
    flow_name = ""
    if body.flow_id:
        rec = repo.get_flow(body.flow_id)
        if not rec:
            raise HTTPException(status_code=404, detail="flow_id 不存在")
        flow_yaml = rec.yaml_content
        flow_name = rec.name
    elif body.flow_yaml:
        flow_yaml = body.flow_yaml
        try:
            parsed = parse_flow(flow_yaml)
            flow_name = parsed.name
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"流程解析失败: {e}")
    else:
        raise HTTPException(status_code=400, detail="必须提供 flow_id 或 flow_yaml")

    task = repo.create_task(
        flow_id=body.flow_id,
        flow_name=flow_name,
        flow_yaml=flow_yaml,
        variables=body.variables,
        schedule=body.schedule,
    )
    return {"id": task.id, "flow_name": flow_name, "status": task.status}


@router.get("/{task_id}")
async def get_task(task_id: int, repo: Repository = Depends(get_repo)):
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "id": task.id,
        "flow_id": task.flow_id,
        "flow_name": task.flow_name,
        "flow_yaml": task.flow_yaml,
        "variables": task.variables,
        "status": task.status,
        "schedule": task.schedule,
        "created_at": task.created_at.isoformat() if task.created_at else None,
    }


@router.post("/{task_id}/run")
async def run_task(
    task_id: int,
    repo: Repository = Depends(get_repo),
    exec_: Executor = Depends(get_exec),
):
    """立即执行任务(创建一次 run 并派发)。"""
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")

    run = repo.create_run(task_id)
    repo.update_task_status(task_id, "running")
    await exec_.submit_task(
        task_id=task_id,
        run_id=run.id,
        yaml=task.flow_yaml,
        variables=task.variables or {},
    )
    return {"task_id": task_id, "run_id": run.id, "status": "running"}


@router.delete("/{task_id}")
async def delete_task(task_id: int, repo: Repository = Depends(get_repo)):
    # 任务记录保留(用于审计),这里只置状态
    task = repo.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    repo.update_task_status(task_id, "cancelled")
    return {"ok": True}
