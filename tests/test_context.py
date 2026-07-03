"""流程上下文变量插值测试。"""

from __future__ import annotations

import os

from automator.flow.context import FlowContext


def test_string_render():
    ctx = FlowContext(variables={"name": "alice"})
    assert ctx.render("hello ${name}") == "hello alice"


def test_full_match_preserves_type():
    ctx = FlowContext(variables={"n": 42, "lst": [1, 2]})
    assert ctx.render("${n}") == 42
    assert ctx.render("${lst}") == [1, 2]


def test_dict_render_recursive():
    ctx = FlowContext(variables={"a": 1, "b": 2})
    out = ctx.render({"x": "${a}", "y": ["${b}", "plain"]})
    assert out == {"x": 1, "y": [2, "plain"]}


def test_env_var(monkeypatch):
    monkeypatch.setenv("AUTOMATOR_TEST_VAR", "envval")
    ctx = FlowContext()
    assert ctx.render("${env.AUTOMATOR_TEST_VAR}") == "envval"


def test_extracted_namespace():
    ctx = FlowContext()
    ctx.add_extracted("title", "hello")
    assert ctx.render("${extracted.title}") == "hello"


def test_missing_var_returns_none_for_fullmatch():
    ctx = FlowContext()
    assert ctx.render("${missing}") is None
    # 嵌入式则替换为空串
    assert ctx.render("a${missing}b") == "ab"
