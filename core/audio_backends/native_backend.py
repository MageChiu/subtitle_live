from __future__ import annotations

import importlib.util
import logging
import platform
import threading
import time
from pathlib import Path
from typing import Callable, List, Optional

import numpy as np

from core.config import AudioConfig
from core.interfaces import AudioCaptureBackend
from core.models import AudioDeviceInfo

logger = logging.getLogger(__name__)


class NativeBackendBase(AudioCaptureBackend):
    """长期方案的 Native 后端占位.

    当前仓库先完成架构分层与后端选择, 真正的 Rust/C 动态库在后续接入.
    """

    def __init__(self, cfg: AudioConfig, backend_name: str, platform_name: str, hint: str):
        self._cfg = cfg
        self._backend_name = backend_name
        self._platform_name = platform_name
        self._hint = hint

    def name(self) -> str:
        return self._backend_name

    def is_supported(self) -> bool:
        return False

    def list_devices(self) -> List[AudioDeviceInfo]:
        return []

    def default_device_id(self) -> Optional[str]:
        return None

    def start(self, callback: Callable) -> None:
        raise RuntimeError(self.unavailable_reason())

    def stop(self) -> None:
        return None

    @property
    def is_running(self) -> bool:
        return False

    @property
    def selected_device_id(self) -> Optional[str]:
        return self._cfg.device_id or None

    @property
    def selected_device_name(self) -> str:
        return self._cfg.device_id or "<native-pending>"

    def unavailable_reason(self) -> str:
        lib_hint = ""
        if self._cfg.native_library_path:
            lib_path = Path(self._cfg.native_library_path).expanduser()
            if lib_path.exists():
                lib_hint = f"已提供动态库路径 `{lib_path}`，但当前 Python 桥接尚未接入。"
            else:
                lib_hint = f"指定的动态库不存在: `{lib_path}`。"
        return (
            f"{self._platform_name} Native 后端 `{self._backend_name}` 尚未接入动态库实现。"
            f"{self._hint}"
            f"{lib_hint}"
        )


class NativeWindowsWASAPIBackend(NativeBackendBase):
    def __init__(self, cfg: AudioConfig):
        self._cfg = cfg
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callback: Optional[Callable[[np.ndarray], None]] = None
        self._buffer = np.array([], dtype=np.float32)
        self._lock = threading.Lock()
        self._chunk_samples = int(cfg.sample_rate * cfg.chunk_duration)
        self._overlap_samples = int(cfg.sample_rate * cfg.overlap_duration)
        self._selected_device_id = cfg.device_id or None
        self._selected_device_name = ""

    def name(self) -> str:
        return "native_windows_wasapi"

    def is_supported(self) -> bool:
        return (
            platform.system() == "Windows"
            and importlib.util.find_spec("soundcard") is not None
        )

    def unavailable_reason(self) -> str:
        if platform.system() != "Windows":
            return "当前不是 Windows 环境。"
        return "缺少 `soundcard` 依赖，无法启用 Windows WASAPI loopback 后端。"

    def list_devices(self) -> List[AudioDeviceInfo]:
        if platform.system() != "Windows":
            return []
        try:
            import soundcard as sc

            speakers = sc.all_speakers()
            devices: List[AudioDeviceInfo] = []
            for idx, speaker in enumerate(speakers):
                device_id = self._speaker_id(speaker, idx)
                channels = int(getattr(speaker, "channels", 2) or 2)
                devices.append(
                    AudioDeviceInfo(
                        device_id=device_id,
                        name=getattr(speaker, "name", str(speaker)),
                        backend=self.name(),
                        platform="Windows",
                        input_channels=max(2, channels),
                        output_channels=channels,
                        default_sample_rate=float(self._cfg.sample_rate),
                        is_loopback=True,
                    )
                )
            return devices
        except Exception as e:
            logger.error("枚举 Windows WASAPI 输出设备失败: %s", e)
            return []

    def default_device_id(self) -> Optional[str]:
        if platform.system() != "Windows":
            return None
        try:
            import soundcard as sc

            speaker = sc.default_speaker()
            if speaker is None:
                return None
            devices = self.list_devices()
            default_name = getattr(speaker, "name", str(speaker))
            for idx, candidate in enumerate(sc.all_speakers()):
                if getattr(candidate, "name", str(candidate)) == default_name:
                    return self._speaker_id(candidate, idx)
            return None
        except Exception as e:
            logger.error("获取默认 Windows 输出设备失败: %s", e)
            return None

    def start(self, callback: Callable[[np.ndarray], None]) -> None:
        if self._running:
            return
        if not self.is_supported():
            raise RuntimeError(self.unavailable_reason())

        self._callback = callback
        if not self._selected_device_id:
            self._selected_device_id = self.default_device_id()
        if not self._selected_device_id:
            raise RuntimeError("未找到可用于 Windows WASAPI loopback 的输出设备。")

        speaker = self._resolve_speaker(self._selected_device_id)
        if speaker is None:
            raise RuntimeError(f"找不到指定的 Windows 输出设备: {self._selected_device_id}")

        self._selected_device_name = getattr(speaker, "name", str(speaker))
        self._running = True
        self._buffer = np.array([], dtype=np.float32)
        self._thread = threading.Thread(
            target=self._capture_loop,
            args=(speaker,),
            daemon=True,
            name="WindowsWASAPICapture",
        )
        self._thread.start()
        logger.info(
            "Windows WASAPI loopback 已启动 (device=%s, sr=%d, chunk=%.1fs)",
            self._selected_device_name,
            self._cfg.sample_rate,
            self._cfg.chunk_duration,
        )

    def stop(self) -> None:
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        logger.info("Windows WASAPI loopback 已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def selected_device_id(self) -> Optional[str]:
        return self._selected_device_id

    @property
    def selected_device_name(self) -> str:
        return self._selected_device_name or (self._selected_device_id or "")

    def _capture_loop(self, speaker) -> None:
        try:
            microphone = self._get_loopback_microphone(speaker)
            blocksize = max(int(self._cfg.sample_rate * 0.2), 1024)
            numframes = max(int(self._cfg.sample_rate * 0.05), 256)
            with microphone.recorder(
                samplerate=self._cfg.sample_rate,
                channels=[0, 1],
                blocksize=blocksize,
            ) as recorder:
                while self._running:
                    data = recorder.record(numframes=numframes)
                    if data is None or len(data) == 0:
                        time.sleep(0.01)
                        continue
                    mono = self._to_mono(data)
                    self._consume_audio(mono)
        except Exception as e:
            logger.error("Windows WASAPI loopback 捕获异常: %s", e, exc_info=True)
            self._running = False

    def _consume_audio(self, audio: np.ndarray) -> None:
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
                        logger.error("Windows 音频回调异常: %s", e)

    def _resolve_speaker(self, device_id: str):
        try:
            import soundcard as sc

            for idx, speaker in enumerate(sc.all_speakers()):
                if self._speaker_id(speaker, idx) == device_id:
                    return speaker
        except Exception:
            return None
        return None

    @staticmethod
    def _speaker_id(speaker, idx: int) -> str:
        speaker_id = getattr(speaker, "id", None)
        if speaker_id:
            return str(speaker_id)
        return f"{idx}:{getattr(speaker, 'name', str(speaker))}"

    @staticmethod
    def _get_loopback_microphone(speaker):
        import soundcard as sc

        for candidate in (
            getattr(speaker, "id", None),
            getattr(speaker, "name", None),
            str(speaker),
        ):
            if not candidate:
                continue
            try:
                return sc.get_microphone(candidate, include_loopback=True)
            except Exception:
                continue
        raise RuntimeError("无法为当前 Windows 输出设备创建 loopback 麦克风")

    @staticmethod
    def _to_mono(data: np.ndarray) -> np.ndarray:
        if data.ndim == 1:
            return data.astype(np.float32, copy=False)
        if data.shape[1] == 1:
            return data[:, 0].astype(np.float32, copy=False)
        return data[:, :2].mean(axis=1).astype(np.float32, copy=False)


class NativeMacOSCoreAudioBackend(NativeBackendBase):
    def __init__(self, cfg: AudioConfig):
        super().__init__(
            cfg,
            backend_name="native_macos_coreaudio",
            platform_name="macOS",
            hint="建议后续由 Rust/C 层接入 ScreenCaptureKit/CoreAudio 或虚拟设备采集。",
        )


class NativeLinuxPipewireBackend(NativeBackendBase):
    def __init__(self, cfg: AudioConfig):
        super().__init__(
            cfg,
            backend_name="native_linux_pipewire",
            platform_name="Linux",
            hint="建议后续由 Rust/C 层接入 PipeWire/PulseAudio monitor。",
        )
