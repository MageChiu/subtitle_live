# ============================================================
# SubtitleLive / core / pipeline.py
# 字幕管线: Audio → ASR → Translate → UI
# ============================================================
from __future__ import annotations

import logging
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np

from core.config import AppConfig
from core.interfaces import ASRPlugin, TranslatorPlugin
from core.models import ASRResult, SubtitleEvent
from core.plugin_registry import PluginRegistry
from core.audio_capture import AudioCapture

logger = logging.getLogger(__name__)


class SubtitlePipeline:
    """
    三线程异步管线

        AudioCapture ──▶ audio_q ──▶ ASR Worker ──▶ text_q ──▶ Translate Worker
                                                                       │
                                                                subtitle_callback
    """

    def __init__(self, config: AppConfig):
        self._cfg = config

        self._audio_capture: Optional[AudioCapture] = None
        self._asr: Optional[ASRPlugin] = None
        self._translator: Optional[TranslatorPlugin] = None

        self._audio_q: queue.Queue[np.ndarray] = queue.Queue(maxsize=20)
        self._text_q: queue.Queue[ASRResult] = queue.Queue(maxsize=20)

        self._asr_thread: Optional[threading.Thread] = None
        self._trans_thread: Optional[threading.Thread] = None

        self._running = False
        self._model_loaded = False
        self._subtitle_cb: Optional[Callable[[SubtitleEvent], None]] = None

        # 去重
        self._last_text = ""
        self._last_text_ts = 0.0

        self._log_fh = None

    # ---- 公共接口 ----

    def set_subtitle_callback(self, cb: Callable[[SubtitleEvent], None]) -> None:
        self._subtitle_cb = cb

    def load_models(self) -> None:
        cfg = self._cfg

        # ASR
        self._asr = PluginRegistry.get_asr(cfg.asr.engine)
        if not self._asr:
            raise RuntimeError(
                f"ASR '{cfg.asr.engine}' 未注册。可用: {PluginRegistry.list_asr()}"
            )
        self._asr.load_model(
            model_size=cfg.asr.model_size,
            device=cfg.asr.device,
            compute_type=cfg.asr.compute_type,
        )

        # Translator
        self._translator = PluginRegistry.get_translator(cfg.translator.engine)
        if not self._translator:
            raise RuntimeError(
                f"Translator '{cfg.translator.engine}' 未注册。"
                f"可用: {PluginRegistry.list_translators()}"
            )
        if cfg.translator.engine == "openai":
            self._translator.initialize(
                api_key=cfg.translator.openai_api_key,
                base_url=cfg.translator.openai_base_url,
                model=cfg.translator.openai_model,
            )
        self._model_loaded = True
        logger.info("模型加载完成")

    def start(self) -> None:
        if self._running:
            return
        if not self._model_loaded:
            self.load_models()

        self._running = True

        if self._cfg.subtitle_log_file:
            try:
                self._log_fh = open(self._cfg.subtitle_log_file, "a", encoding="utf-8")
            except Exception as e:
                logger.error("字幕日志文件打开失败: %s", e)

        self._asr_thread = threading.Thread(target=self._asr_worker, daemon=True, name="ASR")
        self._trans_thread = threading.Thread(target=self._trans_worker, daemon=True, name="Trans")
        self._asr_thread.start()
        self._trans_thread.start()

        ac = self._cfg.audio
        self._audio_capture = AudioCapture(
            backend=ac.backend,
            device_id=ac.device_id,
            device_index=ac.device_index,
            capture_mode=ac.capture_mode,
            prefer_native_backend=ac.prefer_native_backend,
            allow_sounddevice_fallback=ac.allow_sounddevice_fallback,
            native_library_path=ac.native_library_path,
            sample_rate=ac.sample_rate,
            channels=ac.channels,
            chunk_duration=ac.chunk_duration,
            overlap_duration=ac.overlap_duration,
            vad_threshold=ac.vad_threshold,
        )
        self._audio_capture.start(callback=self._on_audio)
        logger.info("管线已启动")

    def stop(self) -> None:
        self._running = False
        if self._audio_capture:
            self._audio_capture.stop()
        self._drain(self._audio_q)
        self._drain(self._text_q)
        for t in (self._asr_thread, self._trans_thread):
            if t and t.is_alive():
                t.join(timeout=3)
        if self._log_fh:
            self._log_fh.close()
            self._log_fh = None
        logger.info("管线已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    def update_source_language(self, lang: str) -> None:
        self._cfg.asr.source_language = lang

    def update_target_language(self, lang: str) -> None:
        # #region debug-point B:update-target-language
        try:
            import json, urllib.request; urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId": "subtitle-live-20260413-target-lang", "runId": "pre-fix", "hypothesisId": "B", "location": "core/pipeline.py:update_target_language", "msg": "[DEBUG] 管线更新目标语言", "data": {"target_language": lang}}).encode(), headers={"Content-Type": "application/json"}), timeout=0.2).read()
        except Exception:
            pass
        # #endregion
        self._cfg.translator.target_language = lang
        self._cfg.translator.target_languages = [lang]

    # ---- Workers ----

    def _on_audio(self, chunk: np.ndarray) -> None:
        try:
            self._audio_q.put_nowait(chunk)
        except queue.Full:
            try:
                self._audio_q.get_nowait()
            except queue.Empty:
                pass
            self._audio_q.put_nowait(chunk)

    def _asr_worker(self) -> None:
        logger.info("ASR worker 启动")
        while self._running:
            try:
                audio = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue

            lang = self._cfg.asr.source_language
            lang = None if lang == "auto" else lang

            try:
                result = self._asr.transcribe(
                    audio, sample_rate=self._cfg.audio.sample_rate, language=lang,
                )
            except Exception as e:
                logger.error("ASR 异常: %s", e)
                continue

            if not result or not result.text.strip():
                continue

            # 去重
            now = time.time()
            if result.text == self._last_text and now - self._last_text_ts < 5:
                continue
            self._last_text = result.text
            self._last_text_ts = now

            try:
                self._text_q.put_nowait(result)
            except queue.Full:
                try:
                    self._text_q.get_nowait()
                except queue.Empty:
                    pass
                self._text_q.put_nowait(result)

    def _trans_worker(self) -> None:
        logger.info("翻译 worker 启动")
        debug_target_logged = False
        while self._running:
            try:
                asr_res: ASRResult = self._text_q.get(timeout=0.5)
            except queue.Empty:
                continue

            targets = tuple(
                lang for lang in self._cfg.translator.target_languages
                if lang and lang.strip()
            ) or (self._cfg.translator.target_language,)
            target = targets[0]
            original = asr_res.text
            if not debug_target_logged:
                debug_target_logged = True
                # #region debug-point C:first-translate-target
                try:
                    import json, urllib.request; urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:7777/event", data=json.dumps({"sessionId": "subtitle-live-20260413-target-lang", "runId": "pre-fix", "hypothesisId": "C", "location": "core/pipeline.py:_trans_worker", "msg": "[DEBUG] 翻译线程读取到首个目标语言", "data": {"target_language": target, "target_languages": list(targets), "source_language": asr_res.language, "original_preview": original[:80]}}).encode(), headers={"Content-Type": "application/json"}), timeout=0.2).read()
                except Exception:
                    pass
                # #endregion
            translations: list[tuple[str, str]] = []
            for current_target in targets:
                if asr_res.language == current_target:
                    current_translated = original
                else:
                    try:
                        tr = self._translator.translate(original, asr_res.language, current_target)
                        current_translated = tr.translated if tr else "[翻译失败]"
                    except Exception as e:
                        logger.error("翻译异常: %s", e)
                        current_translated = "[翻译异常]"
                translations.append((current_target, current_translated))
            translated = translations[0][1] if translations else original

            event = SubtitleEvent(
                original_text=original,
                translated_text=translated,
                source_language=asr_res.language,
                target_language=target,
                translations=tuple(translations),
                timestamp=time.time(),
            )

            if self._log_fh:
                try:
                    ts = time.strftime("%H:%M:%S")
                    joined = " || ".join(f"{lang}:{text}" for lang, text in translations)
                    self._log_fh.write(
                        f"[{ts}] [{asr_res.language}→{','.join(targets)}] "
                        f"{original} | {joined}\n"
                    )
                    self._log_fh.flush()
                except Exception:
                    pass

            if self._subtitle_cb:
                try:
                    self._subtitle_cb(event)
                except Exception as e:
                    logger.error("回调异常: %s", e)

    @staticmethod
    def _drain(q: queue.Queue) -> None:
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break
