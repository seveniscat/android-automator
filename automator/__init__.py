"""Automator —— 基于 uiautomator2 的 Android 真机自动化平台。

分层架构(自下而上):
    device        设备抽象层(本期:U2Device + SingleDeviceManager)
    perception    感知层(截图 / OCR* / VLM*)
    action        动作层(click / swipe / input ...)
    cognition     决策层(规则引擎 / LLM Planner*)
    flow          流程编排层(YAML DSL + Runner + Steps)
    task          任务/调度层(Executor + Scheduler)
    storage       数据层(SQLAlchemy)
    api           API 层(FastAPI)

带 * 的为预留接口,本期只定义不实现。
"""

__version__ = "0.1.0"
