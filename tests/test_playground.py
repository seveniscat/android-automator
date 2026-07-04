"""Playground 路由测试(使用 FastAPI TestClient,mock 设备)。"""

from __future__ import annotations

import contextlib
import os
import tempfile
from unittest.mock import patch

_tmp = tempfile.mkdtemp(prefix="automator_pg_test_")
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


class _FakeDev:
    """假设备:记录最近一次调用。"""

    def __init__(self):
        self.last = None
        # U2Actions.swipe_direction 访问 device.info.resolution
        from automator.device.base import DeviceInfo
        self.info = DeviceInfo(serial="fake", resolution=(1080, 1920))

    def click(self, x, y):
        self.last = ("click", x, y)

    def swipe(self, x1, y1, x2, y2, duration=0.3):
        self.last = ("swipe", x1, y1, x2, y2, duration)

    def input_text(self, text):
        self.last = ("input", text)

    def press(self, key):
        self.last = ("press", key)

    def start_app(self, package, activity=None):
        self.last = ("start_app", package, activity)

    def stop_app(self, package):
        self.last = ("stop_app", package)

    def click_element(self, **kwargs):
        self.last = ("click_element", kwargs)
        return True

    def is_alive(self):
        return True


class _FakeDM:
    def __init__(self, dev):
        self._dev = dev

    def get_device(self):
        return self._dev


@pytest.fixture
def fake_device():
    dev = _FakeDev()
    dm = _FakeDM(dev)
    with patch("automator.api.routes.playground.DeviceManager", autospec=True) as MockDM:
        MockDM.return_value = dm
        # Depends(get_dm) 返回 dm 实例
        from automator.api.routes import playground as pg_mod
        with patch.object(pg_mod, "_build_actions") as ba:
            from automator.action.u2_actions import U2Actions
            ba.return_value = U2Actions(device=dev, humanize=False)
            yield dev


# ---- 用例 ----
def test_list_actions(client):
    r = client.get("/api/playground/actions")
    assert r.status_code == 200
    names = {a["name"] for a in r.json()["actions"]}
    assert {"click", "swipe", "press", "input_text", "start_app"}.issubset(names)


def test_run_click(client, fake_device):
    r = client.post(
        "/api/playground/action",
        json={"action": "click", "params": {"x": 100, "y": 200}},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["success"] is True
    assert data["action"] == "click"
    assert data["shot_at"] > 0
    assert fake_device.last == ("click", 100, 200)


def test_run_press(client, fake_device):
    r = client.post(
        "/api/playground/action",
        json={"action": "press", "params": {"key": "back"}},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "press"
    assert fake_device.last == ("press", "back")


def test_run_input_text(client, fake_device):
    r = client.post(
        "/api/playground/action",
        json={"action": "input_text", "params": {"text": "hello"}},
    )
    assert r.status_code == 200
    assert fake_device.last == ("input", "hello")


def test_run_swipe_direction(client, fake_device):
    r = client.post(
        "/api/playground/action",
        json={"action": "swipe_direction", "params": {"direction": "up"}},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "swipe"
    # up: y 从大→小
    assert isinstance(fake_device.last, tuple) and fake_device.last[0] == "swipe"
    _, _x1, y1, _x2, y2, _dur = fake_device.last
    assert y1 > y2


def test_unsupported_action(client, fake_device):
    """不支持的动作名应返回 400。"""
    r = client.post(
        "/api/playground/action",
        json={"action": "hack_the_planet", "params": {}},
    )
    assert r.status_code == 400


def test_start_app(client, fake_device):
    r = client.post(
        "/api/playground/action",
        json={"action": "start_app", "params": {"package": "com.example"}},
    )
    assert r.status_code == 200
    assert r.json()["action"] == "start_app"
    assert fake_device.last == ("start_app", "com.example", None)


def test_device_not_connected(client):
    """设备未连接时返回 503。"""
    from automator.device.exceptions import DeviceNotFoundError

    def _raise(*a, **k):
        raise DeviceNotFoundError("nope")

    with patch("automator.api.routes.playground._build_actions", side_effect=_raise):
        r = client.post(
            "/api/playground/action",
            json={"action": "click", "params": {"x": 1, "y": 1}},
        )
        assert r.status_code == 503
        assert "设备未连接" in r.json()["detail"]
