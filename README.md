# SubtitleLive — AI 实时字幕软件

## 功能

- **实时语音识别** — 捕获电脑播放音频, 英语/日语/法语等 15 种语言
- **智能翻译** — Google Free (零配置) 或 OpenAI (高质量) 双后端
- **双语字幕** — 原文 + 翻译同时悬浮显示
- **悬浮窗** — 无边框置顶、半透明圆角、可拖动/缩放、右键菜单
- **后台运行** — 系统托盘常驻, 随时控制
- **插件架构** — ASR / 翻译引擎自动发现, 扩展零侵入

## 项目结构

```
subtitle_live/
├── main.py                          # 入口
├── requirements.txt
│
├── core/                            # 核心层 (与 UI 无关)
│   ├── __init__.py
│   ├── models.py                    #   数据模型
│   ├── interfaces.py                #   ASR / 翻译抽象接口
│   ├── plugin_registry.py           #   插件自动发现 & 注册
│   ├── config.py                    #   分层配置
│   ├── audio_capture.py             #   系统音频捕获
│   └── pipeline.py                  #   字幕管线 (Audio→ASR→翻译)
│
├── plugins/                         # 插件目录 (按类型分包)
│   ├── asr/
│   │   ├── whisper_asr.py           #     Faster-Whisper 引擎
│   │   └── _template.py             #     扩展模板
│   └── translator/
│       ├── google_free.py           #     Google 免费翻译
│       ├── openai_translator.py     #     OpenAI 翻译
│       └── _template.py             #     扩展模板
│
└── ui/                              # 展示层 (PyQt6)
    ├── __init__.py
    ├── overlay.py                   #   悬浮字幕窗口
    └── tray.py                      #   系统托盘应用
```

## 快速开始

```bash
pip install -r requirements.txt
python main.py

# 或指定参数
python main.py -s en -t zh -m small --device cuda
```

## 扩展新引擎

### 添加 ASR 引擎

```python
# plugins/asr/my_engine.py
from core.interfaces import ASRPlugin
from core.models import ASRResult
from core.plugin_registry import PluginRegistry

@PluginRegistry.register_asr
class MyASR(ASRPlugin):
    def name(self): return "my_asr"
    def supported_languages(self): return ["en", "zh"]
    def load_model(self, **kw): ...
    def transcribe(self, audio, **kw): return ASRResult(...)
```

### 添加翻译引擎

```python
# plugins/translator/my_trans.py
from core.interfaces import TranslatorPlugin
from core.models import TranslationResult
from core.plugin_registry import PluginRegistry

@PluginRegistry.register_translator
class MyTrans(TranslatorPlugin):
    def name(self): return "my_trans"
    def supported_targets(self): return ["zh", "en"]
    def translate(self, text, src, tgt): return TranslationResult(...)
```

放入对应目录后重启即生效, 无需修改任何现有代码。

## 架构

```
Audio Capture ──▶ Queue ──▶ ASR Worker ──▶ Queue ──▶ Translate Worker
  (Loopback)        │        (Whisper)        │        (Google/OpenAI)
                    │                          │               │
                    └──── 3 线程异步 ──────────┘          SubtitleEvent
                                                               │
                                                        Overlay UI (PyQt6)
                                                       ┌──────────────────┐
                                                       │ Hello, world!    │
                                                       │ 你好，世界！      │
                                                       └──────────────────┘
```
