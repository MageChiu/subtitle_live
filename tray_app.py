# ============================================================
# SubtitleLive - 系统托盘应用
# ============================================================
"""
系统托盘应用: 后台运行, 托盘菜单控制

功能:
- 开始/停止识别
- 切换识别语言
- 切换翻译目标语言
- 切换 ASR 模型大小
- 显示/隐藏字幕窗口
- 退出应用
"""
from __future__ import annotations
import logging
import sys
import traceback
from typing import Optional

from PyQt6.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QMessageBox,
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PyQt6.QtCore import Qt, QSize

from config import AppConfig
from subtitle_pipeline import SubtitlePipeline
from overlay_ui import SubtitleOverlay
from plugin_registry import SubtitleEvent

logger = logging.getLogger(__name__)


# ============================================================
# 语言/模型选项
# ============================================================

SOURCE_LANGUAGES = {
    "auto":  "🌐 自动检测",
    "en":    "🇬🇧 英语 (English)",
    "ja":    "🇯🇵 日语 (日本語)",
    "fr":    "🇫🇷 法语 (Français)",
    "de":    "🇩🇪 德语 (Deutsch)",
    "es":    "🇪🇸 西班牙语 (Español)",
    "ko":    "🇰🇷 韩语 (한국어)",
    "ru":    "🇷🇺 俄语 (Русский)",
    "it":    "🇮🇹 意大利语 (Italiano)",
    "pt":    "🇵🇹 葡萄牙语 (Português)",
    "zh":    "🇨🇳 中文",
}

TARGET_LANGUAGES = {
    "zh":   "🇨🇳 中文 (简体)",
    "en":   "🇬🇧 English",
    "ja":   "🇯🇵 日本語",
    "fr":   "🇫🇷 Français",
    "de":   "🇩🇪 Deutsch",
    "es":   "🇪🇸 Español",
    "ko":   "🇰🇷 한국어",
}

MODEL_SIZES = {
    "tiny":      "⚡ tiny (最快, ~39M)",
    "base":      "🔹 base (平衡, ~74M)",
    "small":     "🔸 small (更准, ~244M)",
    "medium":    "🔷 medium (高质, ~769M)",
    "large-v3":  "🏆 large-v3 (最佳, ~1550M)",
}


class TrayApplication:
    """系统托盘应用主类"""

    def __init__(self, config: AppConfig):
        self._config = config
        self._app: Optional[QApplication] = None
        self._tray: Optional[QSystemTrayIcon] = None
        self._overlay: Optional[SubtitleOverlay] = None
        self._pipeline: Optional[SubtitlePipeline] = None
        self._is_running = False

    # ---------- 启动 ----------

    def run(self) -> int:
        """启动应用 (阻塞, 直到退出)"""
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("SubtitleLive")

        # 创建悬浮窗
        self._overlay = SubtitleOverlay(self._config.overlay)

        # 创建管线
        self._pipeline = SubtitlePipeline(self._config)
        self._pipeline.set_subtitle_callback(self._on_subtitle)

        # 创建托盘
        self._create_tray()

        # 显示通知
        self._tray.showMessage(
            "SubtitleLive",
            "AI 字幕软件已启动，右键托盘图标开始识别",
            QSystemTrayIcon.MessageIcon.Information,
            3000,
        )

        return self._app.exec()

    # ---------- 托盘 ----------

    def _create_tray(self):
        """创建系统托盘图标和菜单"""
        self._tray = QSystemTrayIcon(self._app)
        self._tray.setIcon(self._create_icon())
        self._tray.setToolTip("SubtitleLive - AI 实时字幕")

        # 构建菜单
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a3e;
                color: #ffffff;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 6px;
                font-size: 13px;
            }
            QMenu::item {
                padding: 6px 24px;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #4a4a6e;
            }
            QMenu::separator {
                height: 1px;
                background: #555;
                margin: 4px 8px;
            }
        """)

        # 开始/停止
        self._action_toggle = QAction("▶ 开始识别", self._app)
        self._action_toggle.triggered.connect(self._toggle_recognition)
        menu.addAction(self._action_toggle)

        menu.addSeparator()

        # 识别语言子菜单
        lang_menu = menu.addMenu("🗣 识别语言")
        self._source_lang_actions = {}
        for code, label in SOURCE_LANGUAGES.items():
            action = QAction(label, self._app)
            action.setCheckable(True)
            action.setChecked(code == self._config.asr.source_language)
            action.triggered.connect(lambda checked, c=code: self._set_source_lang(c))
            lang_menu.addAction(action)
            self._source_lang_actions[code] = action

        # 翻译语言子菜单
        target_menu = menu.addMenu("🌍 翻译语言")
        self._target_lang_actions = {}
        for code, label in TARGET_LANGUAGES.items():
            action = QAction(label, self._app)
            action.setCheckable(True)
            action.setChecked(code == self._config.translator.target_language)
            action.triggered.connect(lambda checked, c=code: self._set_target_lang(c))
            target_menu.addAction(action)
            self._target_lang_actions[code] = action

        # 模型大小子菜单
        model_menu = menu.addMenu("🤖 模型")
        self._model_actions = {}
        for size, label in MODEL_SIZES.items():
            action = QAction(label, self._app)
            action.setCheckable(True)
            action.setChecked(size == self._config.asr.model_size)
            action.triggered.connect(lambda checked, s=size: self._set_model_size(s))
            model_menu.addAction(action)
            self._model_actions[size] = action

        menu.addSeparator()

        # 显示/隐藏字幕
        self._action_show_overlay = QAction("👁 显示字幕窗口", self._app)
        self._action_show_overlay.setCheckable(True)
        self._action_show_overlay.setChecked(True)
        self._action_show_overlay.triggered.connect(self._toggle_overlay)
        menu.addAction(self._action_show_overlay)

        menu.addSeparator()

        # 退出
        action_quit = QAction("❌ 退出", self._app)
        action_quit.triggered.connect(self._quit)
        menu.addAction(action_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _create_icon(self) -> QIcon:
        """生成托盘图标 (蓝色 S)"""
        size = 64
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(QColor(0, 0, 0, 0))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 圆形背景
        painter.setBrush(QColor("#3b82f6"))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, size - 4, size - 4)

        # 字母 S
        painter.setPen(QColor("#ffffff"))
        font = QFont("Arial", 36, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "S")

        painter.end()
        return QIcon(pixmap)

    # ---------- 操作处理 ----------

    def _toggle_recognition(self):
        """开始/停止识别"""
        if self._is_running:
            self._stop_recognition()
        else:
            self._start_recognition()

    def _start_recognition(self):
        """开始识别"""
        try:
            self._action_toggle.setText("⏳ 加载模型中...")
            self._action_toggle.setEnabled(False)
            QApplication.processEvents()

            self._pipeline.start()
            self._is_running = True

            self._action_toggle.setText("⏹ 停止识别")
            self._action_toggle.setEnabled(True)
            self._overlay.show()

            self._tray.showMessage(
                "SubtitleLive",
                f"识别已开始\n语言: {SOURCE_LANGUAGES.get(self._config.asr.source_language, 'auto')}\n"
                f"翻译: {TARGET_LANGUAGES.get(self._config.translator.target_language, 'zh')}",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        except Exception as e:
            self._action_toggle.setText("▶ 开始识别")
            self._action_toggle.setEnabled(True)
            logger.error(f"启动失败: {e}", exc_info=True)
            QMessageBox.critical(
                None, "启动失败",
                f"无法启动识别:\n\n{str(e)}\n\n{traceback.format_exc()}"
            )

    def _stop_recognition(self):
        """停止识别"""
        self._pipeline.stop()
        self._is_running = False
        self._action_toggle.setText("▶ 开始识别")
        self._overlay.clear_subtitle()

    def _set_source_lang(self, lang: str):
        """切换识别语言"""
        for code, action in self._source_lang_actions.items():
            action.setChecked(code == lang)
        self._config.asr.source_language = lang
        if self._is_running:
            self._pipeline.update_source_language(lang)
        logger.info(f"识别语言 → {lang}")

    def _set_target_lang(self, lang: str):
        """切换翻译目标语言"""
        for code, action in self._target_lang_actions.items():
            action.setChecked(code == lang)
        self._config.translator.target_language = lang
        if self._is_running:
            self._pipeline.update_target_language(lang)
        logger.info(f"翻译语言 → {lang}")

    def _set_model_size(self, size: str):
        """切换模型大小 (需要重启识别)"""
        for s, action in self._model_actions.items():
            action.setChecked(s == size)
        self._config.asr.model_size = size

        if self._is_running:
            self._tray.showMessage(
                "SubtitleLive",
                f"模型已切换为 {size}，将在下次启动识别时生效",
                QSystemTrayIcon.MessageIcon.Information,
                2000,
            )
        logger.info(f"模型 → {size}")

    def _toggle_overlay(self):
        """显示/隐藏字幕窗口"""
        if self._overlay.isVisible():
            self._overlay.hide()
            self._action_show_overlay.setChecked(False)
        else:
            self._overlay.show()
            self._action_show_overlay.setChecked(True)

    def _on_tray_activated(self, reason):
        """托盘图标双击 = 切换识别"""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_recognition()

    def _on_subtitle(self, event: SubtitleEvent):
        """管线字幕回调"""
        self._overlay.update_subtitle(event)

    def _quit(self):
        """退出应用"""
        logger.info("正在退出...")
        if self._is_running:
            self._pipeline.stop()
        self._overlay.save_position()
        self._config.save()
        self._tray.hide()
        self._app.quit()
