# SubtitleLive - AI 实时字幕软件

## 功能特性

- **实时语音识别**: 捕获电脑播放的音频，实时转为文字
- **多语言支持**: 英语、日语、法语等（可扩展）
- **智能翻译**: 自动翻译为中文（可扩展其他目标语言）
- **双语字幕**: 同时显示原文和翻译字幕
- **悬浮显示**: 无边框置顶窗口，不遮挡视频观看
- **后台运行**: 系统托盘常驻，随时开关
- **插件架构**: ASR 和翻译引擎均可扩展

## 安装

```bash
# 1. 克隆项目
git clone <repo-url>
cd subtitle_live

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate   # Windows

# 3. 安装依赖
pip install -r requirements.txt
```

### 音频捕获配置

#### Windows
- 通常自带 "Stereo Mix" 或 "WASAPI Loopback"
- 在声音设置中启用 "立体声混音"

#### macOS
- 安装 [BlackHole](https://github.com/ExistentialAudio/BlackHole)
- 在"音频 MIDI 设置"中创建多输出设备

#### Linux
- PulseAudio 自带 Monitor 设备
- `pactl load-module module-loopback`

## 使用

```bash
python main.py
```

启动后在系统托盘找到 **S** 图标:
1. 右键 → **开始识别**
2. 播放视频，字幕自动显示
3. 右键字幕窗口可控制显示/隐藏原文和翻译

## 快捷操作

| 操作 | 说明 |
|---|---|
| 拖动字幕窗口 | 左键拖动调整位置 |
| 右键字幕窗口 | 显示/隐藏原文或翻译 |
| 托盘右键菜单 | 切换语言、模型、启停 |

## 扩展开发

### 添加新的 ASR 引擎

```python
from plugin_registry import ASRPlugin, ASRResult, PluginRegistry

@PluginRegistry.register_asr
class MyASR(ASRPlugin):
    def name(self) -> str:
        return "my_asr"
    
    def supported_languages(self):
        return ["en", "zh"]
    
    def load_model(self, model_size, device):
        # 加载你的模型
        pass
    
    def transcribe(self, audio_data, sample_rate, language=None):
        # 识别逻辑
        return ASRResult(text="...", language="en", confidence=0.9)
```

### 添加新的翻译引擎

```python
from plugin_registry import TranslatorPlugin, TranslationResult, PluginRegistry

@PluginRegistry.register_translator
class MyTranslator(TranslatorPlugin):
    def name(self) -> str:
        return "my_translator"
    
    def supported_targets(self):
        return ["zh", "en"]
    
    def translate(self, text, source_lang, target_lang):
        # 翻译逻辑
        return TranslationResult(
            original=text, translated="...",
            source_lang=source_lang, target_lang=target_lang
        )
```

## 技术架构

```
Audio Capture → ASR Engine → Translator → Overlay UI
  (Loopback)    (Whisper)   (Pluggable)   (PyQt6)
```

## 依赖

- Python 3.10+
- PyQt6 (GUI)
- faster-whisper (语音识别)
- sounddevice (音频捕获)
