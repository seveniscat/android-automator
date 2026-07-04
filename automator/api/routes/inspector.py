"""页面元素检查器路由。

提供"截屏 + 解析后的元素树"给前端,用于可视化查看当前界面元素、
点击高亮、自动生成 YAML 步骤(类似 weditor)。
"""

from __future__ import annotations

import asyncio
import re
from xml.etree import ElementTree as ET

from fastapi import APIRouter, Depends, HTTPException, Response

from ...device.manager import DeviceManager
from ..deps import get_dm

router = APIRouter(prefix="/api/inspector", tags=["inspector"])

_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _parse_bounds(s: str) -> tuple[int, int, int, int] | None:
    m = _BOUNDS_RE.search(s or "")
    if not m:
        return None
    return tuple(int(x) for x in m.groups())


def _build_element_tree(xml: str) -> dict:
    """把 UI XML 解析成扁平元素列表 + 屏幕尺寸。

    返回:
        {
          "width": int, "height": int,
          "elements": [
            {"id","depth","parent","bounds":[l,t,r,b],"cx","cy",
             "text","content_desc","resource_id","class","clickable","package","children":[...]}
          ]
        }
    """
    root = ET.fromstring(xml)
    elements: list[dict] = []
    width = height = 0

    def walk(node: ET.Element, depth: int, parent: int | None) -> int:
        nonlocal width, height
        idx = len(elements)
        a = node.attrib
        bounds = _parse_bounds(a.get("bounds", ""))
        l, t, r, b = bounds or (0, 0, 0, 0)
        if r > width:
            width = r
        if b > height:
            height = b
        rec = {
            "id": idx,
            "depth": depth,
            "parent": parent,
            "bounds": [l, t, r, b],
            "cx": (l + r) // 2,
            "cy": (t + b) // 2,
            "text": a.get("text", ""),
            "content_desc": a.get("content-desc", ""),
            "resource_id": a.get("resource-id", ""),
            "class": a.get("class", ""),
            "clickable": a.get("clickable") == "true",
            "scrollable": a.get("scrollable") == "true",
            "package": a.get("package", ""),
            "children": [],
        }
        elements.append(rec)
        if parent is not None:
            elements[parent]["children"].append(idx)
        child_parent = idx if node.tag != "hierarchy" else None
        for child in node:
            walk(child, depth + 1, idx)
        return idx

    # hierarchy 根节点本身不计入,从其子节点开始
    for child in root:
        walk(child, 0, None)

    return {"width": width, "height": height, "elements": elements}


@router.get("/snapshot")
async def snapshot(dm: DeviceManager = Depends(get_dm)):
    """采集一次快照:截图 + 元素树。

    前端可基于元素 bounds 在截图上画高亮框;选中元素后可自动生成 YAML。
    """
    try:
        dev = dm.get_device()
        png, xml = await asyncio.to_thread(_capture, dev)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"采集快照失败: {e}")

    tree = _build_element_tree(xml)
    # 把 PNG 存为可访问的 URL(用时间戳避免缓存)
    import time, uuid

    from ...config import settings
    filename = f"insp_{int(time.time())}_{uuid.uuid4().hex[:6]}.png"
    path = settings.screenshot_dir / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)

    # 过滤"有用"元素(有文字/标签/可点击),便于前端默认展示
    useful = [
        e for e in tree["elements"]
        if e["text"] or e["content_desc"] or e["clickable"]
    ]

    return {
        "screenshot": f"/api/inspector/screenshot/{filename}",
        "width": tree["width"],
        "height": tree["height"],
        "total": len(tree["elements"]),
        "useful_count": len(useful),
        "elements": tree["elements"],
        "useful": useful,
    }


def _capture(dev):
    """采集截图与 XML。"""
    png = dev.screenshot()
    xml = dev.dump_hierarchy()
    return png, xml


@router.get("/screenshot/{filename}")
async def get_inspector_screenshot(filename: str):
    """读取 inspector 存下的截图。"""
    from ...config import settings
    from pathlib import Path

    # 防目录穿越
    if "/" in filename or "\\" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="非法文件名")
    path: Path = settings.screenshot_dir / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="截图不存在")
    return Response(content=path.read_bytes(), media_type="image/png")


@router.post("/tap")
async def tap(body: dict, dm: DeviceManager = Depends(get_dm)):
    """点击指定坐标(检查器里点元素时调用)。"""
    x = int(body.get("x", 0))
    y = int(body.get("y", 0))
    try:
        dev = dm.get_device()
        await asyncio.to_thread(dev.click, x, y)
        return {"ok": True, "x": x, "y": y}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"点击失败: {e}")


@router.post("/generate-yaml")
async def generate_yaml(body: dict):
    """根据选中元素 + 期望动作,生成 YAML 步骤片段。

    body: {"element": {...}, "action": "click"|"wait"|"assert"}
    """
    el = body.get("element", {})
    action = body.get("action", "click")
    # 定位器优先级:content_desc > text > resource_id > 坐标
    locator = None
    if el.get("content_desc"):
        locator = f'content_desc: "{el["content_desc"]}"'
    elif el.get("text"):
        locator = f'text: "{el["text"]}"'
    elif el.get("resource_id"):
        locator = f'resource_id: "{el["resource_id"]}"'
    else:
        locator = f'x: {el.get("cx", 0)}, y: {el.get("cy", 0)}'

    yaml_map = {
        "click": f"- click: {{ {locator} }}",
        "wait": f"- wait: {{ {locator}, timeout: 5 }}",
        "assert": f"- assert: {{ exists: {{ {locator} }} }}",
    }
    snippet = yaml_map.get(action, yaml_map["click"])
    return {"yaml": snippet, "locator": locator}
