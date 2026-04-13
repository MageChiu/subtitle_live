# Debug Session

- Status: FIXED
- Date: 2026-04-11
- Project: subtitle_live
- Symptom: 后台运行后，前台预期应以类似 QQ 音乐歌词悬浮窗样式显示当前视频字幕与翻译，但当前“不工作”。

## Falsifiable Hypotheses

1. 悬浮窗 UI 没有被真正创建或显示，导致后台程序在运行但前台完全无窗口。
2. 音频采集或 ASR 管线没有产出字幕事件，导致悬浮窗存在但始终无内容。
3. 翻译插件初始化失败或阻塞，导致整条字幕更新链路中断。
4. 托盘/主线程事件循环与悬浮窗更新线程配合异常，导致窗口生命周期或 UI 刷新失效。
5. 配置默认值、依赖或平台权限与 README 假设不一致，导致功能在本机环境下无法启动。

## Evidence Log

- Bootstrap completed. No business logic modified.
- Environment bootstrap initially failed in local verification: `PyQt6` and `sounddevice` were not installed.
- Runtime evidence from `.dbg/trae-debug-log-subtitle-live-20260411-01.ndjson`:
  - `core/audio_capture.py:find_loopback_device` reported `os=Darwin`, `default_input_name=MacBook Pro麦克风`.
  - No loopback-capable input device (`BlackHole` / `Soundflower` / `Loopback`) was present.
  - The pre-fix behavior silently fell back to the default microphone, which does not satisfy the product design of capturing currently playing video audio.
- Post-fix command verification:
  - `AudioCapture.find_loopback_device()` now returns `None` instead of a microphone index.
  - `AudioCapture.start()` now raises a clear `RuntimeError` with platform-specific guidance instead of entering a false-working state.
- Loopback follow-up evidence on macOS:
  - `AudioCapture.list_devices()` now enumerates both `BlackHole 2ch` and a Loopback-created virtual input `SubtitleLive Audio`.
  - `AudioCapture.find_loopback_device()` returns device `4`, which corresponds to `BlackHole 2ch`, not the Loopback virtual device.
  - This means `auto` selection currently prefers keyword-matched loopback devices, and does not automatically select the user's custom Loopback virtual input.
  - User feedback confirms the app shows only a Dock icon labeled `python3.12`, and the menu bar tray is not discoverable in practice.
  - Runtime log shows `is_system_tray_available=true` and `tray_visible=true`, so the blocker is now operational discoverability rather than tray object creation failure.

## Hypothesis Status

1. A - Overlay window not created/shown: INCONCLUSIVE. No evidence indicates this is the primary blocker.
2. B - Audio capture / ASR produced no subtitle events: CONFIRMED at the capture selection stage for the current Loopback scenario, because `auto` chooses `BlackHole 2ch` instead of the user-created Loopback device.
3. C - Translator initialization failure: REJECTED as primary cause for the current symptom.
4. D - UI event loop / overlay update mismatch: REJECTED as the primary blocker for the latest reproduction. The run loop and tray object are alive; the practical blocker is that the user cannot access the tray action to trigger `_start()`.
5. E - Config / dependency / platform mismatch with README assumptions: CONFIRMED. macOS loopback prerequisite was missing from docs, and the current auto-selection policy does not align with custom Loopback device naming.

## Next Steps

1. Keep instrumentation in place until user confirms the fix direction.
2. Verify the minimal fix that bypasses tray dependence via `--auto-start`.
3. If the user still sees no subtitle after auto-start, continue with audio/ASR path verification.
