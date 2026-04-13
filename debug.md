# Debug Session

- Status: OPEN
- Date: 2026-04-11
- Project: subtitle_live
- Symptom: 目标语言无法按预期设置，例如希望输出中文繁体或日语时，实际结果仍然不是期望语言。

## Falsifiable Hypotheses

1. macOS 上用户无法稳定通过托盘菜单操作，导致目标语言设置动作根本没有发生。
2. UI 的目标语言列表或配置结构没有覆盖用户需要的语言代码，例如 `zh-TW`。
3. 翻译插件虽然收到切换请求，但并不支持该目标语言，或内部把它回退到默认值。
4. 配置层中的目标语言值改变了，但运行中的字幕管线没有读取到更新后的值。

## Evidence Log

- Bootstrap completed. No business logic modified for this issue yet.
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

1. Read target-language related UI, config, and translator code paths.
2. Add minimal instrumentation around target-language selection and translation execution.
3. Ask user to reproduce once the observation points are in place.
