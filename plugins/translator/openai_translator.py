# ============================================================
# plugins / translator / openai_translator.py
# OpenAI / 兼容 API 翻译引擎
# ============================================================
"""
适配 OpenAI、DeepSeek、通义千问等 Chat Completions 兼容 API
需要设置 API Key 才能使用
"""
from __future__ import annotations

import json
import logging
import urllib.request
from typing import List, Optional

from core.interfaces import TranslatorPlugin
from core.models import TranslationResult
from core.plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "zh": "Chinese (Simplified)", "en": "English",
    "ja": "Japanese", "fr": "French", "de": "German",
    "es": "Spanish", "ko": "Korean", "ru": "Russian",
    "it": "Italian", "pt": "Portuguese", "ar": "Arabic",
    "hi": "Hindi", "th": "Thai", "vi": "Vietnamese",
}


@PluginRegistry.register_translator
class OpenAITranslator(TranslatorPlugin):
    """OpenAI Chat Completions 翻译引擎"""

    def __init__(self):
        self._api_key = ""
        self._base_url = "https://api.openai.com/v1"
        self._model = "gpt-4o-mini"

    def name(self) -> str:
        return "openai"

    def supported_targets(self) -> List[str]:
        return list(LANGUAGE_NAMES)

    def initialize(
        self,
        api_key: str = "",
        base_url: str = "",
        model: str = "gpt-4o-mini",
        **kwargs,
    ) -> None:
        self._api_key = api_key
        if base_url:
            self._base_url = base_url.rstrip("/")
        self._model = model

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> Optional[TranslationResult]:
        if not text or not text.strip():
            return None
        if not self._api_key:
            logger.error("OpenAI 翻译需要 API Key")
            return None
        if source_lang == target_lang:
            return TranslationResult(text, text, source_lang, target_lang)

        target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        source_name = LANGUAGE_NAMES.get(source_lang, "the detected language")

        system_prompt = (
            f"You are a professional translator. "
            f"Translate the following {source_name} text to {target_name}. "
            f"Output ONLY the translated text. Preserve meaning and tone."
        )

        try:
            payload = json.dumps({
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ],
                "temperature": 0.3,
                "max_tokens": 500,
            }).encode("utf-8")

            req = urllib.request.Request(
                f"{self._base_url}/chat/completions",
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._api_key}",
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            translated = data["choices"][0]["message"]["content"].strip()
            return TranslationResult(text, translated, source_lang, target_lang)

        except Exception as e:
            logger.error("OpenAI 翻译失败: %s", e)
            return None
