"""设备管理器。

本期:`DeviceManager` 持有**单台**设备(进程级单例)。
接口已抽象,未来可平滑替换为多设备池或 atxserver2 客户端。
"""

from __future__ import annotations

import threading
from typing import Optional

from ..config import settings
from ..logging import logger
from .base import Device
from .exceptions import DeviceNotFoundError
from .u2_device import U2Device


class DeviceManager:
    """设备管理器(线程安全单例)。

    本期策略:
        - `get_device()` 首次调用时连接配置中的默认设备并缓存
        - `list_devices()` 通过 adbutils 列出 USB/远程设备
    """

    _instance: Optional["DeviceManager"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "DeviceManager":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._device: Optional[Device] = None
        self._device_lock = threading.Lock()
        self._initialized = True

    # ---- 获取设备 ----
    def get_device(self, device_id: Optional[str] = None) -> Device:
        """获取设备连接。

        本期忽略 device_id,始终返回单台默认设备。
        """
        with self._device_lock:
            if self._device is not None and self._device.is_alive():
                return self._device

            serial = device_id or settings.device_serial
            logger.info(f"创建设备连接: serial={serial!r}")
            dev = U2Device(serial=serial, atx_port=settings.atx_port)
            dev.connect()
            self._device = dev
            return dev

    def reset(self) -> None:
        """强制断开并清空缓存,下次 get_device 重新连接。"""
        with self._device_lock:
            if self._device is not None:
                try:
                    self._device.close()
                except Exception:
                    pass
            self._device = None

    # ---- 枚举 ----
    @staticmethod
    def list_adb_devices() -> list[dict]:
        """列出 adb 可见设备(不依赖 atx-agent 是否就绪)。"""
        try:
            from adbutils import adb

            devices = []
            for d in adb.device_list():
                # 兼容不同版本 adbutils:state 字段可能缺失
                state = getattr(d, "state", None) or "device"
                try:
                    model = d.prop.model if hasattr(d, "prop") else ""
                except Exception:
                    model = ""
                devices.append({"serial": d.serial, "state": state, "model": model})
            return devices
        except Exception as e:
            logger.warning(f"枚举 adb 设备失败: {e}")
            return []


def get_device_manager() -> DeviceManager:
    """获取全局 DeviceManager 单例。"""
    return DeviceManager()
