# Debug Session

- Status: FIXED
- Date: 2026-04-11
- Project: subtitle_live
- Symptom: `make run` 在当前 macOS + Loopback 场景下“看起来没有生效”，用户预期是一条可直接工作的默认运行入口。

## Falsifiable Hypotheses

1. `make run` 只是调用了一个过于“通用”的默认命令，没有把当前 macOS 所需的 `--auto-start` / `--audio-device-id` 等参数带进去。
2. `scripts/run.py` 的默认参数在 macOS 上会走到不适合当前用户环境的路径，导致“命令成功执行，但体验上等于没启动”。
3. 当前本地配置文件中的持久化值与用户现在的 Loopback 设备选择不一致，导致 `make run` 读取了错误的默认设备或启动策略。
4. `Makefile` 入口本身没有问题，真正的问题是 macOS 上默认 GUI 交互入口仍然依赖用户找到托盘，而 `make run` 没有显式绕开这一点。

## Evidence Log

- Bootstrap completed. No business logic modified.
- Runtime evidence for `make run`:
  - `make -n run` expands to `python3 scripts/run.py`.
  - Before the fix, `python3 scripts/run.py --dry-run` expanded to bare `main.py` with no `--auto-start`.
  - Current local audio enumeration includes `SubtitleLive Audio` as device `7`.
  - Before the fix, `AudioCapture.find_loopback_device()` resolved to `4` (`BlackHole 2ch`), not the Loopback virtual input.
  - After the fix, `python3 scripts/run.py --dry-run` expands to `main.py --auto-start`.
  - After the fix, `AudioCapture.find_loopback_device()` resolves to `7`, which matches the user-created Loopback virtual input.
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

1. `make run` on macOS now injects `--auto-start` through `scripts/run.py`.
2. Default sounddevice device selection on macOS now prefers user-created stereo virtual input devices such as Loopback outputs.
3. Keep `debug.md` only as a retained record because file deletion was skipped by user preference.
