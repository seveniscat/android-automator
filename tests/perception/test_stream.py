"""StreamHub 投屏中心单测(不依赖真机)。

注意:
    - StreamSubscriber 通过 `loop.call_soon_threadsafe` 投递帧,要求该 loop 处于
      运行态(生产环境即 WebSocket 路由所在的 uvicorn loop)。测试中我们在后台
      线程跑一个常驻 loop 来模拟。
    - subscribe() 必须在 patch 生效后调用,否则抓帧线程会在 patch 之前连真机。
"""

from __future__ import annotations

import asyncio
import io
import threading
import time
from unittest.mock import patch

import pytest

from automator.perception import stream as stream_mod


# ---- 测试用辅助 ----
def _fake_png(color=(255, 0, 0)) -> bytes:
    from PIL import Image

    img = Image.new("RGB", (8, 8), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class _FakeDevice:
    """假设备:screenshot() 吐固定 PNG。"""

    def __init__(self) -> None:
        self.calls = 0

    def screenshot(self) -> bytes:
        self.calls += 1
        return _fake_png()


class _FailingDevice:
    def screenshot(self) -> bytes:
        raise RuntimeError("boom")


class _FakeDM:
    def __init__(self, dev) -> None:
        self._dev = dev

    def get_device(self):
        return self._dev


class _RunningLoop:
    """在后台线程里跑一个常驻 event loop,供 StreamSubscriber 绑定。"""

    def __init__(self):
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def submit(self, coro, timeout=2.0):
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def stop(self):
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(timeout=2.0)


@pytest.fixture
def fresh_hub(monkeypatch):
    """每个用例用一个全新的 StreamHub 实例(绕过单例缓存)。"""
    monkeypatch.setattr(stream_mod.settings, "stream_fps", 20)
    monkeypatch.setattr(stream_mod.settings, "stream_quality", 50)
    monkeypatch.setattr(stream_mod.settings, "stream_max_width", 0)
    stream_mod.StreamHub._instance = None
    hub = stream_mod.StreamHub()
    yield hub
    hub.stop()
    stream_mod.StreamHub._instance = None


@pytest.fixture
def rloop():
    rl = _RunningLoop()
    yield rl
    rl.stop()


# ---- 用例 ----
def test_subscribe_starts_thread_and_unsubscribe_stops(fresh_hub, rloop):
    """subscribe 应启动抓帧线程;最后一个 unsubscribe 应停止。"""
    dev = _FakeDevice()
    with patch.object(stream_mod, "get_device_manager", return_value=_FakeDM(dev)):
        # 在常驻 loop 里 subscribe,确保 StreamSubscriber 绑定到运行中的 loop
        sub = rloop.submit(_subscribe_coro(fresh_hub))
        assert fresh_hub._thread is not None
        assert fresh_hub._thread.is_alive()
        assert fresh_hub._subscriber_count() == 1
        # 等抓帧线程产出几帧
        time.sleep(0.4)
        assert dev.calls > 0

    fresh_hub.unsubscribe(sub)
    assert fresh_hub._subscriber_count() == 0
    assert not (fresh_hub._thread and fresh_hub._thread.is_alive())


async def _subscribe_coro(hub):
    return hub.subscribe()


async def _wait_frame(sub, want_type=None, timeout=2.0):
    """从订阅队列等一帧。"""
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            f = await asyncio.wait_for(sub.queue.get(), timeout=0.3)
        except asyncio.TimeoutError:
            continue
        if want_type is None or f.get("type") == want_type:
            return f
    return None


def test_receives_jpeg_frame(fresh_hub, rloop):
    """订阅者应能从队列拿到 JPEG 帧。"""
    dev = _FakeDevice()
    with patch.object(stream_mod, "get_device_manager", return_value=_FakeDM(dev)):
        sub = rloop.submit(_subscribe_coro(fresh_hub))
        frame = rloop.submit(_wait_frame(sub, want_type="frame", timeout=2.0))

    assert frame is not None
    assert frame["type"] == "frame"
    assert isinstance(frame["data"], (bytes, bytearray))
    # JPEG magic bytes FFD8
    assert bytes(frame["data"][:2]) == b"\xff\xd8"
    fresh_hub.unsubscribe(sub)


def test_grab_failure_returns_error_not_raise(fresh_hub, rloop):
    """设备截图抛异常时,订阅者收到 error 帧,抓帧线程不崩。"""
    with patch.object(stream_mod, "get_device_manager", return_value=_FakeDM(_FailingDevice())):
        sub = rloop.submit(_subscribe_coro(fresh_hub))
        err = rloop.submit(_wait_frame(sub, want_type="error", timeout=2.0))
        assert err is not None
        # 线程仍存活(没有因异常崩)
        assert fresh_hub._thread.is_alive()

    assert err["type"] == "error"
    assert "boom" in err["detail"]
    fresh_hub.unsubscribe(sub)


def test_device_not_connected_error(fresh_hub, rloop):
    """DeviceNotFoundError 应被转成 error 帧。"""
    from automator.device.exceptions import DeviceNotFoundError

    class _NoDevDM:
        def get_device(self):
            raise DeviceNotFoundError("no device")

    with patch.object(stream_mod, "get_device_manager", return_value=_NoDevDM()):
        sub = rloop.submit(_subscribe_coro(fresh_hub))
        err = rloop.submit(_wait_frame(sub, want_type="error", timeout=2.0))

    assert err is not None
    assert err["type"] == "error"
    assert "设备未连接" in err["detail"]
    fresh_hub.unsubscribe(sub)


def test_multiple_subscribers_share_capture(fresh_hub, rloop):
    """多个订阅者共享同一抓帧线程,各自都能收到帧。"""
    dev = _FakeDevice()
    with patch.object(stream_mod, "get_device_manager", return_value=_FakeDM(dev)):
        sub1 = rloop.submit(_subscribe_coro(fresh_hub))
        sub2 = rloop.submit(_subscribe_coro(fresh_hub))
        assert fresh_hub._subscriber_count() == 2
        # 只有一个抓帧线程
        assert fresh_hub._thread is not None

        f1 = rloop.submit(_wait_frame(sub1, want_type="frame", timeout=2.0))
        f2 = rloop.submit(_wait_frame(sub2, want_type="frame", timeout=2.0))

    assert f1 is not None and f1["type"] == "frame"
    assert f2 is not None and f2["type"] == "frame"
    fresh_hub.unsubscribe(sub1)
    fresh_hub.unsubscribe(sub2)
