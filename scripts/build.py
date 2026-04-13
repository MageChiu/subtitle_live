#!/usr/bin/env python3
from __future__ import annotations

import argparse
import compileall
import datetime as dt
import platform
from pathlib import Path

from common import (
    MAIN_FILE,
    REQUIREMENTS_FILE,
    ROOT,
    default_audio_backend,
    detect_platform,
    platform_notes,
    python_executable,
    run_command,
    write_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="SubtitleLive 构建入口")
    parser.add_argument(
        "--platform",
        default="auto",
        choices=["auto", "windows", "macos", "linux"],
        help="目标平台配置",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        help="构建前安装 requirements.txt",
    )
    parser.add_argument(
        "--skip-compile",
        action="store_true",
        help="跳过 Python 字节码校验",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_platform = detect_platform(args.platform)
    host_platform = detect_platform("auto")
    build_dir = ROOT / "build" / target_platform
    manifest_file = build_dir / "build-manifest.json"

    if args.install_deps:
        run_command([python_executable(), "-m", "pip", "install", "-r", str(REQUIREMENTS_FILE)])

    if not args.skip_compile:
        ok = True
        ok &= compileall.compile_dir(str(ROOT / "core"), quiet=1)
        ok &= compileall.compile_dir(str(ROOT / "plugins"), quiet=1)
        ok &= compileall.compile_dir(str(ROOT / "ui"), quiet=1)
        ok &= compileall.compile_file(str(MAIN_FILE), quiet=1)
        if not ok:
            raise SystemExit("Python 字节码校验失败")

    run_command(
        [python_executable(), "-c", "from core.pipeline import SubtitlePipeline; from core.config import AppConfig; SubtitlePipeline(AppConfig.load()); print('validation-ok')"],
    )

    manifest = {
        "project": "subtitle_live",
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "host_platform": host_platform,
        "target_platform": target_platform,
        "cross_platform": host_platform != target_platform,
        "python_version": platform.python_version(),
        "default_audio_backend": default_audio_backend(target_platform),
        "platform_note": platform_notes(target_platform),
        "artifacts": {
            "entry": "main.py",
            "build_dir": str(build_dir),
            "native_status": "placeholder",
        },
    }
    write_json(manifest_file, manifest)

    print(f"[build] host={host_platform} target={target_platform}")
    print(f"[build] default-audio-backend={manifest['default_audio_backend']}")
    print(f"[build] manifest={manifest_file}")
    if host_platform != target_platform:
        print("[build] note=当前仅生成目标平台构建配置与校验结果，Native 后端仍需在目标平台实现与编译")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
