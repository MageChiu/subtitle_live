# ============================================================
# SubtitleLive - 翻译引擎 (Google Free + OpenAI 实现)
# ============================================================
"""
默认提供两个翻译引擎:
  1. GoogleFreeTranslator - 免费 Google 翻译 (无需 API Key)
  2. OpenAITranslator     - 基于 OpenAI/兼容 API 的翻译
"""
from __future__ import annotations
import json
import logging
import re
import urllib.request
import urllib.parse
from typing import List, Optional

from plugin_registry import TranslatorPlugin, TranslationResult, PluginRegistry

logger = logging.getLogger(__name__)


# ============================================================
# 语言名称映射 (用于 OpenAI 提示词)
# ============================================================

LANGUAGE_NAMES = {
    "zh": "Chinese (Simplified)",
    "en": "English",
    "ja": "Japanese",
    "fr": "French",
    "de": "German",
    "es": "Spanish",
    "ko": "Korean",
    "ru": "Russian",
    "it": "Italian",
    "pt": "Portuguese",
    "ar": "Arabic",
    "hi": "Hindi",
    "th": "Thai",
    "vi": "Vietnamese",
}


# ============================================================
# Google Free 翻译引擎
# ============================================================

@PluginRegistry.register_translator
class GoogleFreeTranslator(TranslatorPlugin):
    """
    使用 Google Translate 免费接口
    
    优点: 免费、无需配置
    缺点: 有频率限制, 不适合超高频调用
    """

    # Google 免费翻译 API 端点
    _API_URL = "https://translate.googleapis.com/translate_a/single"

    def name(self) -> str:
        return "google_free"

    def supported_targets(self) -> List[str]:
        return list(LANGUAGE_NAMES.keys())

    def translate(self, text: str, source_lang: str,
                  target_lang: str) -> Optional[TranslationResult]:
        if not text or not text.strip():
            return None

        # 如果源语言和目标语言相同, 直接返回
        if source_lang == target_lang:
            return TranslationResult(
                original=text, translated=text,
                source_lang=source_lang, target_lang=target_lang,
            )

        try:
            params = urllib.parse.urlencode({
                "client": "gtx",
                "sl": source_lang if source_lang != "auto" else "auto",
                "tl": target_lang,
                "dt": "t",
                "q": text,
            })
            url = f"{self._API_URL}?{params}"

            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
            )

            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            # 解析结果: data[0] 是翻译段数组
            translated_parts = []
            if data and data[0]:
                for part in data[0]:
                    if part[0]:
                        translated_parts.append(part[0])

            translated_text = "".join(translated_parts).strip()
            if not translated_text:
                return None

            # 检测到的源语言
            detected_source = data[2] if len(data) > 2 and data[2] else source_lang

            return TranslationResult(
                original=text,
                translated=translated_text,
                source_lang=detected_source,
                target_lang=target_lang,
            )

        except Exception as e:
            logger.error(f"Google 翻译失败: {e}")
            return None


# ============================================================
# OpenAI 兼容翻译引擎
# ============================================================

@PluginRegistry.register_translator
class OpenAITranslator(TranslatorPlugin):
    """
    使用 OpenAI API (或兼容 API, 如 DeepSeek / 通义千问) 进行翻译
    
    优点: 翻译质量高, 支持语境理解
    缺点: 需要 API Key, 有成本
    """

    def __init__(self):
        self._api_key: str = ""
        self._base_url: str = "https://api.openai.com/v1"
        self._model: str = "gpt-4o-mini"

    def name(self) -> str:
        return "openai"

    def supported_targets(self) -> List[str]:
        return list(LANGUAGE_NAMES.keys())

    def initialize(self, api_key: str = "", base_url: str = "",
                   model: str = "gpt-4o-mini", **kwargs) -> None:
        self._api_key = api_key
        if base_url:
            self._base_url = base_url.rstrip("/")
        self._model = model

    def translate(self, text: str, source_lang: str,
                  target_lang: str) -> Optional[TranslationResult]:
        if not text or not text.strip():
            return None
        if not self._api_key:
            logger.error("OpenAI 翻译需要设置 API Key")
            return None

        if source_lang == target_lang:
            return TranslationResult(
                original=text, translated=text,
                source_lang=source_lang, target_lang=target_lang,
            )

        target_name = LANGUAGE_NAMES.get(target_lang, target_lang)
        source_name = LANGUAGE_NAMES.get(source_lang, "the detected language")

        system_prompt = (
            f"You are a professional translator. Translate the following "
            f"{source_name} text to {target_name}. "
            f"Output ONLY the translated text, nothing else. "
            f"Preserve the original meaning and tone. "
            f"If the input is already in {target_name}, return it as-is."
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

            translated_text = data["choices"][0]["message"]["content"].strip()

            return TranslationResult(
                original=text,
                translated=translated_text,
                source_lang=source_lang,
                target_lang=target_lang,
            )

        except Exception as e:
            logger.error(f"OpenAI 翻译失败: {e}")
            return None
