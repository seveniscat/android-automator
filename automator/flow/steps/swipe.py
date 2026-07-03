"""swipe 步骤:滑动。"""

from __future__ import annotations

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("swipe")
def step_swipe(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """
    YAML 用法:
        - swipe: { direction: up }             # up/down/left/right
        - swipe: { direction: down, scale: 0.6 }
        - swipe: { x1: 500, y1: 1500, x2: 500, y2: 500, duration: 0.4 }
    """
    direction = params.get("direction")
    if direction:
        scale = float(params.get("scale", 0.5))
        a = actions.swipe_direction(direction, scale=scale)
    else:
        a = actions.swipe(
            int(params["x1"]), int(params["y1"]),
            int(params["x2"]), int(params["y2"]),
            duration=float(params.get("duration", 0.3)),
        )
    return StepResult(
        step_name=params.get("_name", "swipe"),
        step_type="swipe",
        success=a.success,
        duration_ms=a.duration_ms,
        detail=a.target,
    )
