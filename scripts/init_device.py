#!/usr/bin/env python3
"""设备初始化脚本:自动为 USB 设备安装 atx-agent + app-uiautomator APK。

用法:
    python scripts/init_device.py                  # 自动选第一台设备
    python scripts/init_device.py <serial>         # 指定设备
    python scripts/init_device.py 192.168.1.100    # WiFi 设备
"""

from __future__ import annotations

import sys
from pathlib import Path

# 让脚本无需安装即可引用 automator 包
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from automator.logging import logger, setup_logging


def main() -> int:
    setup_logging()
    serial = sys.argv[1] if len(sys.argv) > 1 else None

    try:
        import uiautomator2 as u2
    except ImportError:
        logger.error("未安装 uiautomator2,请先 `pip install uiautomator2`")
        return 1

    logger.info(f"开始初始化设备: {serial or '(自动)'}")
    try:
        # u2.init 会自动安装/更新 atx-agent 与 app-uiautomator[-test].apk
        if serial and "." in serial:
            # WiFi 模式:先用 adb connect
            from adbutils import adb
            adb.connect(serial)
        u2.init(serial=serial or None, reinstall=False)
        logger.info("✓ atx-agent 与 APK 安装完成")
    except Exception as e:
        logger.error(f"初始化失败: {e}")
        logger.info("排查建议:")
        logger.info("  1. 确认手机已开启 USB 调试,且 PC 能 `adb devices` 看到设备")
        logger.info("  2. 在手机上授权 PC 的 RSA 指纹")
        logger.info("  3. 确认 atx-agent 端口(默认 7912)未被占用")
        return 2

    # 验证连接
    try:
        d = u2.connect(serial) if serial else u2.connect()
        info = d.info
        logger.info(
            f"✓ 连接成功: {info.get('productName','?')} "
            f"(Android {info.get('sdkInt','?')}, {info.get('displayWidth','?')}x{info.get('displayHeight','?')})"
        )
    except Exception as e:
        logger.error(f"连接验证失败: {e}")
        return 3

    logger.info("设备初始化完成。可在 .env 中设置 AUTOMATOR_DEVICE_SERIAL 后启动平台。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
