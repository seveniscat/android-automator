"""规则决策器。

本期"规则"= YAML Flow 中预定义的步骤序列。
FlowRunner 不强制走 Planner —— 直接顺序执行 Step;
但 RulePlanner 提供了"按目标反查动作"的统一入口,便于未来切换到 LLM。
"""

from __future__ import annotations

from typing import Optional

from ..perception.base import PerceptionState
from .base import ActionSpec, Planner


class RulePlanner(Planner):
    """规则决策器占位实现。

    本期 Flow 由 YAML 显式编排,无需 Planner 做推理;
    这里保留接口,使未来 LLM Planner 可与之互换。
    """

    name = "rule"

    def plan(
        self,
        state: PerceptionState,
        goal: str,
        context: Optional[dict] = None,
    ) -> list[ActionSpec]:
        # 规则版:无显式规则库时返回空,交由 Flow 显式编排
        return []
