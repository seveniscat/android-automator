"""全局配置,基于 pydantic-settings 从环境变量/.env 加载。"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """平台全局配置。

    所有字段均可通过环境变量(`AUTOMATOR_*`)或项目根目录下的 `.env` 文件覆盖。
    """

    model_config = SettingsConfigDict(
        env_prefix="AUTOMATOR_",
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- 服务 ----
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # ---- 设备 ----
    device_serial: str = ""
    atx_port: int = 7912

    # ---- Web 实时投屏 ----
    # 抓帧帧率(u2 截图实测约 2-5fps,设置过高会被截图耗时限制)
    stream_fps: int = 4
    # JPEG 编码质量(1-100),越低带宽越小
    stream_quality: int = 60
    # 投屏画面最大宽度像素(0=不缩放,>0 按比例缩小降带宽)
    stream_max_width: int = 720

    # ---- 存储 ----
    db_url: str = f"sqlite:///{PROJECT_ROOT / 'data' / 'automator.db'}"
    screenshot_dir: Path = PROJECT_ROOT / "data" / "screenshots"

    # ---- 任务执行 ----
    executor_workers: int = 4
    step_timeout: int = 30

    # ---- LLM(预留)----
    llm_provider: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: str = "gpt-4o"

    @property
    def flows_dir(self) -> Path:
        return PROJECT_ROOT / "flows"

    def ensure_dirs(self) -> None:
        """确保运行时目录存在。"""
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        (PROJECT_ROOT / "data").mkdir(parents=True, exist_ok=True)


settings = Settings()
