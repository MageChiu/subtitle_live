from __future__ import annotations

from pathlib import Path
from typing import Callable, List, Optional

from core.config import AudioConfig
from core.interfaces import AudioCaptureBackend
from core.models import AudioDeviceInfo


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
        super().__init__(
            cfg,
            backend_name="native_windows_wasapi",
            platform_name="Windows",
            hint="建议后续由 Rust/C 层实现 WASAPI loopback 并通过 Python 桥接调用。",
        )


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
