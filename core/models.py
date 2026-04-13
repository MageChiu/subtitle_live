# ============================================================
# SubtitleLive / core / models.py
# 全局数据模型 (值对象, 无外部依赖)
# ============================================================
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


@dataclass(frozen=True)
class ASRResult:
    """语音识别结果"""
    text: str
    language: str
    confidence: float = 0.0
    segments: tuple = ()


@dataclass(frozen=True)
class TranslationResult:
    """翻译结果"""
    original: str
    translated: str
    source_lang: str
    target_lang: str


@dataclass
class SubtitleEvent:
    """字幕事件 — 管线最终输出, 传递给 UI"""
    original_text: str
    translated_text: str
    source_language: str
    target_language: str
    translations: tuple[tuple[str, str], ...] = ()
    timestamp: float = 0.0


@dataclass(frozen=True)
class AudioDeviceInfo:
    """统一的音频设备描述, 屏蔽不同平台/后端的设备枚举差异"""
    device_id: str
    name: str
    backend: str
    platform: str
    input_channels: int = 0
    output_channels: int = 0
    default_sample_rate: float = 0.0
    is_loopback: bool = False
