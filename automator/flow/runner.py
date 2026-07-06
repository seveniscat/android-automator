"""Flow 运行器。

逐步执行 Flow.steps,每步:
    1. 渲染 ${var} 插值
    2. 调用对应 step 函数
    3. 采集截图(可配)
    4. 记录 StepResult

失败处理:
    - on_failure=abort    → 整个流程终止,FlowResult.success=False
    - on_failure=continue → 跳过继续
    - retries > 0         → 失败后重试
"""

from __future__ import annotations

import time
from typing import Optional

from ..action.u2_actions import U2Actions
from ..config import settings
from ..device.base import Device
from ..device.manager import get_device_manager
from ..logging import logger
from ..perception.screenshot import ScreenshotPerception
from .base import Flow, FlowResult, StepResult
from .context import FlowContext
from .steps import get_step


class FlowRunner:
    """流程运行器。

    Args:
        device: 已连接的 Device(不传则从 DeviceManager 获取)
        perception: 感知器(默认截图感知),None 则不截图
        humanize: 是否开启人类化时延
    """

    def __init__(
        self,
        device: Optional[Device] = None,
        perception: Optional[ScreenshotPerception] = None,
        humanize: bool = True,
        capture_per_step: bool = True,
        device_serial: Optional[str] = None,
    ) -> None:
        self._device_arg = device
        self._device_serial = device_serial
        self.perception = perception
        self.humanize = humanize
        self.capture_per_step = capture_per_step

    def _resolve_device(self) -> Device:
        if self._device_arg is not None:
            return self._device_arg
        return get_device_manager().get_device(self._device_serial)

    def run(
        self,
        flow: Flow,
        variables: Optional[dict] = None,
        on_step: Optional[callable] = None,
    ) -> FlowResult:
        """执行流程。

        Args:
            flow: Flow 对象
            variables: 运行期变量(覆盖 flow.variables)
            on_step: 每步完成后的回调 (step_index, step, result) -> None
        """
        device = self._resolve_device()
        actions = U2Actions(device, humanize=self.humanize)
        ctx = FlowContext(variables={**flow.variables, **(variables or {})})
        perception = self.perception or ScreenshotPerception()

        logger.info(f"▶ 开始执行流程: {flow.name} ({len(flow.steps)} 步)")
        t0 = time.perf_counter()
        results: list[StepResult] = []
        flow_error: Optional[str] = None

        for i, step in enumerate(flow.steps):
            step_t0 = time.perf_counter()
            # 1. 插值
            params = ctx.render(step.params)
            params["_name"] = step.name

            # 2. 截图(执行前快照,便于排错)
            screenshot_path: Optional[str] = None
            if self.capture_per_step:
                try:
                    state = perception.perceive(device)
                    screenshot_path = state.screenshot_path
                except Exception as e:
                    logger.debug(f"步骤 {step.name} 截图失败: {e}")

            # 3. 执行(含重试)
            result = self._exec_step(step, actions, device, ctx, params)
            result.screenshot_path = screenshot_path
            results.append(result)

            logger.info(
                f"  [{i + 1}/{len(flow.steps)}] {step.name} "
                f"({'✓' if result.success else '✗'}) {result.detail or ''}"
            )
            if on_step:
                try:
                    on_step(i, step, result)
                except Exception as e:
                    logger.warning(f"on_step 回调异常: {e}")

            # 4. 失败处理
            if not result.success:
                if step.on_failure == "continue":
                    continue
                flow_error = result.error or f"步骤 {step.name} 失败"
                break

        duration_ms = int((time.perf_counter() - t0) * 1000)
        success = flow_error is None
        logger.info(
            f"■ 流程结束: {flow.name} "
            f"({'成功' if success else '失败'}) {duration_ms}ms"
        )
        return FlowResult(
            success=success,
            steps=results,
            duration_ms=duration_ms,
            error=flow_error,
            data=dict(ctx.extracted),
        )

    # ---- 内部 ----
    def _exec_step(
        self, step, actions, device, ctx, params
    ) -> StepResult:
        fn = get_step(step.type)
        attempts = step.retries + 1
        last: Optional[StepResult] = None
        for attempt in range(attempts):
            try:
                result = fn(actions, device, ctx, params)
                if result.success:
                    return result
                last = result
                if attempt < attempts - 1:
                    logger.debug(
                        f"步骤 {step.name} 第 {attempt + 1} 次失败,重试..."
                    )
                    time.sleep(0.5 * (attempt + 1))
            except Exception as e:
                logger.error(f"步骤 {step.name} 异常: {e}")
                last = StepResult(
                    step_name=step.name,
                    step_type=step.type,
                    success=False,
                    error=f"{type(e).__name__}: {e}",
                )
                if attempt < attempts - 1:
                    time.sleep(0.5 * (attempt + 1))
        return last or StepResult(
            step_name=step.name,
            step_type=step.type,
            success=False,
            error="未知错误",
        )
