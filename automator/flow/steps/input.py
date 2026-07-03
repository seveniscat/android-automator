"""input 步骤:输入文本。"""

from __future__ import annotations

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("input")
def step_input(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """
    YAML 用法:
        - input: { text: "hello" }
        - input: { text: "${username}", clear: true }
        - input:
            into: { resource_id: "com.x/.edit_user" }   # 先点击目标输入框
            text: "alice"
    """
    text = params.get("text", "")
    clear = bool(params.get("clear", False))

    # 可选先点击某输入框
    into = params.get("into")
    if into:
        actions.click_by(
            resource_id=into.get("resource_id"),
            text=into.get("text"),
            text_contains=into.get("text_contains"),
            content_desc=into.get("content_desc"),
            xpath=into.get("xpath"),
            timeout=float(into.get("timeout", 5.0)),
        )

    a = actions.input_text(str(text), clear=clear)
    return StepResult(
        step_name=params.get("_name", "input"),
        step_type="input",
        success=a.success,
        duration_ms=a.duration_ms,
        detail=a.target,
    )
