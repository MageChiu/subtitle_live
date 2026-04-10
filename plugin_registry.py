# ============================================================
# SubtitleLive - 插件注册中心
# ============================================================
"""
插件扩展机制:
  - ASR 引擎和翻译引擎均可通过装饰器注册
  - 新增语言/引擎只需实现接口 + 装饰器, 零侵入
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional, Type
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 数据模型
# ============================================================

@dataclass
class ASRResult:
    """语音识别结果"""
    text: str                           # 识别文本
    language: str                       # 检测到的语言 (ISO 639-1)
    confidence: float = 0.0            # 置信度 0~1
    segments: list = None               # 分段信息 (可选)

    def __post_init__(self):
        if self.segments is None:
            self.segments = []


@dataclass
class TranslationResult:
    """翻译结果"""
    original: str                       # 原文
    translated: str                     # 译文
    source_lang: str                    # 源语言
    target_lang: str                    # 目标语言


@dataclass
class SubtitleEvent:
    """字幕事件 - 管线最终输出"""
    original_text: str                  # 原始识别文本
    translated_text: str                # 翻译后文本
    source_language: str                # 源语言
    target_language: str                # 目标语言
    timestamp: float = 0.0             # 时间戳


# ============================================================
# 抽象基类
# ============================================================

class ASRPlugin(ABC):
    """ASR 引擎插件接口"""

    @abstractmethod
    def name(self) -> str:
        """引擎名称, 用于配置文件匹配"""
        ...

    @abstractmethod
    def supported_languages(self) -> List[str]:
        """支持的语言列表 (ISO 639-1 代码)"""
        ...

    @abstractmethod
    def load_model(self, model_size: str = "base", device: str = "auto",
                   compute_type: str = "int8") -> None:
        """加载模型"""
        ...

    @abstractmethod
    def transcribe(self, audio_data, sample_rate: int = 16000,
                   language: Optional[str] = None) -> Optional[ASRResult]:
        """
        识别音频
        :param audio_data: numpy float32 数组
        :param sample_rate: 采样率
        :param language: 指定语言, None=自动检测
        :return: ASRResult 或 None(无有效内容)
        """
        ...

    def unload_model(self) -> None:
        """卸载模型 (可选实现)"""
        pass


class TranslatorPlugin(ABC):
    """翻译引擎插件接口"""

    @abstractmethod
    def name(self) -> str:
        """引擎名称"""
        ...

    @abstractmethod
    def supported_targets(self) -> List[str]:
        """支持的目标语言列表"""
        ...

    @abstractmethod
    def translate(self, text: str, source_lang: str,
                  target_lang: str) -> Optional[TranslationResult]:
        """
        翻译文本
        :return: TranslationResult 或 None
        """
        ...

    def initialize(self, **kwargs) -> None:
        """初始化 (可选, 如设置 API Key)"""
        pass


# ============================================================
# 插件注册中心
# ============================================================

class PluginRegistry:
    """全局插件注册中心 (单例)"""

    _asr_plugins: Dict[str, Type[ASRPlugin]] = {}
    _translator_plugins: Dict[str, Type[TranslatorPlugin]] = {}

    # ---------- 注册装饰器 ----------

    @classmethod
    def register_asr(cls, plugin_class: Type[ASRPlugin]) -> Type[ASRPlugin]:
        """装饰器: 注册 ASR 插件"""
        instance = plugin_class()
        name = instance.name()
        cls._asr_plugins[name] = plugin_class
        logger.info(f"[PluginRegistry] ASR 插件已注册: {name} "
                     f"(支持语言: {instance.supported_languages()})")
        return plugin_class

    @classmethod
    def register_translator(cls, plugin_class: Type[TranslatorPlugin]) -> Type[TranslatorPlugin]:
        """装饰器: 注册翻译插件"""
        instance = plugin_class()
        name = instance.name()
        cls._translator_plugins[name] = plugin_class
        logger.info(f"[PluginRegistry] 翻译插件已注册: {name} "
                     f"(支持目标: {instance.supported_targets()})")
        return plugin_class

    # ---------- 获取插件 ----------

    @classmethod
    def get_asr(cls, name: str) -> Optional[ASRPlugin]:
        """获取 ASR 插件实例"""
        plugin_cls = cls._asr_plugins.get(name)
        if plugin_cls:
            return plugin_cls()
        logger.error(f"[PluginRegistry] ASR 插件未找到: {name}, "
                      f"可用: {list(cls._asr_plugins.keys())}")
        return None

    @classmethod
    def get_translator(cls, name: str) -> Optional[TranslatorPlugin]:
        """获取翻译插件实例"""
        plugin_cls = cls._translator_plugins.get(name)
        if plugin_cls:
            return plugin_cls()
        logger.error(f"[PluginRegistry] 翻译插件未找到: {name}, "
                      f"可用: {list(cls._translator_plugins.keys())}")
        return None

    @classmethod
    def list_asr(cls) -> Dict[str, List[str]]:
        """列出所有 ASR 插件及其支持的语言"""
        return {name: cls._asr_plugins[name]().supported_languages()
                for name in cls._asr_plugins}

    @classmethod
    def list_translators(cls) -> Dict[str, List[str]]:
        """列出所有翻译插件及其支持的目标语言"""
        return {name: cls._translator_plugins[name]().supported_targets()
                for name in cls._translator_plugins}
