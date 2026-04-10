#!/usr/bin/env python3
# ============================================================
# SubtitleLive - 应用入口
# ============================================================
"""
AI 实时字幕软件
  - 捕获电脑播放的声音
  - 实时语音识别 (Faster-Whisper)
  - 自动翻译为目标语言
  - 悬浮双语字幕显示

用法:
    python main.py [--config path/to/config.json]
"""
import argparse
import logging
import sys
import os

# 将当前目录加入路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import AppConfig

# === 重要: 导入引擎模块以触发插件注册 ===
import asr_engine        # noqa: F401 - 注册 WhisperASR
import translator        # noqa: F401 - 注册 GoogleFreeTranslator, OpenAITranslator

from tray_app import TrayApplication


def setup_logging(level: str = "INFO"):
    """配置日志"""
    log_format = (
        "%(asctime)s │ %(levelname)-7s │ %(name)-20s │ %(message)s"
    )
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format=log_format,
        datefmt="%H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # 降低三方库日志等级
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def parse_args():
    parser = argparse.ArgumentParser(
        description="SubtitleLive - AI 实时字幕软件"
    )
    parser.add_argument(
        "--config", "-c",
        type=str, default="",
        help="配置文件路径 (默认 ~/.subtitle_live/config.json)",
    )
    parser.add_argument(
        "--source-lang", "-s",
        type=str, default="",
        help="识别语言 (auto/en/ja/fr/de/es/ko/...)",
    )
    parser.add_argument(
        "--target-lang", "-t",
        type=str, default="",
        help="翻译目标语言 (zh/en/ja/...)",
    )
    parser.add_argument(
        "--model", "-m",
        type=str, default="",
        help="Whisper 模型大小 (tiny/base/small/medium/large-v3)",
    )
    parser.add_argument(
        "--device",
        type=str, default="",
        help="计算设备 (auto/cpu/cuda)",
    )
    parser.add_argument(
        "--log-level",
        type=str, default="",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="日志级别",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # 加载配置
    config = AppConfig.load()

    # 命令行参数覆盖
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

    # 配置日志
    setup_logging(config.log_level)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("  SubtitleLive - AI 实时字幕软件")
    logger.info("=" * 60)
    logger.info(f"  ASR 引擎:    {config.asr.engine} ({config.asr.model_size})")
    logger.info(f"  识别语言:    {config.asr.source_language}")
    logger.info(f"  翻译引擎:    {config.translator.engine}")
    logger.info(f"  翻译目标:    {config.translator.target_language}")
    logger.info(f"  计算设备:    {config.asr.device}")
    logger.info("=" * 60)

    # 启动托盘应用
    app = TrayApplication(config)
    exit_code = app.run()

    # 保存配置
    config.save()
    logger.info("SubtitleLive 已退出")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
