# ============================================================
# SubtitleLive / core / config.py
# 分层配置 (dataclass + JSON 持久化)
# ============================================================
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

CONFIG_DIR = Path.home() / ".subtitle_live"
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class AudioConfig:
    device_index: Optional[int] = None      # None → 自动检测
    sample_rate: int = 16000
    channels: int = 1
    chunk_duration: float = 3.0             # 送识别的窗口长度 (秒)
    overlap_duration: float = 0.5           # 窗口重叠 (秒)
    vad_threshold: float = 0.01             # 静音 RMS 阈值


@dataclass
class ASRConfig:
    engine: str = "whisper"
    model_size: str = "base"                # tiny / base / small / medium / large-v3
    device: str = "auto"                    # auto / cpu / cuda
    compute_type: str = "int8"
    source_language: str = "auto"           # auto 或 ISO 639-1
    beam_size: int = 5
    vad_filter: bool = True


@dataclass
class TranslatorConfig:
    engine: str = "google_free"             # google_free / openai
    target_language: str = "zh"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    openai_base_url: str = ""


@dataclass
class OverlayConfig:
    x: int = -1                             # -1 → 自动居中
    y: int = -1
    width: int = 800
    height: int = 120
    opacity: float = 0.85
    font_size_original: int = 14
    font_size_translated: int = 18
    font_family: str = "Microsoft YaHei"
    show_original: bool = True
    show_translated: bool = True
    auto_hide_seconds: float = 8.0
    bg_color: str = "#1a1a2e"
    original_color: str = "#a0a0a0"
    translated_color: str = "#ffffff"
    border_radius: int = 12


@dataclass
class AppConfig:
    audio: AudioConfig = field(default_factory=AudioConfig)
    asr: ASRConfig = field(default_factory=ASRConfig)
    translator: TranslatorConfig = field(default_factory=TranslatorConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    log_level: str = "INFO"
    subtitle_log_file: str = ""

    # ---- 序列化 ----

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls) -> AppConfig:
        if not CONFIG_FILE.exists():
            cfg = cls()
            cfg.save()
            return cfg
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
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
