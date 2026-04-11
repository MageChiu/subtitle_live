# ============================================================
# plugins / translator / _template.py
# 翻译引擎扩展模板 (示例, 不会被自动加载)
# ============================================================
"""
扩展步骤:
  1. 复制本文件并重命名 (去掉前缀下划线)
  2. 实现所有抽象方法
  3. 取消 @PluginRegistry.register_translator 注释
  4. 重启应用即自动注册
"""
from __future__ import annotations
from typing import List, Optional

from core.interfaces import TranslatorPlugin
from core.models import TranslationResult
from core.plugin_registry import PluginRegistry


# @PluginRegistry.register_translator    # ← 取消注释即可启用
class TemplateTranslator(TranslatorPlugin):

    def name(self) -> str:
        return "template_translator"

    def supported_targets(self) -> List[str]:
        return ["zh", "en"]

    def translate(self, text: str, source_lang: str,
                  target_lang: str) -> Optional[TranslationResult]:
        # 翻译逻辑
        return TranslationResult(text, f"[translated] {text}", source_lang, target_lang)
