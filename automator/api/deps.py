"""FastAPI 依赖注入。"""

from __future__ import annotations

from ..device.manager import DeviceManager, get_device_manager
from ..storage.repository import Repository, get_repository
from ..task.executor import Executor, get_executor
from ..task.scheduler import Scheduler, get_scheduler


def get_repo() -> Repository:
    return get_repository()


def get_dm() -> DeviceManager:
    return get_device_manager()


def get_exec() -> Executor:
    return get_executor()


def get_sched() -> Scheduler:
    return get_scheduler()
