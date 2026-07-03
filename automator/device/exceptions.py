"""设备层异常体系。"""

from __future__ import annotations


class DeviceError(Exception):
    """设备层基础异常。"""


class DeviceNotFoundError(DeviceError):
    """没有找到可用设备。"""


class DeviceOfflineError(DeviceError):
    """设备离线或 atx-agent 不可达。"""


class ElementNotFoundError(DeviceError):
    """元素定位失败。"""
