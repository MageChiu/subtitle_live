# ============================================================
# SubtitleLive - ASR 引擎 (Faster-Whisper 实现)
# ============================================================
"""
默认 ASR 引擎: 基于 Faster-Whisper (CTranslate2)
支持语言: 英语/日语/法语/德语/西班牙语/韩语/俄语/意大利语/葡萄牙语/中文 等
"""
from __future__ import annotations
import logging
import numpy as np
from typing import List, Optional

from plugin_registry import ASRPlugin, ASRResult, PluginRegistry

logger = logging.getLogger(__name__)


# ============================================================
# 语言配置表 (可扩展)
# ============================================================

LANGUAGE_MAP = {
    "auto": None,       # 自动检测
    "en": "english",
    "ja": "japanese",
    "fr": "french",
    "de": "german",
    "es": "spanish",
    "ko": "korean",
    "ru": "russian",
    "it": "italian",
    "pt": "portuguese",
    "zh": "chinese",
    "ar": "arabic",
    "hi": "hindi",
    "th": "thai",
    "vi": "vietnamese",
}

# Whisper 语言代码反向映射
WHISPER_LANG_TO_ISO = {v: k for k, v in LANGUAGE_MAP.items() if v is not None}


@PluginRegistry.register_asr
class WhisperASR(ASRPlugin):
    """
    基于 Faster-Whisper 的语音识别引擎
    
    特性:
    - 比 OpenAI Whisper 快 4x (CTranslate2 量化)
    - 支持 GPU (CUDA) 和 CPU
    - 内置 VAD 过滤静音段
    """

    def __init__(self):
        self._model = None
        self._model_size = None

    def name(self) -> str:
        return "whisper"

    def supported_languages(self) -> List[str]:
        return list(LANGUAGE_MAP.keys())

    def load_model(self, model_size: str = "base", device: str = "auto",
                   compute_type: str = "int8") -> None:
        """
        加载 Faster-Whisper 模型
        
        :param model_size: tiny / base / small / medium / large-v3
        :param device: auto / cpu / cuda
        :param compute_type: float16 / int8 / int8_float16
        """
        if self._model is not None and self._model_size == model_size:
            logger.info(f"模型 {model_size} 已加载, 跳过")
            return

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            raise ImportError(
                "请安装 faster-whisper: pip install faster-whisper\n"
                "GPU 用户还需: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12"
            )

        # 自动检测设备
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        # CPU 强制使用 int8
        if device == "cpu" and compute_type == "float16":
            compute_type = "int8"

        logger.info(f"正在加载 Whisper 模型: {model_size} "
                     f"(device={device}, compute_type={compute_type})")

        self._model = WhisperModel(
            model_size,
            device=device,
            compute_type=compute_type,
        )
        self._model_size = model_size
        logger.info(f"Whisper 模型加载完成: {model_size}")

    def transcribe(self, audio_data: np.ndarray, sample_rate: int = 16000,
                   language: Optional[str] = None) -> Optional[ASRResult]:
        """
        识别音频数据
        
        :param audio_data: float32 numpy 数组, 值域 [-1, 1]
        :param sample_rate: 采样率 (应为 16000)
        :param language: 源语言 ISO 代码, None/auto=自动检测
        """
        if self._model is None:
            raise RuntimeError("模型未加载, 请先调用 load_model()")

        # 数据验证
        if audio_data is None or len(audio_data) == 0:
            return None

        # 确保 float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)

        # 如果是多声道, 取平均转单声道
        if audio_data.ndim > 1:
            audio_data = audio_data.mean(axis=1)

        # 静音检测 - RMS 过低则跳过
        rms = np.sqrt(np.mean(audio_data ** 2))
        if rms < 0.005:
            return None

        # 处理语言参数
        whisper_lang = None
        if language and language != "auto":
            whisper_lang = language  # faster-whisper 直接接受 ISO 代码

        # 执行识别
        try:
            segments, info = self._model.transcribe(
                audio_data,
                language=whisper_lang,
                beam_size=5,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
                without_timestamps=True,
            )

            # 收集所有段文本
            text_parts = []
            all_segments = []
            for seg in segments:
                text = seg.text.strip()
                if text:
                    text_parts.append(text)
                    all_segments.append({
                        "start": seg.start,
                        "end": seg.end,
                        "text": text,
                    })

            full_text = " ".join(text_parts).strip()
            if not full_text:
                return None

            # 检测到的语言
            detected_lang = info.language if info.language else "unknown"

            return ASRResult(
                text=full_text,
                language=detected_lang,
                confidence=info.language_probability if hasattr(info, 'language_probability') else 0.0,
                segments=all_segments,
            )

        except Exception as e:
            logger.error(f"Whisper 识别失败: {e}", exc_info=True)
            return None

    def unload_model(self) -> None:
        """释放模型资源"""
        if self._model is not None:
            del self._model
            self._model = None
            self._model_size = None
            logger.info("Whisper 模型已卸载")

            # 尝试释放 GPU 显存
            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass
