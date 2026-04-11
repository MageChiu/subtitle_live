# ============================================================
# SubtitleLive / core / plugin_registry.py
# 插件注册中心 (单例)
# ============================================================
"""
使用装饰器自动注册, 新增引擎零侵入:

    @PluginRegistry.register_asr
    class MyASR(ASRPlugin): ...

    @PluginRegistry.register_translator
    class MyTrans(TranslatorPlugin): ...
"""
from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Dict, List, Optional, Type

from core.interfaces import ASRPlugin, TranslatorPlugin

logger = logging.getLogger(__name__)


class PluginRegistry:
    """全局插件注册表"""

    _asr: Dict[str, Type[ASRPlugin]] = {}
    _translator: Dict[str, Type[TranslatorPlugin]] = {}

    # -------- 装饰器 --------

    @classmethod
    def register_asr(cls, plugin_cls: Type[ASRPlugin]) -> Type[ASRPlugin]:
        inst = plugin_cls()
        cls._asr[inst.name()] = plugin_cls
        logger.info(
            "[Registry] ASR  %-12s  languages=%s",
            inst.name(), inst.supported_languages(),
        )
        return plugin_cls

    @classmethod
    def register_translator(cls, plugin_cls: Type[TranslatorPlugin]) -> Type[TranslatorPlugin]:
        inst = plugin_cls()
        cls._translator[inst.name()] = plugin_cls
        logger.info(
            "[Registry] TRANS %-12s  targets=%s",
            inst.name(), inst.supported_targets(),
        )
        return plugin_cls

    # -------- 获取实例 --------

    @classmethod
    def get_asr(cls, name: str) -> Optional[ASRPlugin]:
        if name in cls._asr:
            return cls._asr[name]()
        logger.error("ASR '%s' 未注册, 可用: %s", name, list(cls._asr))
        return None

    @classmethod
    def get_translator(cls, name: str) -> Optional[TranslatorPlugin]:
        if name in cls._translator:
            return cls._translator[name]()
        logger.error("Translator '%s' 未注册, 可用: %s", name, list(cls._translator))
        return None

    # -------- 枚举 --------

    @classmethod
    def list_asr(cls) -> Dict[str, List[str]]:
        return {n: cls._asr[n]().supported_languages() for n in cls._asr}

    @classmethod
    def list_translators(cls) -> Dict[str, List[str]]:
        return {n: cls._translator[n]().supported_targets() for n in cls._translator}

    # -------- 自动发现 --------

    @classmethod
    def discover(cls, package_path: str) -> None:
        """
        自动扫描指定包路径下的所有模块, 触发装饰器注册

        :param package_path: 如 'plugins.asr' 或 'plugins.translator'
        """
        try:
            pkg = importlib.import_module(package_path)
        except ImportError as e:
            logger.error("无法导入包 %s: %s", package_path, e)
            return

        pkg_dir = Path(pkg.__file__).parent
        for finder, module_name, is_pkg in pkgutil.iter_modules([str(pkg_dir)]):
            if module_name.startswith("_"):
                continue
            fqn = f"{package_path}.{module_name}"
            try:
                importlib.import_module(fqn)
                logger.debug("已加载插件模块: %s", fqn)
            except Exception as e:
                logger.warning("加载插件模块 %s 失败: %s", fqn, e)
