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
    p.add_argument("-t", "--target-lang", default="", help="翻译目标语言 (zh/en/ja/...)")
    p.add_argument("-m", "--model", default="", help="模型 (tiny/base/small/medium/large-v3)")
    p.add_argument("--device", default="", help="设备 (auto/cpu/cuda)")
    p.add_argument("--log-level", default="", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return p.parse_args()


def main():
    args = parse_args()
    config = AppConfig.load()

    # 命令行覆盖
    if args.source_lang:
        config.asr.source_language = args.source_lang
    if args.target_lang:
        config.translator.target_language = args.target_lang
    if args.model:
        config.asr.model_size = args.model
    if args.device:
        config.asr.device = args.device
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
