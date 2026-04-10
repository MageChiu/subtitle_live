# ============================================================
# SubtitleLive - 系统音频捕获模块
# ============================================================
"""
通过系统 Loopback 设备捕获桌面播放的音频流

平台支持:
  - Windows: WASAPI Loopback / Stereo Mix
  - macOS:   BlackHole / Soundflower (需额外安装)
  - Linux:   PulseAudio Monitor
"""
from __future__ import annotations
import logging
import threading
import time
import platform
from typing import Callable, Optional, List

import numpy as np

logger = logging.getLogger(__name__)


class AudioCapture:
    """
    系统音频捕获器
    
    工作原理:
    1. 扫描系统音频设备, 找到 Loopback / Monitor 设备
    2. 以 16kHz 单声道采样捕获音频
    3. 将音频按固定长度分块, 通过回调传递给 ASR
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

        # 音频缓冲区
        self._buffer: np.ndarray = np.array([], dtype=np.float32)
        self._lock = threading.Lock()

        # 计算块大小 (样本数)
        self._chunk_samples = int(self._sample_rate * self._chunk_duration)
        self._overlap_samples = int(self._sample_rate * self._overlap_duration)

    # ---------- 设备发现 ----------

    @staticmethod
    def list_devices() -> List[dict]:
        """列出所有可用音频设备"""
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            result = []
            for i, dev in enumerate(devices):
                result.append({
                    "index": i,
                    "name": dev["name"],
                    "channels_in": dev["max_input_channels"],
                    "channels_out": dev["max_output_channels"],
                    "sample_rate": dev["default_samplerate"],
                    "is_loopback": AudioCapture._is_loopback_device(dev["name"]),
                })
            return result
        except Exception as e:
            logger.error(f"枚举音频设备失败: {e}")
            return []

    @staticmethod
    def find_loopback_device() -> Optional[int]:
        """自动查找系统 Loopback 设备"""
        try:
            import sounddevice as sd
        except ImportError:
            raise ImportError("请安装 sounddevice: pip install sounddevice")

        devices = sd.query_devices()
        system = platform.system()

        # 按优先级搜索关键词
        keywords = []
        if system == "Windows":
            keywords = ["stereo mix", "loopback", "what u hear", "wave out"]
        elif system == "Darwin":
            keywords = ["blackhole", "soundflower", "loopback"]
        elif system == "Linux":
            keywords = ["monitor", "loopback"]

        for keyword in keywords:
            for i, dev in enumerate(devices):
                if (keyword in dev["name"].lower()
                        and dev["max_input_channels"] > 0):
                    logger.info(f"找到 Loopback 设备: [{i}] {dev['name']}")
                    return i

        # 未找到, 使用默认输入设备
        default = sd.default.device[0]
        if default is not None and default >= 0:
            logger.warning(f"未找到 Loopback 设备, 使用默认输入: "
                           f"[{default}] {devices[default]['name']}")
            return int(default)

        return None

    @staticmethod
    def _is_loopback_device(name: str) -> bool:
        keywords = ["loopback", "stereo mix", "monitor", "blackhole",
                     "soundflower", "what u hear", "wave out"]
        name_lower = name.lower()
        return any(kw in name_lower for kw in keywords)

    # ---------- 捕获控制 ----------

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        """
        开始捕获音频
        
        :param callback: 音频块回调, 参数为 float32 numpy 数组
        """
        if self._running:
            logger.warning("音频捕获已在运行")
            return

        self._callback = callback

        # 自动检测设备
        if self._device_index is None:
            self._device_index = self.find_loopback_device()
            if self._device_index is None:
                raise RuntimeError(
                    "未找到可用的音频输入设备。\n"
                    "Windows: 请在声音设置中启用「立体声混音」\n"
                    "macOS: 请安装 BlackHole (https://github.com/ExistentialAudio/BlackHole)\n"
                    "Linux: 请确保 PulseAudio 正在运行"
                )

        self._running = True
        self._buffer = np.array([], dtype=np.float32)
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        logger.info(f"音频捕获已启动 (设备={self._device_index}, "
                     f"采样率={self._sample_rate}, 块长={self._chunk_duration}s)")

    def stop(self) -> None:
        """停止捕获"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        if self._stream is not None:
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

    # ---------- 内部逻辑 ----------

    def _capture_loop(self) -> None:
        """音频捕获线程主循环"""
        try:
            import sounddevice as sd
        except ImportError:
            logger.error("sounddevice 未安装")
            self._running = False
            return

        try:
            self._stream = sd.InputStream(
                device=self._device_index,
                samplerate=self._sample_rate,
                channels=self._channels,
                dtype="float32",
                blocksize=int(self._sample_rate * 0.1),  # 100ms 块
                callback=self._audio_callback,
            )
            self._stream.start()

            # 保持线程存活
            while self._running:
                time.sleep(0.05)

        except Exception as e:
            logger.error(f"音频捕获异常: {e}", exc_info=True)
            self._running = False

    def _audio_callback(self, indata: np.ndarray, frames: int,
                         time_info, status) -> None:
        """sounddevice 的流式回调"""
        if status:
            logger.debug(f"音频流状态: {status}")

        # 转为单声道 float32
        audio = indata[:, 0] if indata.ndim > 1 else indata.flatten()

        with self._lock:
            self._buffer = np.concatenate([self._buffer, audio])

            # 当缓冲区积累到一个完整块时, 触发回调
            while len(self._buffer) >= self._chunk_samples:
                chunk = self._buffer[:self._chunk_samples].copy()

                # 保留重叠部分用于下一块
                advance = self._chunk_samples - self._overlap_samples
                self._buffer = self._buffer[advance:]

                # VAD: 静音检测
                rms = np.sqrt(np.mean(chunk ** 2))
                if rms >= self._vad_threshold and self._callback:
                    try:
                        self._callback(chunk)
                    except Exception as e:
                        logger.error(f"音频回调处理异常: {e}")
