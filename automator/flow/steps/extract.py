"""extract 步骤:从 UI 中抽取数据(爬虫场景核心)。

从 UI XML 树中抽取节点与字段,结果写入 ctx.extracted[as]。

== Android UI XML 结构说明 ==
Android dump_hierarchy 产出的 XML 形如:
    <hierarchy>
      <node class="android.widget.TextView" text="设置" resource-id="..." ...>
        <node .../>
      </node>
    </hierarchy>

所有元素 tag 都是 "node",真正的语义信息在属性里(class / text / resource-id /
content-desc / bounds ...),ElementTree 的 findall 不支持 "//tag" 与属性谓词,
因此本实现用 iter() + 属性匹配。

== 选择器语法(selector / list)==
支持三种形式:
    1. class 选择器(最常用):
         "android.widget.TextView"            # class 全等
         "TextView"                            # class 后缀匹配
         "*TextView"                           # class 包含
    2. resource-id:
         "@com.android.settings:id/title"     # resource-id 全等
         "@id/title"                           # resource-id 后缀匹配
    3. 任意(返回所有 node):
         "*"
== fields 语法 ==
对每个匹配节点,字段值用属性名直接读取:
    fields: { title: text, rid: "resource-id", desc: "content-desc" }
或相对子查找(可选):
    fields: { x: "node/2/@text" }
"""

from __future__ import annotations

import re
from typing import Optional

from ...action.base import ActionLayer
from ...device.base import Device
from ..base import StepResult
from ..context import FlowContext
from . import register


@register("extract")
def step_extract(actions: ActionLayer, device: Device, ctx: FlowContext, params: dict) -> StepResult:
    """
    单值模式:
        - extract:
            as: username
            from: { resource_id: "com.x/.tv_user" }   # 或 text / text_contains
            attribute: text                            # 默认 text

    列表模式:
        - extract:
            as: feed
            list: "android.widget.TextView"           # 选择器(见模块 docstring)
            fields: { title: text, rid: "resource-id" }
            limit: 100                                # 可选,默认无限制
    """
    name_key = params.get("as", "extracted")
    attribute = params.get("attribute", "text")
    xml = device.dump_hierarchy()

    # ---- 列表模式 ----
    selector = params.get("list")
    if selector:
        try:
            from xml.etree import ElementTree as ET
            root = ET.fromstring(xml)
        except ET.ParseError as e:
            return StepResult(
                step_name=params.get("_name", "extract"),
                step_type="extract", success=False,
                error=f"解析 UI XML 失败: {e}",
            )

        fields_spec = params.get("fields", {}) or {}
        limit = int(params.get("limit", 0)) or None
        # where:只保留某字段非空的行,如 where: label
        where_field = params.get("where")

        rows = []
        for node in _select_nodes(root, selector):
            row = {}
            for fname, fexpr in fields_spec.items():
                row[fname] = _read_field(node, fexpr, attribute)
            # where 过滤:指定字段为空则跳过
            if where_field:
                val = row.get(where_field)
                if val is None or val == "":
                    continue
            rows.append(row)
            if limit and len(rows) >= limit:
                break
        ctx.add_extracted(name_key, rows)
        return StepResult(
            step_name=params.get("_name", "extract"),
            step_type="extract",
            success=True,
            extracted=rows,
            detail=f"抽出 {len(rows)} 条",
        )

    # ---- 单值模式 ----
    spec = params.get("from", {}) or {}
    text = _first_match_value(
        xml,
        resource_id=spec.get("resource_id"),
        text=spec.get("text"),
        text_contains=spec.get("text_contains"),
        content_desc=spec.get("content_desc"),
        attribute=attribute,
    )
    ctx.add_extracted(name_key, text)
    return StepResult(
        step_name=params.get("_name", "extract"),
        step_type="extract",
        success=True,
        extracted=text,
        detail=f"抽出值: {text!r}",
    )


# ---- 选择器实现 ----
def _select_nodes(root, selector: str):
    """按选择器迭代匹配节点。

    selector 形式见模块 docstring。
    """
    selector = (selector or "").strip()
    if not selector or selector == "*":
        yield from root.iter("node")
        return

    if selector.startswith("@"):
        rid = selector[1:]
        suffix = "/" + rid if not rid.startswith("/") else rid
        for n in root.iter("node"):
            r = n.attrib.get("resource-id", "")
            if r == rid or r.endswith(suffix) or r.endswith("/" + rid):
                yield n
        return

    if selector.startswith("*"):
        sub = selector[1:]
        for n in root.iter("node"):
            if sub in n.attrib.get("class", ""):
                yield n
        return

    # class 选择器:全等或后缀
    cls_target = selector
    for n in root.iter("node"):
        cls = n.attrib.get("class", "")
        if cls == cls_target or cls.endswith("." + cls_target):
            yield n


def _read_field(node, fexpr: str, default_attr: str) -> Optional[str]:
    """读取字段值。

    fexpr 可以是:
        - 纯属性名:"text" / "resource-id" / "content-desc" / "class"
        - 带 @:"@text" (等价于 text)
        - "." :取默认属性
    """
    fexpr = (fexpr or "").strip()
    if not fexpr or fexpr == ".":
        attr = default_attr
    elif fexpr.startswith("@"):
        attr = fexpr[1:]
    else:
        attr = fexpr
    return node.attrib.get(attr)


def _first_match_value(
    xml: str,
    *,
    resource_id: Optional[str] = None,
    text: Optional[str] = None,
    text_contains: Optional[str] = None,
    content_desc: Optional[str] = None,
    attribute: str = "text",
) -> Optional[str]:
    """按条件找首个节点,返回其 attribute。"""
    from xml.etree import ElementTree as ET

    try:
        root = ET.fromstring(xml)
    except ET.ParseError:
        return None

    rid_suffix = ("/" + resource_id) if resource_id and not resource_id.startswith("/") else resource_id

    for node in root.iter("node"):
        a = node.attrib
        if resource_id:
            rid = a.get("resource-id", "")
            if rid != resource_id and not rid.endswith(rid_suffix or "##"):
                continue
        if text and a.get("text", "") != text:
            continue
        if text_contains and text_contains not in a.get("text", ""):
            continue
        if content_desc and a.get("content-desc", "") != content_desc:
            continue
        return a.get(attribute)
    return None
