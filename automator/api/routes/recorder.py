"""录制控制路由。

录制状态由进程级 `Recorder` 单例承载(见 automator.recorder),暂存内存、
不落库;最终生成的 YAML 通过已有的 `POST /api/flows` 保存为 Flow。

交互流程:
    1. POST /start  → 开启录制(清空旧步骤)
    2. 在 Playground 操作(点击/滑动/输入…)→ 自动埋点翻译成 YAML 步骤
    3. GET  /state  → 前端轮询,展示已录步骤
    4. GET  /yaml   → 预览生成的 YAML
    5. POST /stop   → 停止(保留已录步骤,可继续预览/保存)
    6. 前端把 YAML 提交到 /api/flows 即可保存
"""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from ...recorder import get_recorder

router = APIRouter(prefix="/api/recorder", tags=["recorder"])


class StartRequest(BaseModel):
    """开始录制请求。"""

    name: str = Field(default="", description="流程名(留空则自动生成带时间戳的名称)")


@router.post("/start")
async def start(req: StartRequest):
    """开始录制(清空旧步骤)。"""
    rec = get_recorder()
    rec.start(req.name)
    return rec.snapshot()


@router.post("/stop")
async def stop():
    """停止录制,返回当前步骤数(保留步骤供预览/保存)。"""
    rec = get_recorder()
    count = rec.stop()
    snap = rec.snapshot()
    return {"active": False, "step_count": count, "name": snap["name"], "started_at": snap["started_at"]}


@router.post("/reset")
async def reset():
    """清空已录步骤并停止。"""
    rec = get_recorder()
    rec.reset()
    return {"ok": True, "active": False, "step_count": 0}


@router.get("/state")
async def state():
    """当前录制状态 + 已录步骤(前端轮询刷新)。"""
    return get_recorder().snapshot()


@router.delete("/step/{index}")
async def remove_step(index: int):
    """删除指定下标的已录步骤。"""
    ok = get_recorder().remove_step(index)
    return {"ok": ok, "step_count": len(get_recorder().steps)}


@router.get("/yaml")
async def yaml(name: str = Query(default="", description="流程名(留空用录制名)")):
    """预览生成的 YAML 文本(不保存)。"""
    return {"yaml": get_recorder().to_yaml(name), "name": name or get_recorder().name}
