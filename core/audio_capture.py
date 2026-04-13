# ============================================================
# SubtitleLive / core / audio_capture.py
# 统一音频采集入口 (Facade)
# ============================================================
from __future__ import annotations

import logging
from typing import Callable, List, Optional

import numpy as np

from core.audio_backends import build_backend_candidates, create_audio_backend
from core.audio_backends.sounddevice_backend import SoundDeviceLoopbackBackend
from core.config import AudioConfig

logger = logging.getLogger(__name__)


class AudioCapture:
    """统一音频采集 facade.

    上层只依赖此类:
      - 自动按平台和配置挑选后端
      - 保留旧接口兼容性
      - 为后续 Rust/C Native 后端预留接入点
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration: float = 3.0,
        overlap_duration: float = 0.5,
        vad_threshold: float = 0.01,
        backend: str = "auto",
        device_id: str = "",
        capture_mode: str = "system",
        prefer_native_backend: bool = True,
        allow_sounddevice_fallback: bool = True,
        native_library_path: str = "",
    ):
        self._cfg = AudioConfig(
            backend=backend,
            device_id=device_id or (str(device_index) if device_index is not None else ""),
            device_index=device_index,
            capture_mode=capture_mode,
            prefer_native_backend=prefer_native_backend,
            allow_sounddevice_fallback=allow_sounddevice_fallback,
            native_library_path=native_library_path,
            sample_rate=sample_rate,
            channels=channels,
            chunk_duration=chunk_duration,
            overlap_duration=overlap_duration,
            vad_threshold=vad_threshold,
        )
        self._backend = create_audio_backend(self._cfg)

    @staticmethod
    def list_devices(
        backend: str = "auto",
        prefer_native_backend: bool = True,
        allow_sounddevice_fallback: bool = True,
        native_library_path: str = "",
    ) -> List[dict]:
        cfg = AudioConfig(
            backend=backend,
            prefer_native_backend=prefer_native_backend,
            allow_sounddevice_fallback=allow_sounddevice_fallback,
            native_library_path=native_library_path,
        )
        devices = []
        for candidate in build_backend_candidates(cfg):
            if not candidate.is_supported():
                continue
            for device in candidate.list_devices():
                devices.append({
                    "id": device.device_id,
                    "index": int(device.device_id) if device.device_id.isdigit() else device.device_id,
                    "name": device.name,
                    "backend": device.backend,
                    "platform": device.platform,
                    "input_ch": device.input_channels,
                    "output_ch": device.output_channels,
                    "rate": device.default_sample_rate,
                    "is_loopback": device.is_loopback,
                })
        return devices

    @staticmethod
    def find_loopback_device() -> Optional[int]:
        backend = SoundDeviceLoopbackBackend(AudioConfig(backend="sounddevice_loopback"))
        device_id = backend.default_device_id()
        if device_id is None or not str(device_id).isdigit():
            return None
        return int(device_id)

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        self._backend.start(callback)

    def stop(self) -> None:
        self._backend.stop()

    @property
    def is_running(self) -> bool:
        return self._backend.is_running

    @property
    def backend_name(self) -> str:
        return self._backend.name()

    @property
    def selected_device_id(self) -> Optional[str]:
        return self._backend.selected_device_id

    @property
    def selected_device_name(self) -> str:
        return self._backend.selected_device_name
