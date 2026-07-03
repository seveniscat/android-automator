"""Web 实时投屏 —— 共享抓帧 + WebSocket 广播。

设计要点:
    - `StreamHub` 是进程级单例,后台一个 daemon 抓帧线程,按固定 fps 抓取设备截图。
    - 每个 WebSocket 客户端持有一个 `StreamSubscriber`(内含 asyncio.Queue),
      抓帧线程把同一帧 fan-out 给所有订阅者,多客户端共享同一份抓帧,
      不会因打开多个页面而重复抓帧压垮设备。
    - 懒启动:第一个订阅者到来时启动抓帧线程;最后一个离开时停止。
    - 跨线程投递:抓帧线程通过 `loop.call_soon_threadsafe` 把帧放进订阅者的队列,
      队列采用 drop-old 策略(maxsize=1),慢客户端不拖累全局。

帧格式(投递到订阅者队列的 dict):
    - {"type": "frame", "data": <jpeg bytes>}
    - {"type": "error", "detail": <msg>}

WebSocket 路由层负责把 frame.data 作为 binary 发送,error 作为 text 发送。
"""

from __future__ import annotations

import asyncio
import io
import threading
import time

from ..config import settings
from ..device.exceptions import DeviceError, DeviceNotFoundError
from ..device.manager import get_device_manager
from ..logging import logger


class StreamSubscriber:
    """单个 WebSocket 客户端的订阅句柄。

    由 `StreamHub.subscribe()` 创建,持有调用方(异步路由)所在的 event loop,
    这样抓帧线程能线程安全地把帧投递进 `queue`。
    """

    __slots__ = ("loop", "queue")

    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        # maxsize=1 + drop-old:慢客户端最多落后一帧,旧帧丢弃保证实时性
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=1)

    def put(self, frame: dict) -> None:
        """由抓帧线程调用,线程安全地把帧投递进队列(drop-old)。"""
        if self.loop.is_closed():
            return
        try:
            self.loop.call_soon_threadsafe(self._put_nowait, frame)
        except RuntimeError:
            # loop 已关闭
            pass

    def _put_nowait(self, frame: dict) -> None:
        try:
            self.queue.put_nowait(frame)
        except asyncio.QueueFull:
            # 丢弃最旧的一帧再投新的,保证订阅者拿到的总是最新画面
            try:
                self.queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
            try:
                self.queue.put_nowait(frame)
            except asyncio.QueueFull:
                pass


class StreamHub:
    """投屏中心(线程安全单例,仿 `DeviceManager` 模式)。"""

    _instance: StreamHub | None = None
    _lock = threading.Lock()

    def __new__(cls) -> StreamHub:
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._subscribers: list[StreamSubscriber] = []
        self._sub_lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._initialized = True

    # ---- 订阅生命周期 ----
    def subscribe(self) -> StreamSubscriber:
        """注册一个订阅者;若抓帧线程未运行则启动。"""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # 不在异步上下文(例如测试直接调用),回退到新 loop
            loop = asyncio.new_event_loop()
        sub = StreamSubscriber(loop)
        with self._sub_lock:
            self._subscribers.append(sub)
            need_start = self._thread is None or not self._thread.is_alive()
        if need_start:
            self._start()
        logger.debug(f"StreamHub 订阅者+1,当前 {self._subscriber_count()} 个")
        return sub

    def unsubscribe(self, sub: StreamSubscriber) -> None:
        """注销订阅者;订阅者归零则停止抓帧线程。"""
        with self._sub_lock:
            if sub in self._subscribers:
                self._subscribers.remove(sub)
            empty = len(self._subscribers) == 0
        if empty:
            self.stop()
        logger.debug(f"StreamHub 订阅者-1,当前 {self._subscriber_count()} 个")

    def _subscriber_count(self) -> int:
        with self._sub_lock:
            return len(self._subscribers)

    # ---- 抓帧线程 ----
    def _start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._capture_loop,
            name="streamhub-capture",
            daemon=True,
        )
        self._thread.start()
        logger.info(
            f"StreamHub 抓帧线程已启动 (fps={settings.stream_fps}, "
            f"quality={settings.stream_quality}, max_width={settings.stream_max_width})"
        )

    def stop(self) -> None:
        """停止抓帧线程(订阅者归零或应用退出时调用)。"""
        if self._thread is None or not self._thread.is_alive():
            return
        self._stop_event.set()
        self._thread.join(timeout=2.0)
        self._thread = None
        logger.info("StreamHub 抓帧线程已停止")

    def _capture_loop(self) -> None:
        """抓帧主循环(后台线程)。"""
        interval = 1.0 / max(settings.stream_fps, 1)
        consecutive_fail = 0
        while not self._stop_event.is_set():
            t0 = time.monotonic()
            frame = self._grab()
            self._fanout(frame)
            if frame.get("type") == "error":
                consecutive_fail += 1
                if consecutive_fail == 3:
                    logger.warning(f"投屏抓帧连续失败 {consecutive_fail} 次: {frame.get('detail')}")
            else:
                consecutive_fail = 0
            # 按固定节拍抓帧(扣除本帧耗时)
            elapsed = time.monotonic() - t0
            self._stop_event.wait(max(interval - elapsed, 0))
        logger.debug("StreamHub 抓帧循环退出")

    def _grab(self) -> dict:
        """抓一帧并编码为 JPEG,返回投递用 dict。"""
        try:
            dev = get_device_manager().get_device()
            png = dev.screenshot()
        except (DeviceNotFoundError, DeviceError) as e:
            return {"type": "error", "detail": f"设备未连接: {e}"}
        except Exception as e:
            return {"type": "error", "detail": f"抓帧失败: {e}"}

        try:
            from PIL import Image
        except ImportError:
            # 无 PIL 时直接发原 PNG(兼容性回退)
            return {"type": "frame", "data": png}

        try:
            img = Image.open(io.BytesIO(png))
            max_w = settings.stream_max_width
            if max_w and img.width > max_w:
                # thumbnail 保持宽高比,in-place 缩放
                new_h = max(1, int(img.height * max_w / img.width))
                img = img.resize((max_w, new_h))
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=settings.stream_quality)
            return {"type": "frame", "data": buf.getvalue()}
        except Exception as e:
            return {"type": "error", "detail": f"编码失败: {e}"}

    def _fanout(self, frame: dict) -> None:
        """把帧投递给所有订阅者,顺手清理已 loop 关闭的死订阅者。"""
        with self._sub_lock:
            subs = list(self._subscribers)
        dead: list[StreamSubscriber] = []
        for sub in subs:
            if sub.loop.is_closed():
                dead.append(sub)
                continue
            sub.put(frame)
        if dead:
            with self._sub_lock:
                for s in dead:
                    if s in self._subscribers:
                        self._subscribers.remove(s)


def get_stream_hub() -> StreamHub:
    """获取全局 StreamHub 单例。"""
    return StreamHub()
