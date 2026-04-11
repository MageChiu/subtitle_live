# ============================================================
# SubtitleLive / core / interfaces.py
# ASR 与翻译的抽象基类 (纯接口, 无具体实现)
# ============================================================
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional

from core.models import ASRResult, TranslationResult


class ASRPlugin(ABC):
    """ASR 引擎插件接口

    实现者只需:
      1. 在 plugins/asr/ 下新建 .py 文件
      2. 继承本类并实现全部抽象方法
      3. 加 @PluginRegistry.register_asr 装饰器
    """

    @abstractmethod
    def name(self) -> str:
        """引擎唯一标识, 用于配置匹配 (如 'whisper')"""
        ...

    @abstractmethod
    def supported_languages(self) -> List[str]:
        """支持的 ISO 639-1 语言代码列表"""
        ...

    @abstractmethod
    def load_model(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "int8",
    ) -> None:
        """加载 / 初始化模型"""
        ...

    @abstractmethod
    def transcribe(
        self,
        audio_data,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> Optional[ASRResult]:
        """识别音频, 返回 ASRResult 或 None"""
        ...

    def unload_model(self) -> None:
        """释放资源 (可选覆写)"""
        pass


class TranslatorPlugin(ABC):
    """翻译引擎插件接口

    实现者只需:
      1. 在 plugins/translator/ 下新建 .py 文件
      2. 继承本类并实现全部抽象方法
      3. 加 @PluginRegistry.register_translator 装饰器
    """

    @abstractmethod
    def name(self) -> str:
        """引擎唯一标识 (如 'google_free')"""
        ...

    @abstractmethod
    def supported_targets(self) -> List[str]:
        """支持的目标语言 ISO 代码列表"""
        ...

    @abstractmethod
    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> Optional[TranslationResult]:
        """翻译文本, 返回 TranslationResult 或 None"""
        ...

    def initialize(self, **kwargs) -> None:
        """初始化引擎 (可选, 如设置 API Key)"""
        pass
