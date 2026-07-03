"""流程执行上下文。

承载步骤间的变量传递与 extract 抽取的数据。
支持 ${var} / ${env.XXX} 模板插值。
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

_VAR_PATTERN = re.compile(r"\$\{([^}]+)\}")


@dataclass
class FlowContext:
    """流程执行上下文。"""

    variables: dict[str, Any] = field(default_factory=dict)
    extracted: dict[str, Any] = field(default_factory=dict)

    def set(self, key: str, value: Any) -> None:
        self.variables[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self.variables.get(key, default)

    def add_extracted(self, key: str, value: Any) -> None:
        self.extracted[key] = value

    def render(self, value: Any) -> Any:
        """递归对字符串/字典/列表做 ${var} 插值。"""
        if isinstance(value, str):
            return self._render_str(value)
        if isinstance(value, dict):
            return {k: self.render(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.render(v) for v in value]
        return value

    def _render_str(self, s: str) -> Any:
        """字符串插值。

        支持:
            ${var}           - 上下文变量
            ${env.HOME}      - 环境变量
            ${extracted.x}   - 已抽取数据
        整串恰好是一个 ${...} 时,保留原类型(可能为 int/list)。
        """
        m = _VAR_PATTERN.fullmatch(s.strip())
        if m:  # 整串占位 → 保留原类型
            return self._resolve(m.group(1))

        def repl(match):
            v = self._resolve(match.group(1))
            return "" if v is None else str(v)

        return _VAR_PATTERN.sub(repl, s)

    def _resolve(self, expr: str) -> Any:
        expr = expr.strip()
        if expr.startswith("env."):
            return os.environ.get(expr[4:])
        if expr.startswith("extracted."):
            return self.extracted.get(expr[len("extracted."):])
        return self.variables.get(expr)
