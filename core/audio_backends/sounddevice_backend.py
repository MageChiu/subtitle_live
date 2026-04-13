from __future__ import annotations

import logging
import platform
import threading
import time
from typing import Callable, List, Optional

import numpy as np

from core.config import AudioConfig
from core.interfaces import AudioCaptureBackend
from core.models import AudioDeviceInfo

logger = logging.getLogger(__name__)


class SoundDeviceLoopbackBackend(AudioCaptureBackend):
    """基于 sounddevice/PortAudio 的 Python fallback.

    适用场景:
      - macOS 虚拟回采设备 (BlackHole / Soundflower / Loopback)
      - Linux monitor 设备
      - 某些带 loopback 输入的 Windows 环境
    """

    def __init__(self, cfg: AudioConfig):
        self._cfg = cfg
        self._stream = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._buffer = np.array([], dtype=np.float32)
        self._lock = threading.Lock()
        self._chunk_samples = int(cfg.sample_rate * cfg.chunk_duration)
        self._overlap_samples = int(cfg.sample_rate * cfg.overlap_duration)
        self._selected_device_id = cfg.device_id or (
            str(cfg.device_index) if cfg.device_index is not None else None
        )
        self._selected_device_name = ""

    def name(self) -> str:
        return "sounddevice_loopback"

    def is_supported(self) -> bool:
        try:
            import sounddevice  # noqa: F401
            return True
        except ImportError:
            return False

    def unavailable_reason(self) -> str:
        return "缺少 `sounddevice` 依赖，无法启用 Python fallback 音频采集。"

    def list_devices(self) -> List[AudioDeviceInfo]:
        try:
            import sounddevice as sd

            return [
                AudioDeviceInfo(
                    device_id=str(i),
                    name=d["name"],
                    backend=self.name(),
                    platform=platform.system(),
                    input_channels=d["max_input_channels"],
                    output_channels=d["max_output_channels"],
                    default_sample_rate=float(d["default_samplerate"]),
                    is_loopback=self._is_loopback(d["name"]),
                )
                for i, d in enumerate(sd.query_devices())
            ]
        except Exception as e:
            logger.error("枚举音频设备失败: %s", e)
            return []

    def default_device_id(self) -> Optional[str]:
        try:
            import sounddevice as sd

            devices = sd.query_devices()
            os_name = platform.system()
            keywords = {
                "Windows": ["stereo mix", "loopback", "what u hear", "wave out"],
                "Darwin": ["blackhole", "soundflower", "loopback"],
                "Linux": ["monitor", "loopback"],
            }.get(os_name, ["loopback", "monitor"])

            for kw in keywords:
                for i, d in enumerate(devices):
                    if kw in d["name"].lower() and d["max_input_channels"] > 0:
                        return str(i)

            default_in = sd.default.device[0]
            if default_in is not None and default_in >= 0:
                default_dev = devices[int(default_in)]
                if default_dev["max_input_channels"] > 0 and self._is_loopback(default_dev["name"]):
                    return str(int(default_in))

            return None
        except Exception as e:
            logger.error("默认 loopback 设备检测失败: %s", e)
            return None

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        if self._running:
            return

        self._callback = callback
        if not self._selected_device_id:
            self._selected_device_id = self.default_device_id()

        if self._selected_device_id is None:
            available_inputs = [
                d.name for d in self.list_devices()
                if d.input_channels > 0
            ]
            platform_hint = (
                "  macOS:   安装 BlackHole 2ch / Soundflower / Loopback, 并把播放器输出路由到该设备\n"
                if platform.system() == "Darwin"
                else ""
            )
            raise RuntimeError(
                "未找到可用于系统音频回采的输入设备。\n"
                f"{platform_hint}"
                "  Windows: 启用「立体声混音」/ Loopback，或切换到原生 WASAPI 后端\n"
                "  Linux:   使用 PulseAudio Monitor / PipeWire Loopback\n"
                f"  当前输入设备: {available_inputs or ['<none>']}"
            )

        self._selected_device_name = self._lookup_device_name(self._selected_device_id)
        self._running = True
        self._buffer = np.array([], dtype=np.float32)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AudioCapture")
        self._thread.start()
        logger.info(
            "音频捕获已启动 (backend=%s, device=%s, sr=%d, chunk=%.1fs)",
            self.name(), self._selected_device_name or self._selected_device_id,
            self._cfg.sample_rate, self._cfg.chunk_duration,
        )

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        logger.info("音频捕获已停止 (backend=%s)", self.name())

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def selected_device_id(self) -> Optional[str]:
        return self._selected_device_id

    @property
    def selected_device_name(self) -> str:
        return self._selected_device_name or (self._selected_device_id or "")

    def _loop(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("请安装 sounddevice: pip install sounddevice")
            self._running = False
            return

        try:
            device_index = int(self._selected_device_id) if self._selected_device_id is not None else None
            self._stream = sd.InputStream(
                device=device_index,
                samplerate=self._cfg.sample_rate,
                channels=self._cfg.channels,
                dtype="float32",
                blocksize=int(self._cfg.sample_rate * 0.1),
                callback=self._on_audio,
            )
            self._stream.start()
            while self._running:
                time.sleep(0.05)
        except Exception as e:
            logger.error("音频捕获异常: %s", e, exc_info=True)
            self._running = False

    def _on_audio(self, indata: np.ndarray, _frames: int, _time_info, status) -> None:
        if status:
            logger.debug("音频流状态: %s", status)

        audio = indata[:, 0] if indata.ndim > 1 else indata.flatten()

        with self._lock:
            self._buffer = np.concatenate([self._buffer, audio])

            while len(self._buffer) >= self._chunk_samples:
                chunk = self._buffer[:self._chunk_samples].copy()
                advance = self._chunk_samples - self._overlap_samples
                self._buffer = self._buffer[advance:]

                rms = np.sqrt(np.mean(chunk ** 2))
                if rms >= self._cfg.vad_threshold and self._callback:
                    try:
                        self._callback(chunk)
                    except Exception as e:
                        logger.error("音频回调异常: %s", e)

    def _lookup_device_name(self, device_id: str) -> str:
        for device in self.list_devices():
            if device.device_id == str(device_id):
                return device.name
        return str(device_id)

    @staticmethod
    def _is_loopback(name: str) -> bool:
        return any(
            kw in name.lower()
            for kw in ("loopback", "stereo mix", "monitor", "blackhole",
                       "soundflower", "what u hear", "wave out")
        )
