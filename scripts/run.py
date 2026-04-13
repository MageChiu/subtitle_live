#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess

from common import MAIN_FILE, ROOT, detect_platform, format_command, python_executable


def parse_args() -> tuple[argparse.Namespace, list[str]]:
    parser = argparse.ArgumentParser(description="SubtitleLive 运行入口")
    parser.add_argument(
        "--platform",
        default="auto",
        choices=["auto", "windows", "macos", "linux"],
        help="运行平台配置",
    )
    parser.add_argument(
        "--audio-backend",
        default="auto",
        help="音频后端 (auto/native_*/sounddevice_loopback)",
    )
    parser.add_argument(
        "--target-lang",
        default="",
        help="翻译目标语言, 支持逗号分隔多目标 (如 zh,ja 或 zh-TW)",
    )
    parser.add_argument("--audio-device-id", default="", help="统一音频设备 ID")
    parser.add_argument(
        "--capture-mode",
        default="system",
        choices=["system", "microphone", "app"],
        help="音频采集模式",
    )
    parser.add_argument("--native-library-path", default="", help="Native 音频动态库路径")
    parser.add_argument(
        "--disable-native-backend",
        action="store_true",
        help="禁用 native-first 策略",
    )
    parser.add_argument(
        "--disable-sounddevice-fallback",
        action="store_true",
        help="禁用 sounddevice fallback",
    )
    parser.add_argument(
        "--auto-start",
        action="store_true",
        help="启动后自动开始识别",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="仅打印实际运行命令",
    )
    return parser.parse_known_args()


def main() -> int:
    args, passthrough = parse_args()
    if passthrough and passthrough[0] == "--":
        passthrough = passthrough[1:]
    target_platform = detect_platform(args.platform)
    host_platform = detect_platform("auto")
    if target_platform != host_platform:
        raise SystemExit(
            f"run 脚本必须与当前主机平台一致: host={host_platform}, target={target_platform}"
        )

    command = [python_executable(), str(MAIN_FILE)]
    if args.target_lang:
        command.extend(["--target-lang", args.target_lang])
    if args.audio_backend and args.audio_backend != "auto":
        command.extend(["--audio-backend", args.audio_backend])
    if args.audio_device_id:
        command.extend(["--audio-device-id", args.audio_device_id])
    if args.capture_mode and args.capture_mode != "system":
        command.extend(["--capture-mode", args.capture_mode])
    if args.native_library_path:
        command.extend(["--native-library-path", args.native_library_path])
    if args.disable_native_backend:
        command.append("--disable-native-backend")
    if args.disable_sounddevice_fallback:
        command.append("--disable-sounddevice-fallback")
    effective_auto_start = args.auto_start or target_platform == "macos"
    if effective_auto_start:
        command.append("--auto-start")
    command.extend(passthrough)

    print(f"[run] platform={target_platform}")
    print(f"[run] command={format_command(command)}")
    if args.dry_run:
        return 0

    completed = subprocess.run(command, cwd=str(ROOT))
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
