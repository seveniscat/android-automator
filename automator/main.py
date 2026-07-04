"""FastAPI 应用入口。

启动:
    uvicorn automator.main:app --reload
或:
    python -m automator.main
或(安装后):
    automator
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .api.routes import devices, flows, playground, recorder, runs, system, tasks
from .config import PROJECT_ROOT, settings
from .logging import logger, setup_logging
from .storage.db import init_db
from .task.executor import get_executor
from .task.scheduler import get_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期:启动时初始化,退出时关闭。"""
    setup_logging()
    settings.ensure_dirs()
    init_db()
    logger.info(f"Automator 启动 → {settings.host}:{settings.port}")

    sched = get_scheduler()
    sched.start()

    yield

    logger.info("Automator 关闭中...")
    sched.shutdown(wait=False)
    get_executor().shutdown(wait=False)
    # 停止投屏抓帧线程(若有订阅者仍在,daemon 也会随进程退出,这里显式收尾)
    from .perception.stream import get_stream_hub

    get_stream_hub().stop()
    logger.info("已退出")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Automator",
        description="基于 uiautomator2 的 Android 真机自动化平台",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ---- API 路由 ----
    api_prefix = ""
    app.include_router(system.router, prefix=api_prefix)
    app.include_router(devices.router, prefix=api_prefix)
    app.include_router(flows.router, prefix=api_prefix)
    app.include_router(tasks.router, prefix=api_prefix)
    app.include_router(runs.router, prefix=api_prefix)
    app.include_router(playground.router, prefix=api_prefix)
    app.include_router(recorder.router, prefix=api_prefix)

    # ---- 静态资源 + 单页 ----
    web_dir = PROJECT_ROOT / "web"
    if web_dir.exists():
        app.mount(
            "/static",
            StaticFiles(directory=str(web_dir / "static")),
            name="static",
        )

        @app.get("/", include_in_schema=False)
        async def index():
            return FileResponse(str(web_dir / "index.html"))

        @app.get("/{full_path:path}", include_in_schema=False)
        async def spa_fallback(full_path: str):
            """前端 SPA 回退(非 /api/ 且非静态文件的路径回到 index.html)。"""
            if full_path.startswith(("api/", "static/")):
                return FileResponse(str(web_dir / "index.html"))
            candidate = web_dir / full_path
            if candidate.is_file():
                return FileResponse(str(candidate))
            return FileResponse(str(web_dir / "index.html"))

    return app


app = create_app()


def run() -> None:
    """命令行入口。"""
    import uvicorn

    setup_logging()
    uvicorn.run(
        "automator.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
