"""定时调度器(APScheduler 封装)。

支持 cron 与 interval 两种触发,把命中的 task 投递给 Executor。
本期提供 API,具体定时面板在后续迭代完善。
"""

from __future__ import annotations

from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from ..logging import logger
from ..storage.repository import get_repository
from .executor import get_executor


class Scheduler:
    """APScheduler 封装。

    通过 `schedule_task(task_id, kind, **kwargs)` 给已存在的 Task 加定时:
        kind="interval", seconds=60
        kind="cron", hour=8, minute=0
    """

    def __init__(self) -> None:
        self._sched = BackgroundScheduler(daemon=True)

    def start(self) -> None:
        if not self._sched.running:
            self._sched.start()
            logger.info("调度器已启动")

    def shutdown(self, wait: bool = False) -> None:
        if self._sched.running:
            self._sched.shutdown(wait=wait)

    def schedule_task(
        self,
        task_id: int,
        kind: str = "interval",
        **trigger_kwargs,
    ) -> str:
        """给 task 添加定时。返回 job_id。"""
        repo = get_repository()
        task = repo.get_task(task_id)
        if not task:
            raise ValueError(f"任务不存在: {task_id}")

        if kind == "cron":
            trigger = CronTrigger(**trigger_kwargs)
        else:
            trigger = IntervalTrigger(**trigger_kwargs)

        job = self._sched.add_job(
            self._fire,
            trigger=trigger,
            args=[task_id],
            id=f"task-{task_id}",
            replace_existing=True,
        )
        logger.info(f"已为任务 {task_id} 设置定时 ({kind}): {job.id}")
        return job.id

    def unschedule(self, task_id: int) -> bool:
        try:
            self._sched.remove_job(f"task-{task_id}")
            return True
        except Exception:
            return False

    def list_jobs(self) -> list[dict]:
        jobs = []
        for j in self._sched.get_jobs():
            jobs.append({
                "id": j.id,
                "next_run": str(j.next_run_time) if j.next_run_time else None,
                "trigger": str(j.trigger),
            })
        return jobs

    # ---- 内部 ----
    def _fire(self, task_id: int) -> None:
        repo = get_repository()
        task = repo.get_task(task_id)
        if not task:
            logger.warning(f"定时触发取消: 任务 {task_id} 不存在")
            return
        run = repo.create_run(task_id)
        logger.info(f"定时触发任务 {task_id}, 创建 run={run.id}")
        get_executor().submit_task_sync(
            task_id=task_id,
            run_id=run.id,
            yaml=task.flow_yaml,
            variables=task.variables or {},
        )


_scheduler: Optional[Scheduler] = None


def get_scheduler() -> Scheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler()
    return _scheduler
