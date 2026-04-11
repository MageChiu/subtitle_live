# ============================================================
# plugins / asr / whisper_asr.py
# Faster-Whisper 语音识别引擎
# ============================================================
"""
基于 CTranslate2 量化的 Whisper, 比 OpenAI 原版快 4x
支持 15 种语言, 5 种模型规格, GPU/CPU 自适应
"""
from __future__ import annotations

import logging
from typing import List, Optional

import numpy as np

from core.interfaces import ASRPlugin
from core.models import ASRResult
from core.plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

# 支持的语言映射 (ISO 639-1 → Whisper 内部名, 仅做展示用)
SUPPORTED_LANGUAGES = [
    "auto", "en", "ja", "fr", "de", "es",
    "ko", "ru", "it", "pt", "zh",
    "ar", "hi", "th", "vi",
]


@PluginRegistry.register_asr
class WhisperASR(ASRPlugin):
    """Faster-Whisper ASR 引擎"""

    def __init__(self):
        self._model = None
        self._model_size: Optional[str] = None

    def name(self) -> str:
        return "whisper"

    def supported_languages(self) -> List[str]:
        return list(SUPPORTED_LANGUAGES)

    def load_model(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        if self._model and self._model_size == model_size:
            return

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "请安装 faster-whisper:\n"
                "  pip install faster-whisper\n"
                "GPU 加速还需:\n"
                "  pip install nvidia-cublas-cu12 nvidia-cudnn-cu12"
            )

        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        if device == "cpu" and compute_type == "float16":
            compute_type = "int8"

        logger.info("加载 Whisper: %s (device=%s, compute=%s)", model_size, device, compute_type)
        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._model_size = model_size
        logger.info("Whisper 模型就绪: %s", model_size)

    def transcribe(
        self,
        audio_data: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> Optional[ASRResult]:
        if self._model is None:
            raise RuntimeError("模型未加载")

        if audio_data is None or len(audio_data) == 0:
            return None

        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        # 静音检测
        if np.sqrt(np.mean(audio_data ** 2)) < 0.005:
            return None

        try:
            segments_iter, info = self._model.transcribe(
                audio_data,
                language=language,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(min_silence_duration_ms=500, speech_pad_ms=200),
                without_timestamps=True,
            )

            parts = []
            seg_list = []
            for seg in segments_iter:
                t = seg.text.strip()
                if t:
                    parts.append(t)
                    seg_list.append({"start": seg.start, "end": seg.end, "text": t})

            full = " ".join(parts).strip()
            if not full:
                return None

            return ASRResult(
                text=full,
                language=info.language or "unknown",
                confidence=getattr(info, "language_probability", 0.0),
                segments=tuple(seg_list),
            )
        except Exception as e:
            logger.error("Whisper 识别失败: %s", e, exc_info=True)
            return None

    def unload_model(self) -> None:
        if self._model:
            del self._model
            self._model = None
            self._model_size = None
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
            logger.info("Whisper 模型已卸载")
