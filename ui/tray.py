# ============================================================
# SubtitleLive / ui / tray.py
# 系统托盘应用
# ============================================================
"""
后台常驻, 托盘右键菜单控制:
  - 启停识别
  - 切换识别/翻译语言
  - 切换模型规格
  - 显示/隐藏字幕
  - 退出
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
from PyQt6.QtCore import Qt, QSize, QTimer

from core.config import AppConfig
from core.models import SubtitleEvent
from core.pipeline import SubtitlePipeline
from ui.overlay import SubtitleOverlay

logger = logging.getLogger(__name__)

# ---- 选项常量 ----

SOURCE_LANGUAGES = {
    "auto": "🌐 自动检测",
    "en":   "🇬🇧 英语",   "ja": "🇯🇵 日语",   "fr": "🇫🇷 法语",
    "de":   "🇩🇪 德语",   "es": "🇪🇸 西班牙语", "ko": "🇰🇷 韩语",
    "ru":   "🇷🇺 俄语",   "it": "🇮🇹 意大利语", "pt": "🇵🇹 葡萄牙语",
    "zh":   "🇨🇳 中文",
}

TARGET_LANGUAGES = {
    "zh": "🇨🇳 中文",    "en": "🇬🇧 English",
    "ja": "🇯🇵 日本語",  "fr": "🇫🇷 Français",
    "de": "🇩🇪 Deutsch", "es": "🇪🇸 Español",
    "ko": "🇰🇷 한국어",
}

MODEL_SIZES = {
    "tiny":     "⚡ tiny  (~39M)",
    "base":     "🔹 base  (~74M)",
    "small":    "🔸 small (~244M)",
    "medium":   "🔷 medium (~769M)",
    "large-v3": "🏆 large-v3 (~1.5G)",
}


class TrayApplication:
    """系统托盘主应用"""

    def __init__(self, config: AppConfig):
        self._cfg = config
        self._app: Optional[QApplication] = None
        self._tray: Optional[QSystemTrayIcon] = None
        self._overlay: Optional[SubtitleOverlay] = None
        self._pipeline: Optional[SubtitlePipeline] = None
        self._is_running = False

    def run(self) -> int:
        self._app = QApplication(sys.argv)
        self._app.setQuitOnLastWindowClosed(False)
        self._app.setApplicationName("SubtitleLive")
        self._app.setApplicationDisplayName("SubtitleLive")

        self._overlay = SubtitleOverlay(self._cfg.overlay)
        self._pipeline = SubtitlePipeline(self._cfg)
        self._pipeline.set_subtitle_callback(self._on_subtitle)

        self._build_tray()

        self._tray.showMessage(
            "SubtitleLive",
            "AI 字幕已启动，右键托盘图标开始识别",
            QSystemTrayIcon.MessageIcon.Information, 3000,
        )
        if self._cfg.auto_start:
            QTimer.singleShot(0, self._start)
        return self._app.exec()

    # ---- 托盘 ----

    def _build_tray(self):
        self._tray = QSystemTrayIcon(self._app)
        self._tray.setIcon(self._make_icon())
        self._tray.setToolTip("SubtitleLive - AI 实时字幕")

        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background: #2a2a3e; color: #fff;
                border: 1px solid #555; border-radius: 8px;
                padding: 6px; font-size: 13px;
            }
            QMenu::item { padding: 6px 24px; border-radius: 4px; }
            QMenu::item:selected { background: #4a4a6e; }
            QMenu::separator { height: 1px; background: #555; margin: 4px 8px; }
        """)

        # 启停
        self._act_toggle = QAction("▶ 开始识别", self._app)
        self._act_toggle.triggered.connect(self._toggle)
        menu.addAction(self._act_toggle)
        menu.addSeparator()

        # 识别语言
        self._src_acts = self._add_radio_submenu(
            menu, "🗣 识别语言", SOURCE_LANGUAGES,
            self._cfg.asr.source_language, self._set_src,
        )

        # 翻译语言
        self._tgt_acts = self._add_radio_submenu(
            menu, "🌍 翻译语言", TARGET_LANGUAGES,
            self._cfg.translator.target_language, self._set_tgt,
        )

        # 模型
        self._model_acts = self._add_radio_submenu(
            menu, "🤖 模型", MODEL_SIZES,
            self._cfg.asr.model_size, self._set_model,
        )

        menu.addSeparator()

        # 字幕窗口
        self._act_overlay = QAction("👁 显示字幕窗口", self._app)
        self._act_overlay.setCheckable(True)
        self._act_overlay.setChecked(True)
        self._act_overlay.triggered.connect(self._toggle_overlay)
        menu.addAction(self._act_overlay)

        menu.addSeparator()

        act_quit = QAction("❌ 退出", self._app)
        act_quit.triggered.connect(self._quit)
        menu.addAction(act_quit)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _add_radio_submenu(self, parent_menu, title, options, current, setter):
        """创建单选子菜单, 返回 {code: QAction}"""
        sub = parent_menu.addMenu(title)
        actions = {}
        for code, label in options.items():
            act = QAction(label, self._app)
            act.setCheckable(True)
            act.setChecked(code == current)
            act.triggered.connect(lambda _, c=code: setter(c))
            sub.addAction(act)
            actions[code] = act
        return actions

    @staticmethod
    def _make_icon() -> QIcon:
        px = QPixmap(QSize(64, 64))
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QColor("#3b82f6"))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(2, 2, 60, 60)
        p.setPen(QColor("#fff"))
        p.setFont(QFont("Arial", 36, QFont.Weight.Bold))
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "S")
        p.end()
        return QIcon(px)

    # ---- 操作 ----

    def _toggle(self):
        if self._is_running:
            self._stop()
        else:
            self._start()

    def _start(self):
        try:
            self._act_toggle.setText("⏳ 加载中...")
            self._act_toggle.setEnabled(False)
            QApplication.processEvents()

            self._pipeline.start()
            self._is_running = True

            self._act_toggle.setText("⏹ 停止识别")
            self._act_toggle.setEnabled(True)
            self._overlay.show()

            self._tray.showMessage(
                "SubtitleLive", "识别已开始",
                QSystemTrayIcon.MessageIcon.Information, 2000,
            )
        except Exception as e:
            self._act_toggle.setText("▶ 开始识别")
            self._act_toggle.setEnabled(True)
            logger.error("启动失败: %s", e, exc_info=True)
            QMessageBox.critical(None, "启动失败", f"{e}\n\n{traceback.format_exc()}")

    def _stop(self):
        self._pipeline.stop()
        self._is_running = False
        self._act_toggle.setText("▶ 开始识别")
        self._overlay.clear_subtitle()

    def _set_src(self, lang: str):
        for c, a in self._src_acts.items():
            a.setChecked(c == lang)
        self._cfg.asr.source_language = lang
        if self._is_running:
            self._pipeline.update_source_language(lang)

    def _set_tgt(self, lang: str):
        for c, a in self._tgt_acts.items():
            a.setChecked(c == lang)
        self._cfg.translator.target_language = lang
        if self._is_running:
            self._pipeline.update_target_language(lang)

    def _set_model(self, size: str):
        for s, a in self._model_acts.items():
            a.setChecked(s == size)
        self._cfg.asr.model_size = size
        if self._is_running:
            self._tray.showMessage(
                "SubtitleLive",
                f"模型切换为 {size}，下次启动生效",
                QSystemTrayIcon.MessageIcon.Information, 2000,
            )

    def _toggle_overlay(self):
        if self._overlay.isVisible():
            self._overlay.hide()
            self._act_overlay.setChecked(False)
        else:
            self._overlay.show()
            self._act_overlay.setChecked(True)

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle()

    def _on_subtitle(self, event: SubtitleEvent):
        self._overlay.update_subtitle(event)

    def _quit(self):
        if self._is_running:
            self._pipeline.stop()
        self._overlay.save_position()
        self._cfg.save()
        self._tray.hide()
        self._app.quit()
