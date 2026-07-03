"""LLM 决策器(预留接口,本期不实现)。

未来:把 PerceptionState(截图 base64 / XML / OCR 文本)和自然语言 goal
喂给大模型,产出 ActionSpec 序列,实现"AI 自主任务"模式。

接入示意(后续迭代):
    from litellm import completion
    resp = completion(
        model="gpt-4o",
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
        response_format={"type": "json_object"},
    )
    actions = parse_json(resp)
"""

from __future__ import annotations

from typing import Optional

from ..config import settings
from ..perception.base import PerceptionState
from .base import ActionSpec, Planner


class LLMPlanner(Planner):
    """LLM 决策器占位实现。"""

    name = "llm"

    def __init__(self, model: Optional[str] = None) -> None:
        self.model = model or settings.llm_model

    def plan(
        self,
        state: PerceptionState,
        goal: str,
        context: Optional[dict] = None,
    ) -> list[ActionSpec]:
        raise NotImplementedError(
            "LLM 决策器为预留能力,本期不可用。"
            "后续迭代将通过 litellm 接入 GPT-4o/Claude/GLM-4V。"
        )
