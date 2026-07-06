"""内置步骤注册表。

每个 Step 实现一个统一的可调用接口:
    (actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult

新增步骤只需:
    1. 在本目录新增模块
    2. 在本文件用 @register 装饰注册
"""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext

if TYPE_CHECKING:
    pass

# 步骤函数签名
StepFunc = Callable[[ActionLayer, Device, FlowContext, dict], StepResult]

# 全局注册表
_REGISTRY: dict[str, StepFunc] = {}


def register(name: str) -> Callable[[StepFunc], StepFunc]:
    """注册一个步骤类型。"""

    def deco(fn: StepFunc) -> StepFunc:
        if name in _REGISTRY:
            raise ValueError(f"步骤类型已存在: {name}")
        _REGISTRY[name] = fn
        return fn

    return deco


def get_step(name: str) -> StepFunc:
    """获取已注册的步骤函数。"""
    if name not in _REGISTRY:
        raise KeyError(
            f"未知步骤类型: {name!r}。已注册: {sorted(_REGISTRY.keys())}"
        )
    return _REGISTRY[name]


def list_steps() -> list[str]:
    return sorted(_REGISTRY.keys())


# ===== 导入各步骤模块以触发注册 =====
from . import click as _click  # noqa: E402,F401
from . import swipe as _swipe  # noqa: E402,F401
from . import input as _input  # noqa: E402,F401
from . import wait as _wait  # noqa: E402,F401
from . import assert_ as _assert  # noqa: E402,F401
from . import extract as _extract  # noqa: E402,F401
from . import app as _app  # noqa: E402,F401
from . import script as _script  # noqa: E402,F401
