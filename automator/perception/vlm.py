"""VLM 视觉语言模型感知器(预留接口,本期不实现)。

未来接入 GPT-4o / Claude / GLM-4V 等,把截图转成:
  - 自然语言场景描述
  - 可点击元素的语义化列表
为 LLM Planner 提供输入。
"""

from __future__ import annotations

from typing import Optional

from ..config import settings
from .base import Perception, PerceptionState


class VLMPerception(Perception):
    """VLM 感知器占位实现。

    接入方式(后续迭代):
        pip install litellm  # 或 OpenAI/Anthropic SDK
        在 perceive() 中将截图 base64 + prompt 发给 VLM
    """

    name = "vlm"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.llm_model

    def perceive(self, device) -> PerceptionState:
        raise NotImplementedError(
            "VLM 感知器为预留能力,本期不可用。"
            "后续迭代将通过 litellm 接入 GPT-4o/Claude/GLM-4V。"
        )
