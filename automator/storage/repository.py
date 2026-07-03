"""仓储层:封装常用 CRUD。"""

from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..logging import logger
from .db import get_session, init_db
from .models import (
    DeviceRecord,
    FlowRecord,
    RunRecord,
    StepResultRecord,
    TaskRecord,
)


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Repository:
    """数据访问仓储。

    所有方法内部管理 session,调用方无需关心事务。
    """

    def __init__(self, ensure_schema: bool = True) -> None:
        if ensure_schema:
            init_db()

    # ---- Flow ----
    def save_flow(
        self,
        name: str,
        yaml_content: str,
        description: str = "",
        tags: Optional[list] = None,
        variables: Optional[dict] = None,
    ) -> FlowRecord:
        with get_session() as s:
            existing = s.scalar(select(FlowRecord).where(FlowRecord.name == name))
            if existing:
                existing.yaml_content = yaml_content
                existing.description = description
                existing.tags = tags or []
                existing.variables = variables or {}
                existing.updated_at = _now()
                s.flush()
                rec = existing
            else:
                rec = FlowRecord(
                    name=name,
                    yaml_content=yaml_content,
                    description=description,
                    tags=tags or [],
                    variables=variables or {},
                )
                s.add(rec)
                s.flush()
            return self._detach(s, rec)

    def get_flow(self, flow_id: int) -> Optional[FlowRecord]:
        with get_session() as s:
            rec = s.get(FlowRecord, flow_id)
            return self._detach(s, rec)

    def list_flows(self) -> list[FlowRecord]:
        with get_session() as s:
            return list(s.scalars(select(FlowRecord).order_by(FlowRecord.updated_at.desc())))

    def delete_flow(self, flow_id: int) -> bool:
        with get_session() as s:
            rec = s.get(FlowRecord, flow_id)
            if rec:
                s.delete(rec)
                return True
            return False

    # ---- Task ----
    def create_task(
        self,
        flow_id: Optional[int],
        flow_name: str,
        flow_yaml: str,
        variables: Optional[dict] = None,
        device_serial: str = "",
        schedule: str = "",
    ) -> TaskRecord:
        with get_session() as s:
            rec = TaskRecord(
                flow_id=flow_id,
                flow_name=flow_name,
                flow_yaml=flow_yaml,
                variables=variables or {},
                device_serial=device_serial,
                status="pending",
                schedule=schedule,
            )
            s.add(rec)
            s.flush()
            return self._detach(s, rec)

    def get_task(self, task_id: int) -> Optional[TaskRecord]:
        with get_session() as s:
            return self._detach(s, s.get(TaskRecord, task_id))

    def list_tasks(self, limit: int = 100) -> list[TaskRecord]:
        with get_session() as s:
            stmt = select(TaskRecord).order_by(TaskRecord.created_at.desc()).limit(limit)
            return list(s.scalars(stmt))

    def update_task_status(self, task_id: int, status: str) -> None:
        with get_session() as s:
            rec = s.get(TaskRecord, task_id)
            if rec:
                rec.status = status

    # ---- Run ----
    def create_run(self, task_id: int) -> RunRecord:
        with get_session() as s:
            rec = RunRecord(task_id=task_id, status="running")
            s.add(rec)
            s.flush()
            return self._detach(s, rec)

    def finish_run(
        self,
        run_id: int,
        *,
        success: bool,
        duration_ms: int,
        error: str = "",
        extracted_data: Optional[dict] = None,
        step_results: Optional[list[dict]] = None,
    ) -> None:
        with get_session() as s:
            rec = s.get(RunRecord, run_id)
            if not rec:
                return
            rec.status = "success" if success else "failed"
            rec.success = success
            rec.duration_ms = duration_ms
            rec.error = error
            rec.extracted_data = extracted_data or {}
            rec.finished_at = _now()
            if step_results:
                for i, sr in enumerate(step_results):
                    s.add(
                        StepResultRecord(
                            run_id=run_id,
                            index=i,
                            step_name=sr.get("step_name", ""),
                            step_type=sr.get("step_type", ""),
                            success=sr.get("success", False),
                            duration_ms=sr.get("duration_ms", 0),
                            screenshot_path=sr.get("screenshot_path", "") or "",
                            detail=sr.get("detail", ""),
                            error=sr.get("error", ""),
                            extracted=sr.get("extracted"),
                        )
                    )

    def list_runs(self, task_id: Optional[int] = None, limit: int = 50) -> list[RunRecord]:
        with get_session() as s:
            stmt = select(RunRecord).order_by(RunRecord.started_at.desc())
            if task_id is not None:
                stmt = stmt.where(RunRecord.task_id == task_id)
            stmt = stmt.limit(limit)
            return list(s.scalars(stmt))

    def get_run(self, run_id: int) -> Optional[RunRecord]:
        with get_session() as s:
            return self._detach(s, s.get(RunRecord, run_id))

    def get_step_results(self, run_id: int) -> list[StepResultRecord]:
        with get_session() as s:
            stmt = (
                select(StepResultRecord)
                .where(StepResultRecord.run_id == run_id)
                .order_by(StepResultRecord.index)
            )
            return list(s.scalars(stmt))

    # ---- Device ----
    def upsert_device(self, serial: str, **info) -> DeviceRecord:
        with get_session() as s:
            rec = s.scalar(select(DeviceRecord).where(DeviceRecord.serial == serial))
            data = {
                "model": info.get("model", ""),
                "brand": info.get("brand", ""),
                "android_version": info.get("android_version", ""),
                "resolution": info.get("resolution", ""),
                "last_seen_at": _now(),
            }
            if rec:
                for k, v in data.items():
                    setattr(rec, k, v)
            else:
                rec = DeviceRecord(serial=serial, **data)
                s.add(rec)
            s.flush()
            return self._detach(s, rec)

    def list_devices(self) -> list[DeviceRecord]:
        with get_session() as s:
            return list(s.scalars(select(DeviceRecord)))

    # ---- 内部 ----
    @staticmethod
    def _detach(session: Session, obj):
        """从 session 中 detach 后返回,使对象可在 with 块外使用。"""
        if obj is None:
            return None
        session.expunge(obj)
        return obj


_repository: Optional[Repository] = None


def get_repository() -> Repository:
    global _repository
    if _repository is None:
        _repository = Repository()
    return _repository
