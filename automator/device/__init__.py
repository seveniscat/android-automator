"""设备抽象层。

本期实现:
    - U2Device           uiautomator2 实现
    - SingleDeviceManager 单设备管理器

未来扩展(只需新增子类,上层零改动):
    - PoolDeviceManager  本地多设备池
    - AtxServerDevice    远程 atxserver2 设备
"""

from .base import Device, DeviceInfo, ElementInfo
from .exceptions import DeviceError, DeviceNotFoundError, DeviceOfflineError
from .manager import DeviceManager, get_device_manager
from .u2_device import U2Device

__all__ = [
    "Device",
    "DeviceInfo",
    "ElementInfo",
    "DeviceError",
    "DeviceNotFoundError",
    "DeviceOfflineError",
    "DeviceManager",
    "get_device_manager",
    "U2Device",
]
