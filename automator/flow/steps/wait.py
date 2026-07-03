"""wait 步骤:等待元素出现或等待固定时长。"""

from __future__ import annotations

import time

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("wait")
def step_wait(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """
    YAML 用法:
        - wait: { seconds: 2 }                          # 固定等待
        - wait: { resource_id: "com.x/.btn", timeout: 5 }   # 等元素出现
        - wait: { text: "加载完成" }
        - wait: { text_contains: "成功" }
        - wait: { content_desc: "商品列表", timeout: 8 }     # Flutter/自绘 UI 用
        - wait: { xpath: "//node[@text='OK']" }
    """
    seconds = params.get("seconds")
    if seconds is not None:
        t0 = time.perf_counter()
        time.sleep(float(seconds))
        return StepResult(
            step_name=params.get("_name", "wait"),
            step_type="wait",
            success=True,
            duration_ms=int((time.perf_counter() - t0) * 1000),
            detail=f"sleep {seconds}s",
        )

    timeout = float(params.get("timeout", 5.0))
    t0 = time.perf_counter()
    ok = device.wait_exists(
        resource_id=params.get("resource_id"),
        text=params.get("text"),
        text_contains=params.get("text_contains"),
        content_desc=params.get("content_desc"),
        xpath=params.get("xpath"),
        timeout=timeout,
    )
    ms = int((time.perf_counter() - t0) * 1000)
    return StepResult(
        step_name=params.get("_name", "wait"),
        step_type="wait",
        success=ok,
        duration_ms=ms,
        detail="元素出现" if ok else f"等待超时({timeout}s)",
        error=None if ok else "等待元素超时",
    )
