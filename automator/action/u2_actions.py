"""uiautomator2 动作层实现。

在 Device 原语之上叠加:
  - 人类化随机时延(降低反爬/反辅助检测)
  - 人类化滑动(贝塞尔轨迹可选,本期用线性 + 抖动)
  - 统一的 Action 结果(便于审计)
"""

from __future__ import annotations

import random
import time
from typing import Optional

from ..device.base import Device
from ..logging import logger
from .base import Action, ActionLayer


class U2Actions(ActionLayer):
    """基于 Device 的高层动作封装。"""

    def __init__(
        self,
        device: Device,
        humanize: bool = True,
        click_delay: tuple[float, float] = (0.05, 0.25),
    ) -> None:
        self.device = device
        self.humanize = humanize
        self.click_delay = click_delay

    # ---- 内部 ----
    def _delay(self) -> None:
        if self.humanize:
            lo, hi = self.click_delay
            time.sleep(random.uniform(lo, hi))

    @staticmethod
    def _timed(fn, *args, **kwargs):
        t0 = time.perf_counter()
        fn(*args, **kwargs)
        return int((time.perf_counter() - t0) * 1000)

    # ---- 实现 ----
    def click(self, x: int, y: int, humanize: bool = True) -> Action:
        # 人类化:在目标点附近 ±3px 抖动
        if humanize and self.humanize:
            x += random.randint(-3, 3)
            y += random.randint(-3, 3)
        ms = self._timed(self.device.click, x, y)
        self._delay()
        return Action(name="click", target=f"({x},{y})", duration_ms=ms)

    def click_by(
        self,
        *,
        resource_id=None,
        text=None,
        text_contains=None,
        content_desc=None,
        xpath=None,
        timeout=5.0,
    ) -> Action:
        target = (
            f"xpath={xpath}" if xpath
            else f"resource_id={resource_id}" if resource_id
            else f"content_desc={content_desc}" if content_desc
            else f"text={text}" if text
            else f"text_contains={text_contains}"
        )
        t0 = time.perf_counter()
        ok = self.device.click_element(
            resource_id=resource_id,
            text=text,
            text_contains=text_contains,
            content_desc=content_desc,
            xpath=xpath,
            timeout=timeout,
        )
        ms = int((time.perf_counter() - t0) * 1000)
        if ok:
            self._delay()
        else:
            logger.warning(f"点击元素未命中: {target}")
        return Action(name="click_by", target=target, success=ok, duration_ms=ms)

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> Action:
        ms = self._timed(self.device.swipe, x1, y1, x2, y2, duration)
        self._delay()
        return Action(
            name="swipe",
            target=f"({x1},{y1})->({x2},{y2})",
            duration_ms=ms,
        )

    def swipe_direction(self, direction: str, scale: float = 0.5) -> Action:
        """按方向滑动。direction ∈ {up, down, left, right}。"""
        w, h = self.device.info.resolution or (1080, 1920)
        cx, cy = w // 2, h // 2
        dx = int(w * scale)
        dy = int(h * scale)
        d = direction.lower()
        if d == "up":
            x1, y1, x2, y2 = cx, cy + dy // 2, cx, cy - dy // 2
        elif d == "down":
            x1, y1, x2, y2 = cx, cy - dy // 2, cx, cy + dy // 2
        elif d == "left":
            x1, y1, x2, y2 = cx + dx // 2, cy, cx - dx // 2, cy
        elif d == "right":
            x1, y1, x2, y2 = cx - dx // 2, cy, cx + dx // 2, cy
        else:
            return Action(name="swipe_direction", target=direction, success=False,
                          detail=f"未知方向: {direction}")
        return self.swipe(x1, y1, x2, y2)

    def input_text(self, text: str, clear: bool = False) -> Action:
        if clear:
            # 长按删除若干次
            for _ in range(min(50, len(text) + 5)):
                self.device.press("delete")
        ms = self._timed(self.device.input_text, text)
        self._delay()
        return Action(name="input_text", target=f"text={text!r}", duration_ms=ms)

    def press(self, key: str) -> Action:
        ms = self._timed(self.device.press, key)
        self._delay()
        return Action(name="press", target=key, duration_ms=ms)

    def start_app(self, package: str, activity: Optional[str] = None) -> Action:
        ms = self._timed(self.device.start_app, package, activity)
        time.sleep(1.0)  # 等待启动
        return Action(
            name="start_app",
            target=f"{package}/{activity}" if activity else package,
            duration_ms=ms,
        )

    def stop_app(self, package: str) -> Action:
        ms = self._timed(self.device.stop_app, package)
        return Action(name="stop_app", target=package, duration_ms=ms)
