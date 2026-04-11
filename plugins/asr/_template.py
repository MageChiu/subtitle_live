# ============================================================
# plugins / asr / _template.py
# ASR 引擎扩展模板 (示例, 不会被自动加载)
# ============================================================
"""
扩展步骤:
  1. 复制本文件, 重命名为 my_engine.py
  2. 实现所有抽象方法
  3. 去掉文件名前缀下划线 (确保不以 _ 开头)
  4. 重启应用, PluginRegistry.discover() 会自动加载
"""
from __future__ import annotations
from typing import List, Optional
import numpy as np

from core.interfaces import ASRPlugin
from core.models import ASRResult
from core.plugin_registry import PluginRegistry


# @PluginRegistry.register_asr          # ← 取消注释即可启用
class TemplateASR(ASRPlugin):

    def name(self) -> str:
        return "template_asr"

    def supported_languages(self) -> List[str]:
        return ["en", "zh"]

    def load_model(self, model_size="base", device="auto", compute_type="int8"):
        # 加载你的模型
        pass

    def transcribe(self, audio_data: np.ndarray, sample_rate=16000,
                   language=None) -> Optional[ASRResult]:
        # 识别逻辑
        return ASRResult(text="example", language="en", confidence=0.9)
