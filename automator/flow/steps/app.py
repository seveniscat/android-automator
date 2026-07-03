"""app 步骤:启动/停止应用。"""

from __future__ import annotations

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("start_app")
def step_start_app(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """
    YAML 用法:
        - start_app: { package: "com.tencent.mm" }
        - start_app: { package: "com.x", activity: ".MainActivity" }
    """
    package = params["package"]
    activity = params.get("activity")
    a = actions.start_app(package, activity)
    return StepResult(
        step_name=params.get("_name", "start_app"),
        step_type="start_app",
        success=a.success,
        duration_ms=a.duration_ms,
        detail=a.target,
    )


@register("stop_app")
def step_stop_app(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """YAML 用法: - stop_app: { package: "com.tencent.mm" }"""
    package = params["package"]
    a = actions.stop_app(package)
    return StepResult(
        step_name=params.get("_name", "stop_app"),
        step_type="stop_app",
        success=a.success,
        duration_ms=a.duration_ms,
        detail=a.target,
    )


@register("press")
def step_press(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """YAML 用法: - press: { key: back }   # back/home/menu/enter/..."""
    key = params["key"]
    a = actions.press(key)
    return StepResult(
        step_name=params.get("_name", "press"),
        step_type="press",
        success=a.success,
        duration_ms=a.duration_ms,
        detail=a.target,
    )
