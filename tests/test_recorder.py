"""录制器测试:Recorder 单元 + 智能定位 + API 端到端。"""

from __future__ import annotations

import contextlib
import os
import tempfile
from unittest.mock import patch

_tmp = tempfile.mkdtemp(prefix="automator_rec_test_")
os.environ["AUTOMATOR_DB_URL"] = f"sqlite:///{_tmp}/test.db"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


@contextlib.asynccontextmanager
async def _noop_lifespan(app):
    yield


@pytest.fixture(scope="module")
def client():
    from automator.main import create_app

    app = create_app()
    app.router.lifespan_context = _noop_lifespan
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def fresh_recorder():
    """每个用例都拿到干净的录制器单例。"""
    from automator.recorder import get_recorder

    rec = get_recorder()
    rec.reset()
    yield rec
    rec.reset()


# ============================================================
# Recorder 单元测试
# ============================================================
class TestRecorderUnit:
    def test_lifecycle(self, fresh_recorder):
        rec = fresh_recorder
        assert rec.active is False
        rec.start("我的录制")
        assert rec.active is True
        assert rec.name == "我的录制"
        assert rec.started_at > 0
        count = rec.stop()
        assert rec.active is False
        assert count == 0

    def test_start_clears_old_steps(self, fresh_recorder):
        rec = fresh_recorder
        rec.start("a")
        rec.record("press", {"key": "back"}, True)
        assert len(rec.steps) == 1
        # 重新开始(从非 active 状态)应清空
        rec.stop()
        rec.start("b")
        assert len(rec.steps) == 0

    def test_record_click_with_locator(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        step = rec.record("click", {"x": 100, "y": 200}, True, locator={"text": "登录"})
        assert step is not None
        assert step.type == "click"
        assert step.params == {"text": "登录"}
        assert step.action_target == "text='登录'"

    def test_record_click_without_locator_falls_back_to_coords(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        step = rec.record("click", {"x": 50, "y": 60}, True, locator=None)
        assert step.type == "click"
        assert step.params == {"x": 50, "y": 60}
        assert step.action_target == "(50,60)"

    def test_record_click_by(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        step = rec.record(
            "click_by",
            {"resource_id": "com.x/.btn", "text": "确定", "timeout": 5.0},
            True,
        )
        # resource_id 和 text 都给了,翻译保留两个定位键
        assert step.type == "click"
        assert step.params["resource_id"] == "com.x/.btn"
        assert step.params["text"] == "确定"
        # 默认 timeout 5.0 不写进步骤
        assert "timeout" not in step.params

    def test_record_click_by_no_locator_returns_none(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        assert rec.record("click_by", {}, True) is None

    def test_record_swipe_direction(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        step = rec.record("swipe_direction", {"direction": "up", "scale": 0.5}, True)
        assert step.type == "swipe"
        assert step.params == {"direction": "up"}
        # 非默认 scale 才写入
        step2 = rec.record("swipe_direction", {"direction": "down", "scale": 0.7}, True)
        assert step2.params == {"direction": "down", "scale": 0.7}

    def test_record_swipe_coords(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        step = rec.record(
            "swipe", {"x1": 1, "y1": 2, "x2": 3, "y2": 4, "duration": 0.3}, True
        )
        assert step.type == "swipe"
        assert step.params == {"x1": 1, "y1": 2, "x2": 3, "y2": 4}

    def test_record_input_text(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        step = rec.record("input_text", {"text": "hello", "clear": True}, True)
        assert step.type == "input"
        assert step.params == {"text": "hello", "clear": True}

    def test_record_press_and_apps(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        assert rec.record("press", {"key": "back"}, True).type == "press"
        s = rec.record("start_app", {"package": "com.x", "activity": ".Main"}, True)
        assert s.type == "start_app"
        assert s.params == {"package": "com.x", "activity": ".Main"}
        assert rec.record("stop_app", {"package": "com.x"}, True).type == "stop_app"

    def test_failed_action_skipped_by_default(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        assert rec.record("press", {"key": "back"}, success=False) is None
        assert len(rec.steps) == 0

    def test_failed_action_kept_when_skip_disabled(self, fresh_recorder):
        rec = fresh_recorder
        rec.skip_failed = False
        rec.start()
        step = rec.record("press", {"key": "back"}, success=False)
        assert step is not None
        assert step.success is False

    def test_unknown_action_not_recorded(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        assert rec.record("hack", {}, True) is None

    def test_to_yaml_parses_back(self, fresh_recorder):
        from automator.flow.yaml_loader import parse_flow

        rec = fresh_recorder
        rec.start("登录流程")
        rec.record("start_app", {"package": "com.example"}, True)
        rec.record("click", {"x": 10, "y": 20}, True, locator={"text": "登录"})
        rec.record("input_text", {"text": "alice"}, True)
        rec.record("press", {"key": "enter"}, True)

        yaml_text = rec.to_yaml()
        # 生成的 YAML 必须能被 parse_flow 解析回来
        flow = parse_flow(yaml_text)
        assert flow.name == "登录流程"
        assert len(flow.steps) == 4
        assert flow.steps[0].type == "start_app"
        assert flow.steps[1].type == "click"
        assert flow.steps[1].params == {"text": "登录"}
        assert flow.steps[2].type == "input"
        assert flow.steps[3].type == "press"

    def test_snapshot_and_remove_step(self, fresh_recorder):
        rec = fresh_recorder
        rec.start()
        rec.record("press", {"key": "back"}, True)
        rec.record("press", {"key": "home"}, True)
        snap = rec.snapshot()
        assert snap["active"] is True
        assert snap["step_count"] == 2
        assert snap["steps"][0]["type"] == "press"
        # 删除第 0 个
        assert rec.remove_step(0) is True
        assert len(rec.steps) == 1
        assert rec.steps[0].params == {"key": "home"}
        assert rec.remove_step(99) is False


# ============================================================
# 智能定位测试
# ============================================================
class _FakeDev:
    """携带一份 mock UI XML 的假设备。"""

    SAMPLE_XML = """<?xml version='1.0' encoding='UTF-8'?>
<hierarchy>
  <node bounds="[0,0][1000,2000]">
    <node resource-id="com.x/.root" bounds="[0,0][1000,2000]">
      <node text="登录" content-desc="" clickable="true" bounds="[100,100][300,200]" />
      <node content-desc="返回" clickable="true" bounds="[10,10][90,90]" />
      <node resource-id="com.x/.icon" bounds="[500,500][600,600]" />
    </node>
  </node>
</hierarchy>"""

    def __init__(self, xml: str | None = None):
        self._xml = xml if xml is not None else self.SAMPLE_XML

    def dump_hierarchy(self):
        return self._xml


class TestLocator:
    def test_hits_text(self):
        from automator.locator import resolve_click_locator

        # 点中 "登录" 按钮中心 (200,150)
        loc = resolve_click_locator(_FakeDev(), 200, 150)
        assert loc == {"text": "登录"}

    def test_hits_content_desc(self):
        from automator.locator import resolve_click_locator

        # 点中 "返回" (50,50),content_desc 优先级高于其他
        loc = resolve_click_locator(_FakeDev(), 50, 50)
        assert loc == {"content_desc": "返回"}

    def test_hits_resource_id(self):
        from automator.locator import resolve_click_locator

        # 点中只有 resource_id 的图标 (550,550)
        loc = resolve_click_locator(_FakeDev(), 550, 550)
        assert loc == {"resource_id": "com.x/.icon"}

    def test_picks_deepest_smallest(self):
        from automator.locator import resolve_click_locator

        # 点在 "登录" 区域:它比外层 root 更小(更精确),应选 "登录"
        loc = resolve_click_locator(_FakeDev(), 200, 150)
        assert loc == {"text": "登录"}  # 不是外层 root 的 resource_id

    def test_no_hit_returns_none(self):
        from automator.locator import resolve_click_locator

        # 点在空白区域(没有任何节点覆盖)
        loc = resolve_click_locator(_FakeDev(), 9999, 9999)
        assert loc is None

    def test_dump_failure_returns_none(self):
        from automator.locator import resolve_click_locator

        class Boom(_FakeDev):
            def dump_hierarchy(self):
                raise RuntimeError("device gone")

        assert resolve_click_locator(Boom(), 1, 1) is None

    def test_malformed_xml_returns_none(self):
        from automator.locator import resolve_click_locator

        assert resolve_click_locator(_FakeDev(xml="not xml"), 1, 1) is None


# ============================================================
# 录制 API + playground 埋点端到端
# ============================================================
class _PgFakeDev:
    """playground 埋点测试用的假设备。"""

    def __init__(self):
        self.last = None
        from automator.device.base import DeviceInfo
        self.info = DeviceInfo(serial="fake", resolution=(1080, 1920))

    def click(self, x, y):
        self.last = ("click", x, y)

    def dump_hierarchy(self):
        return _FakeDev.SAMPLE_XML

    def click_element(self, **kwargs):
        self.last = ("click_element", kwargs)
        return True

    def input_text(self, text):
        self.last = ("input", text)

    def press(self, key):
        self.last = ("press", key)

    def swipe(self, x1, y1, x2, y2, duration=0.3):
        self.last = ("swipe", x1, y1, x2, y2, duration)

    def start_app(self, package, activity=None):
        self.last = ("start_app", package, activity)

    def stop_app(self, package):
        self.last = ("stop_app", package)

    def is_alive(self):
        return True


class TestRecorderAPI:
    @pytest.fixture
    def fake_device(self):
        dev = _PgFakeDev()
        from automator.action.u2_actions import U2Actions
        from automator.api.routes import playground as pg_mod

        with patch.object(pg_mod, "_build_actions") as ba:
            ba.return_value = U2Actions(device=dev, humanize=False)
            yield dev

    def test_start_stop_state(self, client):
        r = client.post("/api/recorder/start", json={"name": "t1"})
        assert r.status_code == 200
        assert r.json()["active"] is True
        assert r.json()["name"] == "t1"

        r = client.get("/api/recorder/state")
        assert r.json()["active"] is True

        r = client.post("/api/recorder/stop")
        assert r.json()["active"] is False
        assert r.json()["step_count"] == 0

    def test_playground_action_recorded_when_active(self, client, fake_device):
        # 开启录制
        client.post("/api/recorder/start", json={"name": "cap"})
        # 执行一个 press 动作
        r = client.post(
            "/api/playground/action",
            json={"action": "press", "params": {"key": "back"}},
        )
        assert r.status_code == 200
        # 已录步骤应包含一条 press
        snap = client.get("/api/recorder/state").json()
        assert snap["step_count"] == 1
        assert snap["steps"][0]["type"] == "press"

    def test_playground_action_not_recorded_when_inactive(self, client, fake_device):
        r = client.post(
            "/api/playground/action",
            json={"action": "press", "params": {"key": "home"}},
        )
        assert r.status_code == 200
        snap = client.get("/api/recorder/state").json()
        assert snap["step_count"] == 0

    def test_click_smart_locator(self, client, fake_device):
        client.post("/api/recorder/start", json={"name": "click"})
        # 点 (200,150) 命中 "登录" → 录成元素点击
        r = client.post(
            "/api/playground/action",
            json={"action": "click", "params": {"x": 200, "y": 150}, "smart_locator": True},
        )
        assert r.status_code == 200
        snap = client.get("/api/recorder/state").json()
        assert snap["steps"][0]["type"] == "click"
        assert snap["steps"][0]["params"] == {"text": "登录"}

    def test_click_smart_locator_disabled_falls_back_to_coords(self, client, fake_device):
        client.post("/api/recorder/start", json={"name": "click"})
        r = client.post(
            "/api/playground/action",
            json={"action": "click", "params": {"x": 200, "y": 150}, "smart_locator": False},
        )
        assert r.status_code == 200
        snap = client.get("/api/recorder/state").json()
        assert snap["steps"][0]["params"] == {"x": 200, "y": 150}

    def test_yaml_endpoint_and_remove_step(self, client, fake_device):
        client.post("/api/recorder/start", json={"name": "yaml"})
        client.post(
            "/api/playground/action",
            json={"action": "press", "params": {"key": "back"}},
        )
        client.post(
            "/api/playground/action",
            json={"action": "press", "params": {"key": "home"}},
        )
        r = client.get("/api/recorder/yaml?name=自定义")
        data = r.json()
        assert "name: 自定义" in data["yaml"]
        assert "press:" in data["yaml"]
        # 删除第 0 步
        r = client.delete("/api/recorder/step/0")
        assert r.json()["ok"] is True
        assert client.get("/api/recorder/state").json()["step_count"] == 1

    def test_reset(self, client, fake_device):
        client.post("/api/recorder/start")
        client.post(
            "/api/playground/action",
            json={"action": "press", "params": {"key": "back"}},
        )
        r = client.post("/api/recorder/reset")
        assert r.json()["step_count"] == 0
        assert client.get("/api/recorder/state").json()["active"] is False
