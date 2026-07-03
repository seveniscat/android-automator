"""设备路由。"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException, Response

from ...device.exceptions import DeviceError, DeviceNotFoundError
from ...device.manager import DeviceManager
from ..deps import get_dm, get_repo

router = APIRouter(prefix="/api/devices", tags=["devices"])


@router.get("")
async def list_devices(dm: DeviceManager = Depends(get_dm)):
    """列出 adb 可见设备 + 当前连接的设备。"""
    adb_devices = DeviceManager.list_adb_devices()
    current = None
    try:
        dev = dm.get_device()
        info = dev.refresh_info() if dev.is_alive() else dev.info
        current = {
            "serial": info.serial,
            "model": info.model,
            "brand": info.brand,
            "android_version": info.android_version,
            "resolution": list(info.resolution),
            "alive": dev.is_alive(),
        }
    except (DeviceError, DeviceNotFoundError, Exception) as e:
        current = {"alive": False, "error": str(e)}
    return {"adb_devices": adb_devices, "current": current}


@router.get("/screenshot")
async def screenshot(dm: DeviceManager = Depends(get_dm)):
    """实时截图。"""
    try:
        dev = dm.get_device()
        png = await asyncio.to_thread(dev.screenshot)
        return Response(content=png, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"截图失败: {e}")


@router.get("/hierarchy")
async def hierarchy(dm: DeviceManager = Depends(get_dm)):
    """当前 UI 层级 XML。"""
    try:
        dev = dm.get_device()
        xml = await asyncio.to_thread(dev.dump_hierarchy)
        return Response(content=xml, media_type="application/xml")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"取层级失败: {e}")


@router.get("/current-app")
async def current_app(dm: DeviceManager = Depends(get_dm)):
    try:
        dev = dm.get_device()
        info = await asyncio.to_thread(dev.current_app)
        return info
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@router.post("/reset")
async def reset_connection(dm: DeviceManager = Depends(get_dm)):
    """强制重置设备连接(下次自动重连)。"""
    dm.reset()
    return {"ok": True, "msg": "连接已重置"}
