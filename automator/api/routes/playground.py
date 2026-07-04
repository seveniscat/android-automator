"""Playground 路由 —— 即时执行单个设备动作,不落库,供 webui 探索/调试。

设计:
    - 一个统一端点 POST /api/playground/action,body 携带 {action, ...params},
      分派到 U2Actions 对应方法,同步执行(asyncio.to_thread 包装阻塞调用)。
    - humanize 默认关闭,体验即时。
    - 返回 Action(name/target/success/detail/duration_ms) + 触发一次截图的时间戳,
      供前端刷新画面。
    - 不写 task/run 表,纯探索性。
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ...action.u2_actions import U2Actions
from ...device.exceptions import DeviceError, DeviceNotFoundError
from ...device.manager import DeviceManager
from ..deps import get_dm

router = APIRouter(prefix="/api/playground", tags=["playground"])

# 支持的动作白名单(与 U2Actions 方法一一对应)
_ACTION_METHODS = {
    "click", "click_by", "swipe", "swipe_direction",
    "input_text", "press", "start_app", "stop_app",
}


class ActionRequest(BaseModel):
    """单动作请求。

    action: 动作类型,见 _ACTION_METHODS。
    params: 该动作的参数(透传给 U2Actions 对应方法)。
    """

    action: str = Field(..., description="动作类型")
    params: dict = Field(default_factory=dict, description="动作参数")


class ActionResult(BaseModel):
    """单动作响应(不落库)。"""

    action: str
    target: str = ""
    success: bool = True
    detail: str = ""
    duration_ms: int = 0
    shot_at: int = 0  # 截图时间戳,前端据此刷新画面


def _build_actions(dm: DeviceManager, humanize: bool = False) -> U2Actions:
    """获取设备并构造 U2Actions(playground 默认关 humanize)。"""
    dev = dm.get_device()
    return U2Actions(device=dev, humanize=humanize)


def _dispatch(actions: U2Actions, action: str, params: dict):
    """同步执行单个动作,返回 Action。"""
    if action not in _ACTION_METHODS:
        raise ValueError(f"不支持的动作: {action!r},可选: {sorted(_ACTION_METHODS)}")
    fn = getattr(actions, action)
    t0 = time.perf_counter()
    result = fn(**params)
    # result 是 Action dataclass;补一个总耗时(含方法内部延迟)
    result.duration_ms = result.duration_ms or int((time.perf_counter() - t0) * 1000)
    return result


@router.post("/action")
async def run_action(req: ActionRequest, dm: DeviceManager = Depends(get_dm)):
    """即时执行一个设备动作并返回结果(不落库)。"""
    try:
        actions = _build_actions(dm, humanize=False)
        result = await asyncio.to_thread(_dispatch, actions, req.action, req.params)
    except DeviceNotFoundError as e:
        raise HTTPException(status_code=503, detail=f"设备未连接: {e}") from e
    except (DeviceError, ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"执行失败: {e}") from e

    return ActionResult(
        action=result.name,
        target=result.target,
        success=result.success,
        detail=result.detail,
        duration_ms=result.duration_ms,
        shot_at=int(time.time() * 1000),
    )


@router.get("/actions")
async def list_actions():
    """列出 playground 支持的动作类型及参数说明(供前端渲染表单)。"""
    return {
        "actions": [
            {
                "name": "click",
                "label": "点击坐标",
                "params": {"x": "int", "y": "int"},
                "hint": "直接点击屏幕坐标 (x, y)",
            },
            {
                "name": "click_by",
                "label": "点击元素",
                "params": {
                    "resource_id": "str?", "text": "str?", "text_contains": "str?",
                    "content_desc": "str?", "xpath": "str?", "timeout": "float?",
                },
                "hint": "按定位器查找并点击(任选其一)",
            },
            {
                "name": "swipe_direction",
                "label": "方向滑动",
                "params": {"direction": "up|down|left|right", "scale": "float?"},
                "hint": "按方向滑动,scale 控制幅度(默认 0.5)",
            },
            {
                "name": "swipe",
                "label": "坐标滑动",
                "params": {"x1": "int", "y1": "int", "x2": "int", "y2": "int", "duration": "float?"},
                "hint": "从 (x1,y1) 滑到 (x2,y2)",
            },
            {
                "name": "input_text",
                "label": "输入文本",
                "params": {"text": "str", "clear": "bool?"},
                "hint": "在当前焦点输入框输入文本",
            },
            {
                "name": "press",
                "label": "系统按键",
                "params": {"key": "back|home|menu|recent|enter|delete|search|volume_up|volume_down|power"},
                "hint": "按下系统按键",
            },
            {
                "name": "start_app",
                "label": "启动应用",
                "params": {"package": "str", "activity": "str?"},
                "hint": "通过包名启动应用",
            },
            {
                "name": "stop_app",
                "label": "停止应用",
                "params": {"package": "str"},
                "hint": "停止指定应用",
            },
        ]
    }
