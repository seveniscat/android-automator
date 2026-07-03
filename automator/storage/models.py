"""数据库模型。"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


class Base(DeclarativeBase):
    pass


class DeviceRecord(Base):
    """已纳管的设备(信息缓存)。"""

    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    serial: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    model: Mapped[str] = mapped_column(String(128), default="")
    brand: Mapped[str] = mapped_column(String(64), default="")
    android_version: Mapped[str] = mapped_column(String(16), default="")
    resolution: Mapped[str] = mapped_column(String(32), default="")
    last_seen_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class FlowRecord(Base):
    """已保存的流程定义。"""

    __tablename__ = "flows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    yaml_content: Mapped[str] = mapped_column(Text)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now, onupdate=_now)


class TaskRecord(Base):
    """任务(对一次"待执行"的描述)。"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    flow_id: Mapped[int | None] = mapped_column(ForeignKey("flows.id"), nullable=True)
    flow_name: Mapped[str] = mapped_column(String(128), default="")
    flow_yaml: Mapped[str] = mapped_column(Text, default="")  # 冗余,防止 flow 被删
    variables: Mapped[dict] = mapped_column(JSON, default=dict)
    device_serial: Mapped[str] = mapped_column(String(64), default="")
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    schedule: Mapped[str] = mapped_column(String(64), default="")  # cron / interval

    runs: Mapped[list["RunRecord"]] = relationship(back_populates="task")


class RunRecord(Base):
    """一次流程执行。"""

    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_id: Mapped[int] = mapped_column(ForeignKey("tasks.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="running")
    success: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default="")
    extracted_data: Mapped[dict] = mapped_column(JSON, default=dict)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=_now)
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    task: Mapped[TaskRecord] = relationship(back_populates="runs")
    step_results: Mapped[list["StepResultRecord"]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class StepResultRecord(Base):
    """单步执行结果。"""

    __tablename__ = "step_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("runs.id"), index=True)
    index: Mapped[int] = mapped_column(Integer, default=0)
    step_name: Mapped[str] = mapped_column(String(128), default="")
    step_type: Mapped[str] = mapped_column(String(32), default="")
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    screenshot_path: Mapped[str] = mapped_column(String(256), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    error: Mapped[str] = mapped_column(Text, default="")
    extracted: Mapped[Any] = mapped_column(JSON, default=None)

    run: Mapped[RunRecord] = relationship(back_populates="step_results")
