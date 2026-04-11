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
    timestamp: float = 0.0
