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
│   ├── audio_capture.py             #   统一音频采集 Facade
│   ├── audio_backends/              #   平台音频后端
│   │   ├── selector.py              #     后端选择器
│   │   ├── sounddevice_backend.py   #     Python fallback
│   │   └── native_backend.py        #     Native 后端插槽
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

## 构建与运行入口

```bash
# 当前平台构建
make build

# 当前平台运行
make run

# 目标平台构建配置
make build-windows
make build-macos
make build-linux
```

也可以直接使用脚本入口:

```bash
# 构建并生成 build/<platform>/build-manifest.json
python3 scripts/build.py

# 安装依赖后再构建
python3 scripts/build.py --install-deps

# 运行并显式指定音频后端
python3 scripts/run.py --audio-backend sounddevice_loopback --log-level DEBUG

# macOS 上如果菜单栏托盘不易发现, 可直接自动开始识别
python3 scripts/run.py --audio-backend sounddevice_loopback --audio-device-id 7 --auto-start --log-level DEBUG
```

- `scripts/build.py` 负责按平台生成构建配置、执行 Python 字节码校验，并产出平台 manifest。
- `scripts/run.py` 负责统一运行入口，可注入音频后端、设备 ID、capture mode 等参数。
- `Makefile` 负责给类 Unix 开发环境提供标准入口；Windows 上可直接执行 `python scripts/build.py` 和 `python scripts/run.py`。
- `--auto-start` 适合 macOS 上只看到 Dock 图标、不方便通过菜单栏托盘手动点击“开始识别”的场景。

### macOS 额外前提

- 本项目要识别“正在播放的视频声音”，macOS 必须先提供系统音频回采设备。
- 请先安装 `BlackHole 2ch`、`Soundflower` 或 `Loopback` 之一，并在“音频 MIDI 设置”里把播放器输出路由到该设备。
- 如果系统里只有 `MacBook Pro麦克风` 这类普通麦克风，程序无法直接捕获播放器声音，也就不会产出字幕。
- 当前版本会在找不到回采设备时直接报错提示，而不是静默退回麦克风。

#### 安装方法

- 推荐方案: `BlackHole 2ch`

```bash
brew install --cask blackhole-2ch
```

- 安装完成后需要重启 macOS 或至少重新登录一次，系统才能正确加载虚拟音频驱动。
- 官方下载页: [BlackHole](https://existential.audio/blackhole/)
- Homebrew 也提供 `blackhole-16ch`、`blackhole-64ch`，但本项目默认推荐 `2ch` 即可。

- 商业方案: `Loopback`
  - 官网下载: [Loopback](https://rogueamoeba.com/loopback/)
  - 适合按应用精细路由音频，比如只抓 `Chrome` 或只抓某个播放器。

- 旧系统兜底: `Soundflower`
  - 官方 Releases: [Soundflower Releases](https://github.com/mattingalls/Soundflower/releases)
  - 更适合旧版 Intel Mac；Apple Silicon 和较新系统优先使用 `BlackHole`。

#### 配置步骤

1. 安装 `BlackHole 2ch` 或其他虚拟回采设备。
2. 打开 `应用程序 -> 实用工具 -> 音频 MIDI 设置`。
3. 点击左下角 `+`，创建 `多输出设备`。
4. 同时勾选 `BlackHole 2ch` 和你实际听声音的输出设备，例如 `MacBook Pro 扬声器` 或 `AirPods`。
5. 在 `系统设置 -> 声音 -> 输出` 中把输出设备切换到刚创建的 `多输出设备`。
6. 启动本项目后，音频后端选择 `sounddevice_loopback`，或继续保持 `auto` 让程序自动探测。

#### 验证方式

```bash
python3 scripts/run.py --audio-backend sounddevice_loopback --log-level DEBUG
```

- 如果配置正确，程序应能检测到 `BlackHole` 之类的 loopback 设备。
- 如果仍提示没有可用回采设备，请先确认系统输出是否真的切到了 `多输出设备`。

### 音频后端策略

- `audio_capture.py` 现在只作为统一入口, 上层 `pipeline` 不再直接依赖某个平台 API。
- 默认策略是 `native-first`:
  - `Windows` 预留 `native_windows_wasapi`
  - `macOS` 预留 `native_macos_coreaudio`
  - `Linux` 预留 `native_linux_pipewire`
- 当前仓库里真正可运行的是 `sounddevice_loopback` fallback, 适合虚拟声卡或 loopback 输入场景。
- 后续可将 Rust/C 动态库接入 `native_*` 后端, 而无需改动 ASR、翻译和 UI 管线。

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
  (Backend)         │        (Whisper)        │        (Google/OpenAI)
                    │                          │               │
                    └──── 3 线程异步 ──────────┘          SubtitleEvent
                                                               │
                                                        Overlay UI (PyQt6)
                                                       ┌──────────────────┐
                                                       │ Hello, world!    │
                                                       │ 你好，世界！      │
                                                       └──────────────────┘
```

音频层现已拆分为:

```text
AudioCapture Facade
  └── Backend Selector
      ├── native_windows_wasapi   (预留)
      ├── native_macos_coreaudio  (预留)
      ├── native_linux_pipewire   (预留)
      └── sounddevice_loopback    (当前 fallback)
```
