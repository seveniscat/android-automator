"""assert 步骤:断言元素存在/不存在,失败则中断流程。"""

from __future__ import annotations

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("assert")
def step_assert(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """
    YAML 用法:
        - assert: { exists: { text: "登录" } }    # 该元素必须存在
        - assert: { not_exists: { resource_id: "com.x/.btn" } }
        - assert: { exists: { content_desc: "商品列表" } }   # Flutter 用
        - assert: { text: "成功" }                # 简写:exists
    """
    target = params.get("exists") or params.get("exists_")
    not_target = params.get("not_exists")

    # 简写形式
    if target is None and not_target is None:
        target = {k: v for k, v in params.items() if not k.startswith("_")}

    timeout = float(params.get("timeout", 3.0))

    def _exists(spec: dict) -> bool:
        return device.wait_exists(
            resource_id=spec.get("resource_id"),
            text=spec.get("text"),
            text_contains=spec.get("text_contains"),
            content_desc=spec.get("content_desc"),
            xpath=spec.get("xpath"),
            timeout=timeout,
        )

    if target is not None:
        ok = _exists(target)
        return StepResult(
            step_name=params.get("_name", "assert"),
            step_type="assert",
            success=ok,
            detail=f"应存在: {target}",
            error=None if ok else "断言失败: 元素不存在",
        )

    ok = not _exists(not_target)
    return StepResult(
        step_name=params.get("_name", "assert"),
        step_type="assert",
        success=ok,
        detail=f"应不存在: {not_target}",
        error=None if ok else "断言失败: 元素仍存在",
    )
