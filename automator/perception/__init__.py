"""感知层。

本期实现:
    - ScreenshotPerception  截图 + 落盘

预留接口(本期 raise NotImplementedError):
    - OCRPerception         文字识别(PaddleOCR)
    - VLMPerception         视觉语言模型(GPT-4o / Claude / 国产 VLM)
"""

from .base import PerceptionState, Perception
from .screenshot import ScreenshotPerception

__all__ = ["PerceptionState", "Perception", "ScreenshotPerception"]
