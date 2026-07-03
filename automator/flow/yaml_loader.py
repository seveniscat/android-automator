"""YAML DSL 加载器。

把人类可写的 YAML 转成 Flow(steps)对象。

支持的 YAML 形式:

    name: 微信发消息
    description: 打开微信并发消息
    variables:
      username: alice
    tags: [im, demo]
    steps:
      - start_app: { package: "com.tencent.mm" }
      - wait: { seconds: 2 }
      - click: { text: "通讯录" }
      - input:
          into: { resource_id: "com.tencent.mm/.search" }
          text: "${username}"
      - assert: { exists: { text_contains: "${username}" } }
      - extract:
          as: title
          from: { resource_id: "com.tencent.mm/.title" }

校验:未知步骤类型 / 缺失必填字段 → 抛 ValueError。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from ..logging import logger
from .base import Flow, Step
from .steps import list_steps


def parse_flow(data: dict | str) -> Flow:
    """从字典或 YAML 字符串解析出 Flow。"""
    if isinstance(data, str):
        data = yaml.safe_load(data)
    if not isinstance(data, dict):
        raise ValueError("Flow 必须是 mapping")
    return _build_flow(data)


def load_flow(path: str | Path) -> Flow:
    """从 YAML 文件加载 Flow。"""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Flow 文件不存在: {path}")
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return parse_flow(data)


def validate_flow(data: dict) -> list[str]:
    """校验 Flow 定义,返回错误列表(空列表表示通过)。"""
    errors: list[str] = []
    if not isinstance(data, dict):
        return ["Flow 必须是 mapping"]
    if "steps" not in data:
        errors.append("缺少 steps 字段")
        return errors
    if not isinstance(data["steps"], list):
        errors.append("steps 必须是列表")
        return errors

    known = set(list_steps())
    for i, item in enumerate(data["steps"]):
        if not isinstance(item, dict) or len(item) == 0:
            errors.append(f"步骤 #{i}: 必须是非空 mapping")
            continue
        # 一个 step 是 {type: {...}} 或 {type: null}(无参)
        step_type, step_params = next(iter(item.items()))
        if step_type not in known:
            errors.append(
                f"步骤 #{i}: 未知类型 {step_type!r},已注册: {sorted(known)}"
            )
    return errors


# ---- 内部 ----
def _build_flow(data: dict) -> Flow:
    errs = validate_flow(data)
    if errs:
        raise ValueError("Flow 校验失败:\n  - " + "\n  - ".join(errs))

    steps: list[Step] = []
    for i, item in enumerate(data["steps"]):
        step_type, step_params = next(iter(item.items()))
        if step_params is None:
            step_params = {}
        if not isinstance(step_params, dict):
            raise ValueError(
                f"步骤 #{i} ({step_type}) 的参数必须是 mapping,实际: {type(step_params)}"
            )
        steps.append(
            Step(
                name=step_params.pop("_name", f"{i:02d}_{step_type}"),
                type=step_type,
                params=step_params,
                on_failure=step_params.pop("_on_failure", "abort"),
                retries=int(step_params.pop("_retries", 0)),
            )
        )

    flow = Flow(
        name=data.get("name", "unnamed"),
        steps=steps,
        description=data.get("description", ""),
        variables=data.get("variables", {}),
        tags=data.get("tags", []),
    )
    logger.debug(f"已解析 Flow: {flow.name} ({len(flow.steps)} 步)")
    return flow
