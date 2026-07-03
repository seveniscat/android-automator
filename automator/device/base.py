"""设备抽象基类。

定义所有设备实现(本地 u2 / 远程 atxserver2 / ...)需要遵守的统一接口。
上层(动作层、流程层)只依赖 `Device`,不依赖具体实现。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeviceInfo:
    """设备静态信息。"""

    serial: str               # 设备序列号
    model: str = ""           # 机型,如 "Pixel 6"
    brand: str = ""           # 品牌,如 "Google"
    android_version: str = "" # Android 版本,如 "13"
    sdk_version: int = 0      # SDK int
    resolution: tuple[int, int] = (0, 0)  # (width, height)
    atx_version: str = ""     # atx-agent 版本


@dataclass
class ElementInfo:
    """元素信息(由 dump_hierarchy 解析或 find 返回)。"""

    bounds: tuple[int, int, int, int] = (0, 0, 0, 0)  # left, top, right, bottom
    resource_id: str = ""
    text: str = ""
    class_name: str = ""
    content_desc: str = ""
    clickable: bool = False
    attributes: dict = field(default_factory=dict)

    @property
    def center(self) -> tuple[int, int]:
        l, t, r, b = self.bounds
        return ((l + r) // 2, (t + b) // 2)


class Device(ABC):
    """设备抽象基类。

    所有方法均为**同步阻塞**(底层 uiautomator2 是同步的),
    上层在异步上下文中应通过 `asyncio.to_thread` 调用。
    """

    info: DeviceInfo

    # ---- 生命周期 ----
    @abstractmethod
    def connect(self) -> None:
        """建立与设备的连接(对 u2 而言是确认 atx-agent 可达)。"""

    @abstractmethod
    def close(self) -> None:
        """释放连接。"""

    def __enter__(self) -> "Device":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # ---- 状态 ----
    @abstractmethod
    def is_alive(self) -> bool:
        """atx-agent 是否在线。"""

    @abstractmethod
    def refresh_info(self) -> DeviceInfo:
        """刷新并返回设备信息。"""

    # ---- 感知 ----
    @abstractmethod
    def screenshot(self) -> bytes:
        """截屏,返回 PNG 字节。"""

    @abstractmethod
    def dump_hierarchy(self) -> str:
        """导出当前 UI XML 层级。"""

    @abstractmethod
    def find_element(
        self,
        *,
        resource_id: Optional[str] = None,
        text: Optional[str] = None,
        text_contains: Optional[str] = None,
        class_name: Optional[str] = None,
        content_desc: Optional[str] = None,
        xpath: Optional[str] = None,
        timeout: float = 0.0,
    ) -> Optional[ElementInfo]:
        """查找元素,找不到返回 None(timeout=0 时不等待)。"""

    # ---- 动作 ----
    @abstractmethod
    def click(self, x: int, y: int) -> None:
        """按坐标点击。"""

    @abstractmethod
    def click_element(
        self,
        *,
        resource_id: Optional[str] = None,
        text: Optional[str] = None,
        text_contains: Optional[str] = None,
        content_desc: Optional[str] = None,
        xpath: Optional[str] = None,
        timeout: float = 5.0,
    ) -> bool:
        """按定位器点击元素,成功返回 True。

        content_desc 用于 Flutter / 自绘 UI(文字常以 content-description 暴露)。
        """

    @abstractmethod
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        """滑动手势。"""

    @abstractmethod
    def input_text(self, text: str) -> None:
        """向当前焦点输入框输入文本。"""

    @abstractmethod
    def press(self, key: str) -> None:
        """按下系统按键,如 'back' / 'home' / 'enter'。"""

    @abstractmethod
    def press_keycode(self, keycode: int) -> None:
        """按下原始 keycode。"""

    @abstractmethod
    def start_app(self, package: str, activity: Optional[str] = None) -> None:
        """启动应用。"""

    @abstractmethod
    def stop_app(self, package: str) -> None:
        """停止应用。"""

    @abstractmethod
    def current_app(self) -> dict:
        """返回当前前台应用,形如 {"package": ..., "activity": ...}。"""

    # ---- 等待 ----
    @abstractmethod
    def wait_exists(
        self,
        *,
        resource_id: Optional[str] = None,
        text: Optional[str] = None,
        text_contains: Optional[str] = None,
        content_desc: Optional[str] = None,
        xpath: Optional[str] = None,
        timeout: float = 5.0,
    ) -> bool:
        """等待元素出现,超时返回 False。"""
