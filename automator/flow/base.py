"""流程层数据模型。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Step:
    """单个流程步骤。

    name: 步骤显示名
    type: 步骤类型,对应 steps/registry 中注册的 key,如 "click"/"wait"
    params: 步骤参数(已从 YAML 解析)
    """

    name: str
    type: str
    params: dict[str, Any] = field(default_factory=dict)
    on_failure: str = "abort"   # abort / continue / retry
    retries: int = 0

    def __post_init__(self) -> None:
        if not self.name:
            self.name = f"{self.type}#{id(self)}"


@dataclass
class StepResult:
    """步骤执行结果。"""

    step_name: str
    step_type: str
    success: bool
    duration_ms: int = 0
    screenshot_path: Optional[str] = None
    detail: str = ""
    extracted: Any = None     # extract 步骤抽取的数据
    error: Optional[str] = None


@dataclass
class FlowResult:
    """整个流程的执行结果。"""

    success: bool
    steps: list[StepResult] = field(default_factory=list)
    duration_ms: int = 0
    error: Optional[str] = None
    data: dict = field(default_factory=dict)   # extract 汇总数据

    @property
    def step_count(self) -> int:
        return len(self.steps)


@dataclass
class Flow:
    """一个完整流程。"""

    name: str
    steps: list[Step] = field(default_factory=list)
    description: str = ""
    variables: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
