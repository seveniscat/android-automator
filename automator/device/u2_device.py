"""uiautomator2 设备实现。"""

from __future__ import annotations

import time
from typing import Optional

from ..logging import logger
from .base import Device, DeviceInfo, ElementInfo
from .exceptions import DeviceError, DeviceNotFoundError, ElementNotFoundError


# Android 按键名 → u2 接受的字符串
_KEY_ALIASES = {
    "back": "back",
    "home": "home",
    "menu": "menu",
    "recent": "recent",
    "recents": "recent",
    "enter": "enter",
    "delete": "delete",
    "search": "search",
    "volume_up": "volume_up",
    "volume_down": "volume_down",
    "power": "power",
}


class U2Device(Device):
    """基于 openatx/uiautomator2 的真机实现。

    通过 atx-agent(HTTP, 默认 7912 端口)与设备通信,
    支持 USB 与 WiFi 两种连接方式。
    """

    def __init__(self, serial: str = "", atx_port: int = 7912) -> None:
        self._serial = serial
        self._atx_port = atx_port
        self._d = None  # uiautomator2.Device
        self.info: DeviceInfo = DeviceInfo(serial=serial or "unknown")

    # ---- 生命周期 ----
    def connect(self) -> None:
        import uiautomator2 as u2  # 延迟导入,启动更快

        try:
            if self._serial:
                # 形如 "device_serial:port" 或纯 serial(USB)
                addr = (
                    f"{self._serial}:{self._atx_port}"
                    if "." in self._serial
                    else self._serial
                )
                logger.info(f"连接设备: {addr}")
                self._d = u2.connect(addr)
            else:
                logger.info("自动选择第一台可用设备")
                self._d = u2.connect()  # 自动发现
        except Exception as e:
            raise DeviceNotFoundError(
                f"无法连接设备(serial={self._serial!r}): {e}"
            ) from e

        self.info = self.refresh_info()
        logger.info(
            f"已连接 {self.info.brand} {self.info.model} "
            f"(Android {self.info.android_version}, {self.info.serial})"
        )

    def close(self) -> None:
        # u2 是无状态 HTTP,无需显式关闭
        self._d = None

    # ---- 状态 ----
    def is_alive(self) -> bool:
        if self._d is None:
            return False
        try:
            return bool(self._d.info)
        except Exception:
            return False

    def refresh_info(self) -> DeviceInfo:
        if self._d is None:
            raise DeviceError("设备未连接")
        info = self._d.info
        serial = self._serial or self._d.serial or "unknown"
        w, h = info.get("displayWidth", 0), info.get("displayHeight", 0)
        self.info = DeviceInfo(
            serial=serial,
            model=info.get("productName", "") or info.get("model", ""),
            brand=info.get("brand", ""),
            android_version=info.get("sdkInt", "") and str(info["sdkInt"]),
            sdk_version=int(info.get("sdkInt", 0) or 0),
            resolution=(w, h),
            atx_version=info.get("atxAgentVersion", ""),
        )
        return self.info

    # ---- 内部工具 ----
    def _require(self):
        if self._d is None:
            raise DeviceError("设备未连接,请先 connect()")
        return self._d

    def _selector(self, **kwargs):
        """把我们的命名转换为 u2 的 Selector。"""
        d = self._require()
        kw = {k: v for k, v in kwargs.items() if v is not None}
        return d(**kw)

    def _elem_to_info(self, el) -> ElementInfo:
        info = el.info
        bounds = self._normalize_bounds(info.get("bounds", [0, 0, 0, 0]))
        return ElementInfo(
            bounds=bounds,
            resource_id=info.get("resourceName", "") or info.get("resourceId", ""),
            text=info.get("text", ""),
            class_name=info.get("className", ""),
            content_desc=info.get("contentDescription", ""),
            clickable=info.get("clickable", False),
        )

    @staticmethod
    def _normalize_bounds(bounds) -> tuple[int, int, int, int]:
        """把 u2 各种 bounds 表示统一成 (left, top, right, bottom) 整数元组。

        u2 不同版本可能返回:list / dict / namedtuple(可能是字段名 ltrb 或 bounds 对象)。
        """
        # list / tuple of ints
        if isinstance(bounds, (list, tuple)):
            nums = [x for x in bounds if isinstance(x, int)]
            if len(nums) >= 4:
                return tuple(nums[:4])
        # dict 形式
        if isinstance(bounds, dict):
            try:
                return (
                    int(bounds.get("left", bounds.get("l", 0))),
                    int(bounds.get("top", bounds.get("t", 0))),
                    int(bounds.get("right", bounds.get("r", 0))),
                    int(bounds.get("bottom", bounds.get("b", 0))),
                )
            except (TypeError, ValueError):
                pass
        # u2 Bounds 对象(有 ltrb 属性)
        for attr in ("ltrb", "left"):
            if hasattr(bounds, attr):
                try:
                    b = bounds.ltrb if hasattr(bounds, "ltrb") else (
                        bounds.left, bounds.top, bounds.right, bounds.bottom
                    )
                    return tuple(int(x) for x in b)
                except (TypeError, ValueError, AttributeError):
                    break
        return (0, 0, 0, 0)

    # ---- 感知 ----
    def screenshot(self) -> bytes:
        import io

        d = self._require()
        img = d.screenshot()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    def dump_hierarchy(self) -> str:
        d = self._require()
        return d.dump_hierarchy()

    def find_element(
        self,
        *,
        resource_id=None,
        text=None,
        text_contains=None,
        class_name=None,
        content_desc=None,
        xpath=None,
        timeout=0.0,
    ) -> Optional[ElementInfo]:
        d = self._require()
        if xpath:
            sel = d.xpath(xpath)
            if sel.exists:
                return ElementInfo(bounds=sel.bounds)
            return None
        sel = self._selector(
            resourceId=resource_id,
            text=text,
            textContains=text_contains,
            className=class_name,
            description=content_desc,
        )
        if timeout > 0:
            sel.wait(timeout=timeout)
        if not sel.exists:
            return None
        return self._elem_to_info(sel)

    # ---- 动作 ----
    def click(self, x: int, y: int) -> None:
        d = self._require()
        d.click(x, y)

    def click_element(
        self,
        *,
        resource_id=None,
        text=None,
        text_contains=None,
        content_desc=None,
        xpath=None,
        timeout=5.0,
    ) -> bool:
        if xpath:
            d = self._require()
            if d.xpath(xpath).click_exists(timeout=timeout):
                return True
            return False
        sel = self._selector(
            resourceId=resource_id,
            text=text,
            textContains=text_contains,
            description=content_desc,
        )
        if sel.click_exists(timeout=timeout):
            return True
        return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: float = 0.3) -> None:
        d = self._require()
        d.swipe(x1, y1, x2, y2, duration=duration)

    def input_text(self, text: str) -> None:
        d = self._require()
        d.send_keys(text)

    def press(self, key: str) -> None:
        d = self._require()
        name = _KEY_ALIASES.get(key.lower(), key)
        # u2 兼容写法:press("back") 或 key("back") 均可
        try:
            d.press(name)
        except (AttributeError, TypeError):
            d.key(name)

    def press_keycode(self, keycode: int) -> None:
        d = self._require()
        try:
            d.press(code=keycode)
        except (AttributeError, TypeError):
            d.key(code=keycode)

    def start_app(self, package: str, activity: Optional[str] = None) -> None:
        d = self._require()
        if activity:
            d.shell(f"am start -n {package}/{activity}")
        else:
            d.app_start(package)

    def stop_app(self, package: str) -> None:
        d = self._require()
        d.app_stop(package)

    def current_app(self) -> dict:
        d = self._require()
        info = d.app_current()
        return {
            "package": info.get("package", ""),
            "activity": info.get("activity", ""),
            "pid": info.get("pid"),
        }

    # ---- 等待 ----
    def wait_exists(
        self,
        *,
        resource_id=None,
        text=None,
        text_contains=None,
        content_desc=None,
        xpath=None,
        timeout=5.0,
    ) -> bool:
        if xpath:
            return self._require().xpath(xpath).wait(timeout=timeout)
        sel = self._selector(
            resourceId=resource_id,
            text=text,
            textContains=text_contains,
            description=content_desc,
        )
        return bool(sel.wait(timeout=timeout))
