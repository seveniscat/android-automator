"""录制器(进程级单例)。

在 Playground 里开启录制后,每次成功操作都被翻译成 YAML 步骤并暂存;
停止后可预览生成的 YAML,再通过 `POST /api/flows` 保存为 Flow。

设计要点:
    - 与 StreamHub 同构的进程级单例,状态仅存内存,重启即清空
      —— 贴合 Playground「不落库」的探索/调试定位。
    - 单一拦截点:Playground 所有操作都走 `run_action`,在那埋点即可。
    - 失败动作默认丢弃(可关),避免把失效步骤写进流程。
    - `to_yaml` 输出与 `flow.yaml_loader.parse_flow` 输入兼容,可直接喂给流程 CRUD。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import yaml

from .logging import logger

# YAML click 步骤接受的定位器键(与 click_by 参数一一对应)
_CLICK_BY_KEYS = ("resource_id", "text", "text_contains", "content_desc", "xpath")


@dataclass
class RecordedStep:
    """一条已录制步骤(供展示 + 生成 YAML)。"""

    type: str            # YAML 步骤类型:click / swipe / input / press / start_app / stop_app
    params: dict         # 步骤参数(可直接作为 YAML step 的 value)
    action_target: str   # 展示用的目标描述,如 "(100,200)" / "text='登录'"
    success: bool = True
    ts: float = 0.0


class Recorder:
    """录制状态机(进程级单例,通过 `get_recorder()` 获取)。"""

    def __init__(self) -> None:
        self.active: bool = False
        self.name: str = ""
        self.started_at: float = 0.0
        self.steps: list[RecordedStep] = []
        # 失败动作默认丢弃,避免把失效步骤写进流程
        self.skip_failed: bool = True

    # ---- 生命周期 ----
    def start(self, name: str = "") -> None:
        """开始(或继续)录制。"""
        if not self.active:
            self.steps = []
            self.started_at = time.time()
        self.name = name or self.name or f"录制_{time.strftime('%Y%m%d_%H%M%S')}"
        self.active = True
        logger.info(f"录制开始: {self.name}")

    def stop(self) -> int:
        """停止录制,返回已录步骤数。"""
        was = self.active
        self.active = False
        if was:
            logger.info(f"录制停止: {self.name}({len(self.steps)} 步)")
        return len(self.steps)

    def reset(self) -> None:
        """清空已录步骤并停止。"""
        self.active = False
        self.steps = []
        self.name = ""
        self.started_at = 0.0

    # ---- 录制 ----
    def record(
        self,
        action: str,
        params: dict,
        success: bool,
        locator: dict | None = None,
    ) -> RecordedStep | None:
        """把一次 Playground 动作翻译成 YAML 步骤并暂存。

        action:   playground 动作名(click / click_by / swipe / swipe_direction /
                  input_text / press / start_app / stop_app)
        params:   原始动作参数(透传给 U2Actions 的参数)
        success:  动作是否成功
        locator:  仅对 click 动作有效 —— 智能定位结果(如 {"text":"登录"}),
                  命中则记为元素点击,否则回退坐标。

        返回 RecordedStep;若动作不可录制或被过滤(失败动作)则返回 None。
        """
        translated = _translate(action, params, locator)
        if translated is None:
            return None  # 不支持录制的动作

        step_type, step_params, target = translated
        step = RecordedStep(
            type=step_type,
            params=step_params,
            action_target=target,
            success=success,
            ts=time.time(),
        )

        if not success and self.skip_failed:
            logger.debug(f"录制丢弃失败动作: {action} {target}")
            return None

        self.steps.append(step)
        return step

    # ---- 输出 ----
    def snapshot(self) -> dict:
        """当前录制状态 + 步骤列表(供前端轮询)。"""
        return {
            "active": self.active,
            "name": self.name,
            "started_at": self.started_at,
            "step_count": len(self.steps),
            "steps": [
                {
                    "index": i,
                    "type": s.type,
                    "params": s.params,
                    "target": s.action_target,
                    "success": s.success,
                }
                for i, s in enumerate(self.steps)
            ],
        }

    def to_yaml(self, name: str = "") -> str:
        """生成 YAML 文本(与 yaml_loader.parse_flow 输入兼容)。"""
        flow_name = name or self.name or "录制流程"
        data = {
            "name": flow_name,
            "description": f"由录制生成({len(self.steps)} 步)",
            "steps": [{s.type: s.params} for s in self.steps],
        }
        return yaml.safe_dump(data, allow_unicode=True, sort_keys=False)

    def remove_step(self, index: int) -> bool:
        """删除指定下标的步骤,返回是否删除成功。"""
        if 0 <= index < len(self.steps):
            self.steps.pop(index)
            return True
        return False


# ---- 动作 → YAML 步骤翻译 ----
def _translate(
    action: str,
    params: dict,
    locator: dict | None,
) -> tuple[str, dict, str] | None:
    """把 playground 动作翻译成 (step_type, step_params, target)。

    返回 None 表示该动作不录制(目前仅 click/click_by/swipe/swipe_direction/
    input_text/press/start_app/stop_app 可录)。
    """
    if action == "click":
        # 智能定位命中 → 元素点击;否则坐标点击
        if locator:
            key, val = next(iter(locator.items()))
            return "click", dict(locator), f"{key}={val!r}"
        x, y = int(params.get("x", 0)), int(params.get("y", 0))
        return "click", {"x": x, "y": y}, f"({x},{y})"

    if action == "click_by":
        loc = {k: params[k] for k in _CLICK_BY_KEYS if params.get(k)}
        if not loc:
            return None  # 没有任何定位器,无法生成有意义的步骤
        key, val = next(iter(loc.items()))
        # 带上 timeout(若非默认 5s)
        step_params = dict(loc)
        if "timeout" in params and float(params.get("timeout", 5.0)) != 5.0:
            step_params["timeout"] = params["timeout"]
        return "click", step_params, f"{key}={val!r}"

    if action == "swipe_direction":
        direction = params.get("direction", "")
        step_params = {"direction": direction}
        if float(params.get("scale", 0.5)) != 0.5:
            step_params["scale"] = float(params["scale"])
        return "swipe", step_params, direction

    if action == "swipe":
        step_params = {
            "x1": int(params["x1"]), "y1": int(params["y1"]),
            "x2": int(params["x2"]), "y2": int(params["y2"]),
        }
        if float(params.get("duration", 0.3)) != 0.3:
            step_params["duration"] = float(params["duration"])
        return "swipe", step_params, (
            f"({step_params['x1']},{step_params['y1']})->"
            f"({step_params['x2']},{step_params['y2']})"
        )

    if action == "input_text":
        text = params.get("text", "")
        step_params: dict = {"text": str(text)}
        if params.get("clear"):
            step_params["clear"] = True
        return "input", step_params, f"text={text!r}"

    if action == "press":
        key = params.get("key", "")
        return "press", {"key": key}, str(key)

    if action == "start_app":
        pkg = params.get("package", "")
        step_params = {"package": pkg}
        if params.get("activity"):
            step_params["activity"] = params["activity"]
        target = f"{pkg}/{params['activity']}" if params.get("activity") else str(pkg)
        return "start_app", step_params, target

    if action == "stop_app":
        pkg = params.get("package", "")
        return "stop_app", {"package": pkg}, str(pkg)

    return None


# ---- 单例 ----
_recorder: Recorder | None = None


def get_recorder() -> Recorder:
    """获取进程级 Recorder 单例。"""
    global _recorder
    if _recorder is None:
        _recorder = Recorder()
    return _recorder
