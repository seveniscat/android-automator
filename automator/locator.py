"""智能定位辅助 —— 把一次坐标点击翻译成元素定位器。

录制时,点击屏幕会先抓一次 UI 层级,找到包含该坐标且最有意义的元素,
按 `content_desc > text > resource_id` 优先级返回定位器;
找不到则返回 None,录制回退到坐标点击。

定位器优先级与 `inspector.generate_yaml` 保持一致,确保录制与检查器
生成的 YAML 风格统一。
"""

from __future__ import annotations

import re
from xml.etree import ElementTree as ET

from .device.base import Device
from .logging import logger

# bounds 形如 "[100,200][300,400]",与 inspector 路由保持一致的解析
_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _parse_bounds(s: str) -> tuple[int, int, int, int] | None:
    m = _BOUNDS_RE.search(s or "")
    if not m:
        return None
    return tuple(int(x) for x in m.groups())  # type: ignore[return-value]


def resolve_click_locator(dev: Device, x: int, y: int) -> dict | None:
    """根据点击坐标在 UI 层级中找出最佳定位器。

    返回:
        单键字典,如 {"text": "登录"} / {"resource_id": "com.x/.btn"},
        或 None(无命中元素 / 抓取失败 → 调用方回退坐标)。
    """
    try:
        xml = dev.dump_hierarchy()
    except Exception as e:  # noqa: BLE001 —— 抓层级失败不阻塞录制
        logger.debug(f"录制智能定位:抓取层级失败,回退坐标: {e}")
        return None

    best = _find_deepest_at(xml, x, y)
    if best is None:
        return None

    # 优先级:content_desc > text > resource_id
    content_desc = best.get("content-desc", "")
    if content_desc:
        return {"content_desc": content_desc}
    text = best.get("text", "")
    if text:
        return {"text": text}
    resource_id = best.get("resource-id", "")
    if resource_id:
        return {"resource_id": resource_id}
    return None


def _find_deepest_at(xml: str, x: int, y: int) -> ET.Element | None:
    """在 XML 树中找到包含 (x,y) 且最有意义的最深层节点。

    选择策略:在所有「包含该点」的节点里,优先取可点击(clickable=true)或
    带有定位特征(text/content-desc/resource-id)的节点;多个候选时取 bounds
    面积最小(即最深层、最精确)的一个。
    """
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as e:
        logger.debug(f"录制智能定位:XML 解析失败: {e}")
        return None

    candidates: list[tuple[int, ET.Element]] = []  # (area, element)
    for node in root.iter():
        a = node.attrib
        bounds = _parse_bounds(a.get("bounds", ""))
        if not bounds:
            continue
        l, t, r, b = bounds
        if not (l <= x <= r and t <= y <= b):
            continue
        # 只保留有定位意义或可点击的节点
        has_locator = bool(
            a.get("text") or a.get("content-desc") or a.get("resource-id")
        )
        if not (a.get("clickable") == "true" or has_locator):
            continue
        candidates.append(((r - l) * (b - t), node))

    if not candidates:
        return None
    # 面积最小 = 最精确/最深层
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]
