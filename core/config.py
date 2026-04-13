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
    backend: str = "auto"                   # auto / native_* / sounddevice_loopback
    device_id: str = ""                     # 统一设备 ID
    device_index: Optional[int] = None      # None → 自动检测
    capture_mode: str = "system"            # system / microphone / app
    prefer_native_backend: bool = True
    allow_sounddevice_fallback: bool = True
    native_library_path: str = ""
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
    target_languages: list[str] = field(default_factory=lambda: ["zh"])
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
    auto_start: bool = False
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
            audio_data = data.get("audio", {})
            if not audio_data.get("device_id") and audio_data.get("device_index") is not None:
                audio_data = dict(audio_data)
                audio_data["device_id"] = str(audio_data["device_index"])
            translator_data = data.get("translator", {})
            if not translator_data.get("target_languages"):
                translator_data = dict(translator_data)
                translator_data["target_languages"] = [
                    translator_data.get("target_language", "zh")
                ]
            return cls(
                audio=AudioConfig(**audio_data),
                asr=ASRConfig(**data.get("asr", {})),
                translator=TranslatorConfig(**translator_data),
                overlay=OverlayConfig(**data.get("overlay", {})),
                auto_start=data.get("auto_start", False),
                log_level=data.get("log_level", "INFO"),
                subtitle_log_file=data.get("subtitle_log_file", ""),
            )
        except Exception:
            return cls()

    def to_dict(self) -> dict:
        return asdict(self)
