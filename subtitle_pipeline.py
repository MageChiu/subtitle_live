# ============================================================
# SubtitleLive - 字幕管线 (Pipeline)
# ============================================================
"""
核心数据管线: 音频捕获 → ASR → 翻译 → UI 输出

使用多线程 + 队列驱动, 确保各阶段互不阻塞
"""
from __future__ import annotations
import logging
import queue
import threading
import time
from typing import Callable, Optional

import numpy as np

from config import AppConfig
from plugin_registry import (
    PluginRegistry, ASRPlugin, TranslatorPlugin,
    ASRResult, SubtitleEvent,
)
from audio_capture import AudioCapture

logger = logging.getLogger(__name__)


class SubtitlePipeline:
    """
    字幕处理管线
    
    架构:
    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
    │  Audio   │───▶│  Queue   │───▶│   ASR    │───▶│Translate │
    │ Capture  │    │(audio_q) │    │  Thread  │    │  Thread  │
    └──────────┘    └──────────┘    └──────────┘    └──────────┘
                                                          │
                                                          ▼
                                                    ┌──────────┐
                                                    │ subtitle │
                                                    │ callback │
                                                    └──────────┘
    """

    def __init__(self, config: AppConfig):
        self._config = config

        # 核心组件
        self._audio_capture: Optional[AudioCapture] = None
        self._asr_engine: Optional[ASRPlugin] = None
        self._translator: Optional[TranslatorPlugin] = None

        # 队列
        self._audio_queue: queue.Queue = queue.Queue(maxsize=20)
        self._text_queue: queue.Queue = queue.Queue(maxsize=20)

        # 线程
        self._asr_thread: Optional[threading.Thread] = None
        self._translate_thread: Optional[threading.Thread] = None

        # 状态
        self._running = False
        self._model_loaded = False

        # 回调: 产生字幕时调用
        self._subtitle_callback: Optional[Callable[[SubtitleEvent], None]] = None

        # 去重: 避免重复字幕 (重叠音频可能产生相同文本)
        self._last_text = ""
        self._last_text_time = 0.0

        # 字幕日志
        self._subtitle_log_file = None

    # ---------- 公共接口 ----------

    def set_subtitle_callback(self, callback: Callable[[SubtitleEvent], None]) -> None:
        """设置字幕输出回调"""
        self._subtitle_callback = callback

    def load_models(self) -> None:
        """加载 ASR 和翻译模型"""
        cfg = self._config

        # 加载 ASR 引擎
        logger.info(f"正在加载 ASR 引擎: {cfg.asr.engine}")
        self._asr_engine = PluginRegistry.get_asr(cfg.asr.engine)
        if self._asr_engine is None:
            available = PluginRegistry.list_asr()
            raise RuntimeError(
                f"ASR 引擎 '{cfg.asr.engine}' 不可用。\n"
                f"已注册引擎: {available}"
            )
        self._asr_engine.load_model(
            model_size=cfg.asr.model_size,
            device=cfg.asr.device,
            compute_type=cfg.asr.compute_type,
        )

        # 加载翻译引擎
        logger.info(f"正在加载翻译引擎: {cfg.translator.engine}")
        self._translator = PluginRegistry.get_translator(cfg.translator.engine)
        if self._translator is None:
            available = PluginRegistry.list_translators()
            raise RuntimeError(
                f"翻译引擎 '{cfg.translator.engine}' 不可用。\n"
                f"已注册引擎: {available}"
            )

        # 初始化翻译引擎 (如 API Key 等)
        if cfg.translator.engine == "openai":
            self._translator.initialize(
                api_key=cfg.translator.openai_api_key,
                base_url=cfg.translator.openai_base_url,
                model=cfg.translator.openai_model,
            )

        self._model_loaded = True
        logger.info("所有模型加载完成")

    def start(self) -> None:
        """启动管线 (音频捕获 + ASR 线程 + 翻译线程)"""
        if self._running:
            logger.warning("管线已在运行")
            return

        if not self._model_loaded:
            self.load_models()

        self._running = True

        # 打开字幕日志
        if self._config.subtitle_log_file:
            try:
                self._subtitle_log_file = open(
                    self._config.subtitle_log_file, "a", encoding="utf-8"
                )
            except Exception as e:
                logger.error(f"无法打开字幕日志文件: {e}")

        # 启动 ASR 处理线程
        self._asr_thread = threading.Thread(
            target=self._asr_worker, daemon=True, name="ASR-Worker"
        )
        self._asr_thread.start()

        # 启动翻译处理线程
        self._translate_thread = threading.Thread(
            target=self._translate_worker, daemon=True, name="Translate-Worker"
        )
        self._translate_thread.start()

        # 启动音频捕获
        cfg = self._config.audio
        self._audio_capture = AudioCapture(
            device_index=cfg.device_index,
            sample_rate=cfg.sample_rate,
            channels=cfg.channels,
            chunk_duration=cfg.chunk_duration,
            overlap_duration=cfg.overlap_duration,
            vad_threshold=cfg.vad_threshold,
        )
        self._audio_capture.start(callback=self._on_audio_chunk)

        logger.info("字幕管线已启动")

    def stop(self) -> None:
        """停止管线"""
        self._running = False

        # 停止音频捕获
        if self._audio_capture:
            self._audio_capture.stop()

        # 清空队列, 唤醒阻塞的线程
        self._drain_queue(self._audio_queue)
        self._drain_queue(self._text_queue)

        # 等待线程结束
        for t in [self._asr_thread, self._translate_thread]:
            if t and t.is_alive():
                t.join(timeout=3)

        # 关闭日志文件
        if self._subtitle_log_file:
            self._subtitle_log_file.close()
            self._subtitle_log_file = None

        logger.info("字幕管线已停止")

    @property
    def is_running(self) -> bool:
        return self._running

    def update_source_language(self, lang: str) -> None:
        """动态切换源语言"""
        self._config.asr.source_language = lang
        logger.info(f"源语言已切换为: {lang}")

    def update_target_language(self, lang: str) -> None:
        """动态切换目标语言"""
        self._config.translator.target_language = lang
        logger.info(f"目标语言已切换为: {lang}")

    # ---------- 内部 Worker ----------

    def _on_audio_chunk(self, audio_data: np.ndarray) -> None:
        """音频捕获回调 → 放入 ASR 队列"""
        try:
            self._audio_queue.put_nowait(audio_data)
        except queue.Full:
            # 队列满时丢弃最旧的
            try:
                self._audio_queue.get_nowait()
            except queue.Empty:
                pass
            self._audio_queue.put_nowait(audio_data)

    def _asr_worker(self) -> None:
        """ASR 处理线程: 从 audio_queue 取音频 → 识别 → 放入 text_queue"""
        logger.info("ASR 工作线程已启动")

        while self._running:
            try:
                audio_data = self._audio_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            # 获取源语言
            lang = self._config.asr.source_language
            if lang == "auto":
                lang = None

            # 执行 ASR
            try:
                result: Optional[ASRResult] = self._asr_engine.transcribe(
                    audio_data,
                    sample_rate=self._config.audio.sample_rate,
                    language=lang,
                )
            except Exception as e:
                logger.error(f"ASR 处理异常: {e}")
                continue

            if result is None or not result.text.strip():
                continue

            # 去重检查
            now = time.time()
            if (result.text == self._last_text
                    and now - self._last_text_time < 5.0):
                continue
            self._last_text = result.text
            self._last_text_time = now

            logger.debug(f"ASR 结果 [{result.language}]: {result.text}")

            # 放入翻译队列
            try:
                self._text_queue.put_nowait(result)
            except queue.Full:
                try:
                    self._text_queue.get_nowait()
                except queue.Empty:
                    pass
                self._text_queue.put_nowait(result)

        logger.info("ASR 工作线程已退出")

    def _translate_worker(self) -> None:
        """翻译处理线程: 从 text_queue 取文本 → 翻译 → 输出字幕"""
        logger.info("翻译工作线程已启动")

        while self._running:
            try:
                asr_result: ASRResult = self._text_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            target_lang = self._config.translator.target_language
            original_text = asr_result.text
            translated_text = ""

            # 如果源语言与目标语言相同, 跳过翻译
            if asr_result.language == target_lang:
                translated_text = original_text
            else:
                try:
                    tr_result = self._translator.translate(
                        text=original_text,
                        source_lang=asr_result.language,
                        target_lang=target_lang,
                    )
                    if tr_result:
                        translated_text = tr_result.translated
                    else:
                        translated_text = "[翻译失败]"
                except Exception as e:
                    logger.error(f"翻译异常: {e}")
                    translated_text = "[翻译异常]"

            # 构建字幕事件
            event = SubtitleEvent(
                original_text=original_text,
                translated_text=translated_text,
                source_language=asr_result.language,
                target_language=target_lang,
                timestamp=time.time(),
            )

            logger.debug(f"字幕: {original_text} → {translated_text}")

            # 写入日志
            if self._subtitle_log_file:
                try:
                    ts = time.strftime("%H:%M:%S")
                    self._subtitle_log_file.write(
                        f"[{ts}] [{asr_result.language}→{target_lang}] "
                        f"{original_text} | {translated_text}\n"
                    )
                    self._subtitle_log_file.flush()
                except Exception:
                    pass

            # 触发回调
            if self._subtitle_callback:
                try:
                    self._subtitle_callback(event)
                except Exception as e:
                    logger.error(f"字幕回调异常: {e}")

        logger.info("翻译工作线程已退出")

    @staticmethod
    def _drain_queue(q: queue.Queue) -> None:
        """清空队列"""
        while True:
            try:
                q.get_nowait()
            except queue.Empty:
                break
