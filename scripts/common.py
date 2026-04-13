#!/usr/bin/env python3
from __future__ import annotations

import json
import platform
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS_FILE = ROOT / "requirements.txt"
MAIN_FILE = ROOT / "main.py"


def detect_platform(target: str = "auto") -> str:
    target = (target or "auto").strip().lower()
    if target in {"windows", "macos", "linux"}:
        return target

    system = platform.system()
    mapping = {
        "Windows": "windows",
        "Darwin": "macos",
        "Linux": "linux",
    }
    try:
        return mapping[system]
    except KeyError as exc:
        raise RuntimeError(f"暂不支持的平台: {system}") from exc


def default_audio_backend(target_platform: str) -> str:
    return {
        "windows": "native_windows_wasapi",
        "macos": "native_macos_coreaudio",
        "linux": "native_linux_pipewire",
    }[target_platform]


def platform_notes(target_platform: str) -> str:
    return {
        "windows": "推荐长期实现: WASAPI loopback Native 后端",
        "macos": "推荐长期实现: ScreenCaptureKit/CoreAudio Native 后端，虚拟设备作为 fallback",
        "linux": "推荐长期实现: PipeWire/PulseAudio monitor Native 后端",
    }[target_platform]


def run_command(command: list[str], cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=str(cwd or ROOT), check=True)


def write_json(file_path: Path, data: dict) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def format_command(command: Iterable[str]) -> str:
    return " ".join(shlex.quote(part) for part in command)


def python_executable() -> str:
    return sys.executable
