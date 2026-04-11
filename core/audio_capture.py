# ============================================================
# SubtitleLive / core / audio_capture.py
# 系统音频 Loopback 捕获器
# ============================================================
from __future__ import annotations

import logging
import platform
import threading
import time
from typing import Callable, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


class AudioCapture:
    """
    系统桌面音频捕获器

    工作流: sounddevice InputStream → 内部环形缓冲 → 按固定窗口回调
    """

    def __init__(
        self,
        device_index: Optional[int] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        chunk_duration: float = 3.0,
        overlap_duration: float = 0.5,
        vad_threshold: float = 0.01,
    ):
        self._device_index = device_index
        self._sample_rate = sample_rate
        self._channels = channels
        self._chunk_duration = chunk_duration
        self._overlap_duration = overlap_duration
        self._vad_threshold = vad_threshold

        self._stream = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None

        self._buffer = np.array([], dtype=np.float32)
        self._lock = threading.Lock()

        self._chunk_samples = int(sample_rate * chunk_duration)
        self._overlap_samples = int(sample_rate * overlap_duration)

    # ---- 设备发现 ----

    @staticmethod
    def list_devices() -> List[dict]:
        try:
            import sounddevice as sd
            return [
                {
                    "index": i,
                    "name": d["name"],
                    "input_ch": d["max_input_channels"],
                    "output_ch": d["max_output_channels"],
                    "rate": d["default_samplerate"],
                    "is_loopback": AudioCapture._is_loopback(d["name"]),
                }
                for i, d in enumerate(sd.query_devices())
            ]
        except Exception as e:
            logger.error("枚举音频设备失败: %s", e)
            return []

    @staticmethod
    def find_loopback_device() -> Optional[int]:
        import sounddevice as sd

        devices = sd.query_devices()
        os_name = platform.system()

        keywords = {
            "Windows": ["stereo mix", "loopback", "what u hear", "wave out"],
            "Darwin":  ["blackhole", "soundflower", "loopback"],
            "Linux":   ["monitor", "loopback"],
        }.get(os_name, ["loopback", "monitor"])

        for kw in keywords:
            for i, d in enumerate(devices):
                if kw in d["name"].lower() and d["max_input_channels"] > 0:
                    logger.info("Loopback 设备: [%d] %s", i, d["name"])
                    return i

        default_in = sd.default.device[0]
        if default_in is not None and default_in >= 0:
            logger.warning(
                "未找到 Loopback, 使用默认输入: [%d] %s",
                default_in, devices[default_in]["name"],
            )
            return int(default_in)
        return None

    @staticmethod
    def _is_loopback(name: str) -> bool:
        return any(
            kw in name.lower()
            for kw in ("loopback", "stereo mix", "monitor", "blackhole",
                       "soundflower", "what u hear", "wave out")
        )

    # ---- 控制 ----

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        if self._running:
            return
        self._callback = callback

        if self._device_index is None:
            self._device_index = self.find_loopback_device()
            if self._device_index is None:
                raise RuntimeError(
                    "未找到可用音频输入设备。\n"
                    "  Windows: 启用「立体声混音」\n"
                    "  macOS:   安装 BlackHole\n"
                    "  Linux:   确保 PulseAudio 运行"
                )

        self._running = True
        self._buffer = np.array([], dtype=np.float32)
        self._thread = threading.Thread(target=self._loop, daemon=True, name="AudioCapture")
        self._thread.start()
        logger.info("音频捕获已启动 (device=%s, sr=%d, chunk=%.1fs)",
                     self._device_index, self._sample_rate, self._chunk_duration)

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
        logger.info("音频捕获已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    # ---- 内部 ----

    def _loop(self) -> None:
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("请安装 sounddevice: pip install sounddevice")
            self._running = False
            return

        try:
            self._stream = sd.InputStream(
                device=self._device_index,
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=int(self._sample_rate * 0.1),
                callback=self._on_audio,
            )
            self._stream.start()
            while self._running:
                time.sleep(0.05)
        except Exception as e:
            logger.error("音频捕获异常: %s", e, exc_info=True)
            self._running = False

    def _on_audio(self, indata: np.ndarray, frames: int, time_info, status) -> None:
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
                if rms >= self._vad_threshold and self._callback:
                    try:
                        self._callback(chunk)
                    except Exception as e:
                        logger.error("音频回调异常: %s", e)
