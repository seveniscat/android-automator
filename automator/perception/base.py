"""感知层抽象。

`Perception` 负责把"设备当前状态"转成决策层可消费的结构化数据。
不同实现提供不同维度的感知:截图 / OCR 文本 / VLM 描述 / UI 树。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PerceptionState:
    """一次感知的快照。各字段按能力可选填充。"""

    screenshot: Optional[bytes] = None       # PNG 原图
    screenshot_path: Optional[str] = None    # 落盘路径
    hierarchy_xml: Optional[str] = None      # UI XML 树
    ocr_texts: list[dict] = field(default_factory=list)   # [{"text","box"}, ...]
    vlm_description: Optional[str] = None    # VLM 自然语言描述
    extras: dict = field(default_factory=dict)


class Perception(ABC):
    """感知器接口。"""

    name: str = "base"

    @abstractmethod
    def perceive(self, device) -> PerceptionState:
        """从设备采集一次状态快照。"""
