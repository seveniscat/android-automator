#!/usr/bin/env python3
"""环境自检脚本。

用法:
    python scripts/doctor.py
"""

from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def check(label: str, ok: bool, detail: str = "") -> bool:
    mark = "✓" if ok else "✗"
    print(f"  {mark} {label}" + (f"  ({detail})" if detail else ""))
    return ok


def main() -> int:
    print("🔍 Automator 环境自检\n")

    all_ok = True

    # 1. Python 版本
    v = sys.version_info
    all_ok &= check(
        "Python 版本",
        v >= (3, 10),
        f"{v.major}.{v.minor}.{v.micro}",
    )

    # 2. adb 可执行
    adb_path = shutil.which("adb")
    all_ok &= check("adb 命令", adb_path is not None, adb_path or "未找到")

    # 3. adb 设备列表
    if adb_path:
        try:
            out = subprocess.run(
                ["adb", "devices"], capture_output=True, text=True, timeout=5
            ).stdout.strip()
            devices = [
                l.split()[0]
                for l in out.splitlines()[1:]
                if l.strip() and "device" in l
            ]
            all_ok &= check("已连接设备", len(devices) > 0, f"{len(devices)} 台: {devices}")
        except Exception as e:
            all_ok &= check("已连接设备", False, str(e))
    else:
        all_ok &= check("已连接设备", False, "跳过(无 adb)")

    # 4. 关键 Python 依赖
    for mod in ("uiautomator2", "fastapi", "sqlalchemy", "apscheduler", "yaml", "loguru"):
        try:
            m = importlib.import_module(mod)
            ver = getattr(m, "__version__", "")
            all_ok &= check(f"依赖 {mod}", True, ver)
        except ImportError:
            all_ok &= check(f"依赖 {mod}", False, "未安装")

    # 5. atx-agent(尝试连接默认设备)
    try:
        import uiautomator2 as u2

        d = u2.connect()
        info = d.info
        all_ok &= check(
            "atx-agent 可达",
            True,
            f"{info.get('productName','?')} / atx={info.get('atxAgentVersion','?')}",
        )
    except Exception as e:
        all_ok &= check("atx-agent 可达", False, str(e)[:80])

    # 6. 目录可写
    try:
        data = Path("data")
        data.mkdir(exist_ok=True)
        (data / ".write_test").write_text("ok", encoding="utf-8")
        (data / ".write_test").unlink()
        all_ok &= check("data/ 目录可写", True)
    except Exception as e:
        all_ok &= check("data/ 目录可写", False, str(e))

    print()
    if all_ok:
        print("✅ 全部检查通过,可启动平台:  uvicorn automator.main:app")
        return 0
    print("⚠️  存在未通过项,请按提示修复后重试")
    return 1


if __name__ == "__main__":
    sys.exit(main())
