"""截图感知器:采集截图 + UI 层级,落盘以便回放。"""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from ..config import settings
from ..logging import logger
from .base import Perception, PerceptionState


class ScreenshotPerception(Perception):
    """截图感知。

    把 PNG 写到 `settings.screenshot_dir`,便于运行回放。
    可选同时采集 UI 层级 XML。
    """

    name = "screenshot"

    def __init__(self, capture_hierarchy: bool = True) -> None:
        self.capture_hierarchy = capture_hierarchy

    def perceive(self, device) -> PerceptionState:
        png = device.screenshot()
        screenshot_path = None
        try:
            filename = f"{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.png"
            path = Path(settings.screenshot_dir) / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png)
            screenshot_path = str(path)
        except Exception as e:
            logger.warning(f"截图落盘失败: {e}")

        hierarchy_xml = None
        if self.capture_hierarchy:
            try:
                hierarchy_xml = device.dump_hierarchy()
            except Exception as e:
                logger.debug(f"采集 UI 层级失败: {e}")

        return PerceptionState(
            screenshot=png,
            screenshot_path=screenshot_path,
            hierarchy_xml=hierarchy_xml,
        )
