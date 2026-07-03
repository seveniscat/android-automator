"""OCR 感知器(预留接口,本期不实现)。

未来接入 PaddleOCR / EasyOCR,把截图转成文字 + 坐标,
让 YAML 流程支持 `click_text: "登录"` 这类语义步骤。
"""

from __future__ import annotations

from .base import Perception, PerceptionState


class OCRPerception(Perception):
    """OCR 感知器占位实现。

    接入方式(后续迭代):
        pip install paddleocr   # 或 easyocr
        在 perceive() 中加载模型,识别 PNG 中文字,填入 state.ocr_texts
    """

    name = "ocr"

    def __init__(self, lang: str = "ch") -> None:
        self.lang = lang
        self._engine = None

    def _ensure_engine(self):
        if self._engine is None:
            raise NotImplementedError(
                "OCR 感知器尚未接入。请安装 PaddleOCR/EasyOCR "
                "并在此实现模型加载。"
            )
        return self._engine

    def perceive(self, device) -> PerceptionState:
        raise NotImplementedError(
            "OCR 感知器为预留能力,本期不可用。"
            "后续迭代将通过 PaddleOCR 实现。"
        )
