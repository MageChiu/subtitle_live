# ============================================================
# SubtitleLive - 配置管理模块
# ============================================================
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


CONFIG_DIR = Path.home() / ".subtitle_live"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AudioConfig:
    """音频捕获配置"""
    device_index: Optional[int] = None          # None = 自动检测 Loopback 设备
    sample_rate: int = 16000                     # Whisper 要求 16kHz
    channels: int = 1                            # 单声道即可
    chunk_duration: float = 3.0                  # 每次送识别的音频时长(秒)
    overlap_duration: float = 0.5                # 块之间重叠时长(秒), 防止截断单词
    vad_threshold: float = 0.01                  # 静音检测阈值 (RMS)


@dataclass
class ASRConfig:
    """语音识别配置"""
    engine: str = "whisper"                      # 当前使用的 ASR 引擎名
    model_size: str = "base"                     # tiny / base / small / medium / large-v3
    device: str = "auto"                         # auto / cpu / cuda
    compute_type: str = "int8"                   # float16 / int8 / int8_float16
    source_language: str = "auto"                # auto = 自动检测, 或 en / ja / fr / ...
    beam_size: int = 5
    vad_filter: bool = True                      # Whisper 内置 VAD 过滤


@dataclass
class TranslatorConfig:
    """翻译配置"""
    engine: str = "google_free"                  # google_free / openai
    target_language: str = "zh"                  # 翻译目标语言
    openai_api_key: str = ""                     # 如果使用 OpenAI 翻译
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""                    # 自定义 API 地址


@dataclass
class OverlayConfig:
    """悬浮窗配置"""
    x: int = -1                                  # -1 = 居中
    y: int = -1                                  # -1 = 屏幕底部偏上
    width: int = 800
    height: int = 120
    opacity: float = 0.85                        # 背景透明度
    font_size_original: int = 14                 # 原文字号
    font_size_translated: int = 18               # 翻译字号
    font_family: str = "Microsoft YaHei"         # 字体
    show_original: bool = True                   # 是否显示原文
    show_translated: bool = True                 # 是否显示翻译
    auto_hide_seconds: float = 8.0               # 无新字幕时自动隐藏(秒)
    bg_color: str = "#1a1a2e"                    # 背景颜色
    original_color: str = "#a0a0a0"              # 原文文字颜色
    translated_color: str = "#ffffff"            # 翻译文字颜色
    border_radius: int = 12                      # 圆角半径


@dataclass
class AppConfig:
    """应用总配置"""
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    translator: TranslatorConfig = field(default_factory=TranslatorConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    log_level: str = "INFO"
    subtitle_log_file: str = ""                  # 字幕日志文件路径(空=不记录)

    def save(self):
        """持久化配置到文件"""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(asdict(self), f, ensure_ascii=False, indent=2)

    @classmethod
    def load(cls) -> "AppConfig":
        """从文件加载配置, 不存在则返回默认"""
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                audio=AudioConfig(**data.get("audio", {})),
                asr=ASRConfig(**data.get("asr", {})),
                translator=TranslatorConfig(**data.get("translator", {})),
                overlay=OverlayConfig(**data.get("overlay", {})),
                log_level=data.get("log_level", "INFO"),
                subtitle_log_file=data.get("subtitle_log_file", ""),
            )
        except Exception:
            return cls()

    def to_dict(self) -> dict:
        return asdict(self)
