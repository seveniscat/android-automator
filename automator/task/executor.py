"""任务执行器。

由于 uiautomator2 是同步阻塞的,本执行器使用 ThreadPoolExecutor
把同步 Flow 运行隔离到工作线程,主线程(FastAPI)异步派发。
"""

from __future__ import annotations

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Optional

from ..config import settings
from ..flow.runner import FlowRunner
from ..flow.yaml_loader import parse_flow
from ..logging import logger
from ..storage.repository import get_repository
from .states import TaskStatus


class Executor:
    """任务执行器(线程池)。"""

    def __init__(self, max_workers: Optional[int] = None) -> None:
        self._pool = ThreadPoolExecutor(
            max_workers=max_workers or settings.executor_workers,
            thread_name_prefix="automator-worker",
        )
        self._futures: dict[int, Future] = {}
        self._lock = threading.Lock()

    # ---- 同步入口(在工作线程中调用)----
    def _run_sync(self, task_id: int, run_id: int, yaml: str, variables: dict) -> None:
        repo = get_repository()
        try:
            flow = parse_flow(yaml)
            runner = FlowRunner()
            result = runner.run(flow, variables=variables)

            repo.finish_run(
                run_id,
                success=result.success,
                duration_ms=result.duration_ms,
                error=result.error or "",
                extracted_data=result.data,
                step_results=[
                    {
                        "step_name": r.step_name,
                        "step_type": r.step_type,
                        "success": r.success,
                        "duration_ms": r.duration_ms,
                        "screenshot_path": r.screenshot_path,
                        "detail": r.detail,
                        "error": r.error or "",
                        "extracted": r.extracted,
                    }
                    for r in result.steps
                ],
            )
            repo.update_task_status(task_id, TaskStatus.SUCCESS.value if result.success else TaskStatus.FAILED.value)
            logger.info(f"任务 {task_id} 运行结束 (run={run_id}): {'成功' if result.success else '失败'}")
        except Exception as e:
            logger.exception(f"任务 {task_id} 执行异常: {e}")
            repo.finish_run(
                run_id,
                success=False,
                duration_ms=0,
                error=f"{type(e).__name__}: {e}",
            )
            repo.update_task_status(task_id, TaskStatus.FAILED.value)
        finally:
            with self._lock:
                self._futures.pop(task_id, None)

    # ---- 异步入口(FastAPI 中调用)----
    async def submit_task(
        self,
        task_id: int,
        run_id: int,
        yaml: str,
        variables: Optional[dict] = None,
    ) -> None:
        """异步提交任务到线程池。"""
        loop = asyncio.get_running_loop()

        def on_done(fut: Future) -> None:
            if fut.exception():
                logger.error(f"task {task_id} 线程异常: {fut.exception()}")

        with self._lock:
            fut = self._pool.submit(self._run_sync, task_id, run_id, yaml, variables or {})
            fut.add_done_callback(on_done)
            self._futures[task_id] = fut
        logger.info(f"已派发任务 {task_id} (run={run_id}) 到线程池")

    def submit_task_sync(
        self,
        task_id: int,
        run_id: int,
        yaml: str,
        variables: Optional[dict] = None,
    ) -> None:
        """同步派发(阻塞直到提交完成,任务在工作线程异步执行)。"""
        with self._lock:
            fut = self._pool.submit(self._run_sync, task_id, run_id, yaml, variables or {})
            self._futures[task_id] = fut
        logger.info(f"已派发任务 {task_id} (run={run_id})")

    def is_running(self, task_id: int) -> bool:
        with self._lock:
            fut = self._futures.get(task_id)
            return fut is not None and not fut.done()

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait, cancel_futures=True)


_executor: Optional[Executor] = None


def get_executor() -> Executor:
    global _executor
    if _executor is None:
        _executor = Executor()
    return _executor
