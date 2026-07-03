"""loguru 日志配置。"""

from __future__ import annotations

import sys

from loguru import logger

from .config import settings

_configured = False


def setup_logging() -> None:
    """初始化全局 loguru 日志。幂等,可重复调用。"""
    global _configured
    if _configured:
        return

    logger.remove()
    level = settings.log_level.upper()

    # 控制台:彩色 + 时间 + 模块
    logger.add(
        sys.stderr,
        level=level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> "
            "<level>{level: <7}</level> "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # 文件:按天滚动,保留 7 天
    logger.add(
        "data/run.log",
        level=level,
        rotation="00:00",
        retention="7 days",
        encoding="utf-8",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} {level: <7} "
            "{name}:{function}:{line} - {message}"
        ),
    )

    _configured = True


__all__ = ["setup_logging", "logger"]
