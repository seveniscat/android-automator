"""动作层抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class Action:
    """一次动作的结果(便于日志/审计)。"""

    name: str
    target: str = ""           # 动作目标描述,如 "resource_id=xxx" / "(100,200)"
    success: bool = True
    detail: str = ""
    duration_ms: int = 0


class ActionLayer(ABC):
    """动作层接口。"""

    @abstractmethod
    def click(self, x: int, y: int, humanize: bool = True) -> Action: ...

    @abstractmethod
    def click_by(
        self,
        *,
        resource_id: Optional[str] = None,
        text: Optional[str] = None,
        text_contains: Optional[str] = None,
        content_desc: Optional[str] = None,
        xpath: Optional[str] = None,
        timeout: float = 5.0,
    ) -> Action: ...

    @abstractmethod
    def swipe(
        self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3
    ) -> Action: ...

    @abstractmethod
    def swipe_direction(self, direction: str, scale: float = 0.5) -> Action: ...

    @abstractmethod
    def input_text(self, text: str, clear: bool = False) -> Action: ...

    @abstractmethod
    def press(self, key: str) -> Action: ...

    @abstractmethod
    def start_app(self, package: str, activity: Optional[str] = None) -> Action: ...

    @abstractmethod
    def stop_app(self, package: str) -> Action: ...
