# ============================================================
# plugins / translator / google_free.py
# Google 免费翻译引擎
# ============================================================
"""
使用 Google Translate 免费端点, 零配置即可使用
限制: 有频率限制, 不适合极高频调用
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from typing import List, Optional

from core.interfaces import TranslatorPlugin
from core.models import TranslationResult
from core.plugin_registry import PluginRegistry

logger = logging.getLogger(__name__)

_API_URL = "https://translate.googleapis.com/translate_a/single"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# 所有支持的目标语言
SUPPORTED = [
    "zh", "en", "ja", "fr", "de", "es",
    "ko", "ru", "it", "pt", "ar", "hi", "th", "vi",
]


@PluginRegistry.register_translator
class GoogleFreeTranslator(TranslatorPlugin):
    """Google Translate 免费接口"""

    def name(self) -> str:
        return "google_free"

    def supported_targets(self) -> List[str]:
        return list(SUPPORTED)

    def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str,
    ) -> Optional[TranslationResult]:
        if not text or not text.strip():
            return None
        if source_lang == target_lang:
            return TranslationResult(text, text, source_lang, target_lang)

        try:
            params = urllib.parse.urlencode({
                "client": "gtx",
                "sl": "auto" if source_lang == "auto" else source_lang,
                "tl": target_lang,
                "dt": "t",
                "q": text,
            })

            req = urllib.request.Request(
                f"{_API_URL}?{params}",
                headers={"User-Agent": _UA},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            parts = []
            if data and data[0]:
                for seg in data[0]:
                    if seg[0]:
                        parts.append(seg[0])

            translated = "".join(parts).strip()
            if not translated:
                return None

            detected = data[2] if len(data) > 2 and data[2] else source_lang

            return TranslationResult(
                original=text,
                translated=translated,
                source_lang=detected,
                target_lang=target_lang,
            )
        except Exception as e:
            logger.error("Google 翻译失败: %s", e)
            return None
