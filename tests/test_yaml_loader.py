"""YAML 加载与校验测试(不依赖真机)。"""

from __future__ import annotations

import pytest

from automator.flow.yaml_loader import parse_flow, validate_flow
from automator.flow.steps import list_steps


def test_validate_ok():
    data = {
        "name": "t",
        "steps": [
            {"click": {"x": 1, "y": 2}},
            {"wait": {"seconds": 1}},
        ],
    }
    assert validate_flow(data) == []


def test_validate_missing_steps():
    assert validate_flow({}) == ["缺少 steps 字段"]


def test_validate_unknown_step():
    data = {"steps": [{"__unknown__": {}}]}
    errs = validate_flow(data)
    assert any("未知类型" in e for e in errs)


def test_parse_flow_basic():
    yaml_text = """
name: 测试
description: 一个测试流程
variables:
  k: v
steps:
  - start_app: { package: "com.x" }
  - wait: { seconds: 1 }
  - click: { text: "OK" }
"""
    flow = parse_flow(yaml_text)
    assert flow.name == "测试"
    assert flow.description == "一个测试流程"
    assert flow.variables == {"k": "v"}
    assert len(flow.steps) == 3
    assert flow.steps[0].type == "start_app"
    assert flow.steps[0].params["package"] == "com.x"
    assert flow.steps[2].params["text"] == "OK"


def test_parse_flow_invalid_raises():
    with pytest.raises(ValueError):
        parse_flow({"steps": [{"__bad__": {}}]})


def test_all_builtin_steps_registered():
    """所有内置步骤都应可被注册表发现。"""
    steps = list_steps()
    expected = {"click", "swipe", "input", "wait", "assert", "extract", "start_app", "stop_app", "press"}
    assert expected.issubset(set(steps))


def test_step_names_default_to_indexed():
    flow = parse_flow({"name": "n", "steps": [{"wait": {"seconds": 1}}]})
    # 默认 name 形如 "00_wait"
    assert flow.steps[0].name.endswith("_wait")
