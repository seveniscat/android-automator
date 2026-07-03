"""click 步骤:点击坐标或元素。"""

from __future__ import annotations

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("click")
def step_click(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """
    YAML 用法:
        - click: { x: 100, y: 200 }
        - click: { resource_id: "com.x/.btn" }
        - click: { text: "登录" }
        - click: { text_contains: "确认" }
        - click: { content_desc: "商品列表" }      # Flutter/自绘 UI 用
        - click: { xpath: "//node[@text='OK']" }
    """
    x = params.get("x")
    y = params.get("y")
    timeout = float(params.get("timeout", 5.0))

    if x is not None and y is not None:
        a = actions.click(int(x), int(y))
        return StepResult(
            step_name=params.get("_name", "click"),
            step_type="click",
            success=a.success,
            duration_ms=a.duration_ms,
            detail=a.target,
        )

    # 元素定位
    a = actions.click_by(
        resource_id=params.get("resource_id"),
        text=params.get("text"),
        text_contains=params.get("text_contains"),
        content_desc=params.get("content_desc"),
        xpath=params.get("xpath"),
        timeout=timeout,
    )
    return StepResult(
        step_name=params.get("_name", "click"),
        step_type="click",
        success=a.success,
        duration_ms=a.duration_ms,
        detail=a.target,
        error=None if a.success else f"元素未命中: {a.target}",
    )
