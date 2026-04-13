#!/usr/bin/env python3
# ============================================================
# SubtitleLive - 应用入口
# ============================================================
"""
AI 实时字幕软件
  捕获桌面音频 → 语音识别 → 翻译 → 悬浮双语字幕

用法:
    python main.py
    python main.py -s en -t zh -m small
    python main.py --help
"""
import argparse
import logging
import sys
import os

# 确保项目根目录在 sys.path (支持 python main.py 直接运行)
_ROOT = os.path.dirname(os.path.abspath(__file__))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from core.config import AppConfig
from core.plugin_registry import PluginRegistry
from ui.tray import TrayApplication


def setup_logging(level: str = "INFO"):
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s │ %(levelname)-7s │ %(name)-22s │ %(message)s",
        datefmt="%H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    for name in ("faster_whisper", "urllib3", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def parse_args():
    p = argparse.ArgumentParser(description="SubtitleLive - AI 实时字幕软件")
    p.add_argument("-s", "--source-lang", default="", help="识别语言 (auto/en/ja/fr/...)")
    p.add_argument("-t", "--target-lang", default="", help="翻译目标语言, 支持逗号分隔多目标 (zh/zh-TW/ja/...)")
    p.add_argument("-m", "--model", default="", help="模型 (tiny/base/small/medium/large-v3)")
    p.add_argument("--device", default="", help="设备 (auto/cpu/cuda)")
    p.add_argument(
        "--audio-backend",
        default="",
        help="音频后端 (auto/native_windows_wasapi/native_macos_coreaudio/native_linux_pipewire/sounddevice_loopback)",
    )
    p.add_argument("--audio-device-id", default="", help="统一音频设备 ID")
    p.add_argument(
        "--capture-mode",
        default="",
        choices=["system", "microphone", "app"],
        help="音频采集模式",
    )
    p.add_argument("--native-library-path", default="", help="Native 音频后端动态库路径")
    p.add_argument(
        "--disable-native-backend",
        action="store_true",
        help="禁用 native-first 策略",
    )
    p.add_argument(
        "--disable-sounddevice-fallback",
        action="store_true",
        help="禁用 sounddevice fallback",
    )
    p.add_argument(
        "--auto-start",
        action="store_true",
        help="启动后自动开始识别, 适合无法方便操作托盘的场景",
    )
    p.add_argument("--log-level", default="", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main():
    args = parse_args()
    config = AppConfig.load()

    # 命令行覆盖
    if args.source_lang:
        config.asr.source_language = args.source_lang
    if args.target_lang:
        targets = [item.strip() for item in args.target_lang.split(",") if item.strip()]
        if targets:
            config.translator.target_languages = targets
            config.translator.target_language = targets[0]
    if args.model:
        config.asr.model_size = args.model
    if args.device:
        config.asr.device = args.device
    if args.audio_backend:
        config.audio.backend = args.audio_backend
    if args.audio_device_id:
        config.audio.device_id = args.audio_device_id
    if args.capture_mode:
        config.audio.capture_mode = args.capture_mode
    if args.native_library_path:
        config.audio.native_library_path = args.native_library_path
    if args.disable_native_backend:
        config.audio.prefer_native_backend = False
    if args.disable_sounddevice_fallback:
        config.audio.allow_sounddevice_fallback = False
    if args.auto_start:
        config.auto_start = True
    if args.log_level:
        config.log_level = args.log_level

    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    # ★ 自动发现并注册所有插件
    PluginRegistry.discover("plugins.asr")
    PluginRegistry.discover("plugins.translator")

    logger.info("=" * 56)
    logger.info("  SubtitleLive — AI 实时字幕")
    logger.info("=" * 56)
    logger.info("  ASR      : %s (%s)", config.asr.engine, config.asr.model_size)
    logger.info("  源语言   : %s", config.asr.source_language)
    logger.info("  翻译     : %s → %s", config.translator.engine, config.translator.target_language)
    logger.info("  设备     : %s", config.asr.device)
    logger.info("  已注册 ASR  : %s", list(PluginRegistry.list_asr().keys()))
    logger.info("  已注册 Trans: %s", list(PluginRegistry.list_translators().keys()))
    logger.info("=" * 56)

    app = TrayApplication(config)
    code = app.run()
    config.save()
    sys.exit(code)


if __name__ == "__main__":
    main()
