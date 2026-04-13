from __future__ import annotations

import platform
from typing import List

from core.config import AudioConfig
from core.interfaces import AudioCaptureBackend
from core.audio_backends.native_backend import (
    NativeLinuxPipewireBackend,
    NativeMacOSCoreAudioBackend,
    NativeWindowsWASAPIBackend,
)
from core.audio_backends.sounddevice_backend import SoundDeviceLoopbackBackend


def build_backend_candidates(cfg: AudioConfig) -> List[AudioCaptureBackend]:
    explicit = (cfg.backend or "auto").strip().lower()
    if explicit != "auto":
        return [_backend_from_name(cfg, explicit)]

    candidates: List[AudioCaptureBackend] = []
    if cfg.prefer_native_backend:
        candidates.append(_default_native_backend(cfg))
    if cfg.allow_sounddevice_fallback:
        candidates.append(SoundDeviceLoopbackBackend(cfg))
    return candidates


def create_audio_backend(cfg: AudioConfig) -> AudioCaptureBackend:
    candidates = build_backend_candidates(cfg)
    unavailable = []
    for backend in candidates:
        if backend.is_supported():
            return backend
        unavailable.append(
            f"{backend.name()}: {backend.unavailable_reason() or '当前环境不支持'}"
        )

    requested = (cfg.backend or "auto").strip().lower()
    if requested != "auto":
        raise RuntimeError(
            f"音频后端 `{requested}` 不可用: "
            f"{unavailable[0] if unavailable else '未找到对应实现'}"
        )

    raise RuntimeError(
        "当前环境没有可用的音频采集后端。\n"
        + "\n".join(f"  - {item}" for item in unavailable)
    )


def _default_native_backend(cfg: AudioConfig) -> AudioCaptureBackend:
    system = platform.system()
    if system == "Windows":
        return NativeWindowsWASAPIBackend(cfg)
    if system == "Darwin":
        return NativeMacOSCoreAudioBackend(cfg)
    return NativeLinuxPipewireBackend(cfg)


def _backend_from_name(cfg: AudioConfig, backend_name: str) -> AudioCaptureBackend:
    mapping = {
        "sounddevice_loopback": SoundDeviceLoopbackBackend,
        "native_windows_wasapi": NativeWindowsWASAPIBackend,
        "native_macos_coreaudio": NativeMacOSCoreAudioBackend,
        "native_linux_pipewire": NativeLinuxPipewireBackend,
    }
    try:
        return mapping[backend_name](cfg)
    except KeyError as exc:
        supported = ", ".join(sorted(mapping))
        raise RuntimeError(
            f"未知音频后端 `{backend_name}`。可选: {supported}"
        ) from exc
