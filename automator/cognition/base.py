"""决策层抽象。

`Planner` 把"目标 + 当前感知"映射为动作序列。
- 规则版:YAML Flow 预定义的步骤即"规则",FlowRunner 直接顺序执行
- LLM 版:把感知态(截图/XML/OCR)喂给大模型,让它产出动作
两者接口一致,可平滑替换。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

from ..perception.base import PerceptionState


@dataclass
class ActionSpec:
    """决策层产出的"动作意图",由动作层执行。"""

    op: str                  # click / swipe / input / press / start_app ...
    params: dict = None      # 参数,如 {"x":100,"y":200} 或 {"text":"hi"}
    reason: str = ""         # 决策理由(LLM 版会填)

    def __post_init__(self):
        if self.params is None:
            self.params = {}


class Planner(ABC):
    """决策器接口。"""

    name: str = "planner"

    @abstractmethod
    def plan(
        self,
        state: PerceptionState,
        goal: str,
        context: Optional[dict] = None,
    ) -> list[ActionSpec]:
        """根据感知态和目标,产出动作序列。"""
