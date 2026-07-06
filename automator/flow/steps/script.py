"""script 步骤:在运行时执行一小段 Python,处理 extract 抓不到的结构化数据。

extract 步骤擅长按选择器抓扁平字段列表,但遇到「标题 + 价格 + 销量」需要按
卡片容器分组、或需要相对取值/正则清洗时力不从心。script 步骤把整棵 UI XML
交给用户脚本,由用户自行解析,结果写入 ctx.extracted[as]。

== 用法 ==
    - script:
        as: products
        code: |
            root = ET.fromstring(device.dump_hierarchy())
            pm = {c: p for p in root.iter("node") for c in p}
            result = []
            for n in root.iter("node"):
                if n.attrib.get("resource-id", "").endswith("tv_title"):
                    card = n
                    pdd = [x.attrib.get("text", "")
                           for x in card.iter("node")
                           if x.attrib.get("resource-id", "").endswith("pdd")
                           and x.attrib.get("text", "").strip()]
                    result.append({
                        "title": n.attrib.get("content-desc", "").strip(),
                        "price": pdd[1] if len(pdd) > 1 else "",
                        "sales": pdd[2] if len(pdd) > 2 else "",
                    })

== 注入的命名空间 ==
    device  - Device 实例,可调用 dump_hierarchy() / click(x,y) / click_element(...) /
              wait_exists(...) / press(...) 等
    ctx     - FlowContext,可读 ctx.variables / ctx.extracted(跨步骤传递数据)
    ET      - xml.etree.ElementTree
    re      - 正则模块
    json    - json 模块
    time    - time 模块(sleep 等,面板动画兜底等待)
    result  - 脚本需把最终结果赋给此变量(默认 None)

== 安全说明 ==
运行在可信环境(本机/自有服务器),脚本来自流程作者本人。仅做 import 白名单
与异常捕获,不做完整沙箱。globals 仅暴露上述符号,不包含 __builtins__ 之外的
危险函数(但 Python 完全沙箱不可能,此处定位为「防误用」而非「防恶意」)。
"""

from __future__ import annotations

import json
import re
import time
from xml.etree import ElementTree as ET

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("script")
def step_script(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """执行用户 Python 脚本,结果(result 变量)写入 ctx.extracted[as]。"""
    name_key = params.get("as", "script_result")
    code = params.get("code") or ""

    # 受限 globals:仅暴露安全/常用符号,移除 open/exec/eval 等
    safe_builtins = {
        "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict,
        "enumerate": enumerate, "filter": filter, "float": float, "int": int,
        "isinstance": isinstance, "iter": iter, "len": len, "list": list,
        "map": map, "max": max, "min": min, "next": next, "print": print,
        "range": range, "round": round, "set": set, "sorted": sorted,
        "str": str, "sum": sum, "tuple": tuple, "zip": zip,
        "Exception": Exception, "ValueError": ValueError,
        "TypeError": TypeError, "KeyError": KeyError,
        "IndexError": IndexError, "StopIteration": StopIteration,
    }
    g: dict = {
        "__builtins__": safe_builtins,
        "device": device,
        "ctx": ctx,
        "ET": ET,
        "re": re,
        "json": json,
        "time": time,
        "result": None,
    }

    try:
        exec(compile(code, "<flow-script>", "exec"), g)
    except Exception as e:  # noqa: BLE001 —— 用户脚本异常需上报
        return StepResult(
            step_name=params.get("_name", "script"),
            step_type="script",
            success=False,
            error=f"脚本执行失败: {type(e).__name__}: {e}",
        )

    result = g.get("result")
    ctx.add_extracted(name_key, result)

    # 摘要:列表给条数,其它给 repr 截断
    if isinstance(result, list):
        detail = f"产出 {len(result)} 条"
    elif isinstance(result, dict):
        detail = f"产出 {len(result)} 个键"
    else:
        detail = f"产出: {result!r}"[:80]

    return StepResult(
        step_name=params.get("_name", "script"),
        step_type="script",
        success=True,
        extracted=result,
        detail=detail,
    )
