# ============================================================
# SubtitleLive / ui / overlay.py
# 悬浮字幕窗口 (PyQt6)
# ============================================================
"""
特性:
  - 无边框置顶, 半透明圆角
  - 可拖动 / 可缩放
  - 双语字幕 (原文 + 翻译)
  - 右键菜单调节显示
  - 自动淡出
  - 跨线程安全 (pyqtSignal)
"""
from __future__ import annotations

import logging
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QMenu,
    QApplication, QSizeGrip,
)
from PyQt6.QtCore import Qt, QTimer, QPoint, pyqtSignal, pyqtSlot, QSize
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath,
    QAction, QMouseEvent, QPaintEvent, QCursor,
)

from core.config import OverlayConfig
from core.models import SubtitleEvent

logger = logging.getLogger(__name__)


class SubtitleOverlay(QWidget):
    """悬浮字幕窗口"""

    # 跨线程信号
    subtitle_signal = pyqtSignal(object)     # SubtitleEvent
    clear_signal = pyqtSignal()

    def __init__(self, config: OverlayConfig, parent=None):
        super().__init__(parent)
        self._cfg = config
        self._drag_pos: Optional[QPoint] = None
        self._last_update = 0.0

        self._setup_window()
        self._setup_labels()
        self._setup_timer()
        self.subtitle_signal.connect(self._on_subtitle)
        self.clear_signal.connect(self._on_clear)

    # ---- 初始化 ----

    def _setup_window(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
            | Qt.WindowType.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        c = self._cfg
        self.resize(c.width, c.height)
        self.setMinimumSize(QSize(300, 60))

        if c.x >= 0 and c.y >= 0:
            self.move(c.x, c.y)
        else:
            screen = QApplication.primaryScreen()
            if screen:
                g = screen.availableGeometry()
                self.move((g.width() - c.width) // 2, g.height() - c.height - 100)

        self._grip = QSizeGrip(self)
        self._grip.setFixedSize(16, 16)

    def _setup_labels(self):
        c = self._cfg
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(4)

        # 原文
        self._lbl_orig = QLabel("")
        self._lbl_orig.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_orig.setWordWrap(True)
        self._lbl_orig.setFont(QFont(c.font_family, c.font_size_original))
        self._lbl_orig.setStyleSheet(f"color: {c.original_color};")
        self._lbl_orig.setVisible(c.show_original)
        layout.addWidget(self._lbl_orig)

        # 翻译
        self._lbl_trans = QLabel("")
        self._lbl_trans.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._lbl_trans.setWordWrap(True)
        f = QFont(c.font_family, c.font_size_translated)
        f.setBold(True)
        self._lbl_trans.setFont(f)
        self._lbl_trans.setStyleSheet(f"color: {c.translated_color};")
        self._lbl_trans.setVisible(c.show_translated)
        layout.addWidget(self._lbl_trans)

    def _setup_timer(self):
        self._timer = QTimer(self)
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._check_hide)
        self._timer.start()

    # ---- 公共 API (线程安全) ----

    def update_subtitle(self, event: SubtitleEvent) -> None:
        self.subtitle_signal.emit(event)

    def clear_subtitle(self) -> None:
        self.clear_signal.emit()

    def set_show_original(self, show: bool):
        self._cfg.show_original = show
        self._lbl_orig.setVisible(show)

    def set_show_translated(self, show: bool):
        self._cfg.show_translated = show
        self._lbl_trans.setVisible(show)

    def save_position(self):
        pos = self.pos()
        self._cfg.x, self._cfg.y = pos.x(), pos.y()
        self._cfg.width, self._cfg.height = self.width(), self.height()

    # ---- 信号槽 ----

    @pyqtSlot(object)
    def _on_subtitle(self, event: SubtitleEvent):
        self._last_update = time.time()
        if self._cfg.show_original:
            self._lbl_orig.setText(event.original_text)
        if self._cfg.show_translated:
            self._lbl_trans.setText(self._format_translations(event))
        if not self.isVisible():
            self.show()

    @pyqtSlot()
    def _on_clear(self):
        self._lbl_orig.setText("")
        self._lbl_trans.setText("")

    def _check_hide(self):
        if self._last_update and time.time() - self._last_update > self._cfg.auto_hide_seconds:
            self._lbl_orig.setText("")
            self._lbl_trans.setText("")

    # ---- 绘制 ----

    def paintEvent(self, event: QPaintEvent):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0, 0, float(self.width()), float(self.height()),
            self._cfg.border_radius, self._cfg.border_radius,
        )
        bg = QColor(self._cfg.bg_color)
        bg.setAlphaF(self._cfg.opacity)
        p.fillPath(path, bg)
        p.end()

    # ---- 鼠标拖动 ----

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag_pos and e.buttons() & Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e: QMouseEvent):
        self._drag_pos = None
        self.save_position()

    # ---- 右键菜单 ----

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a3e; color: white;
                border: 1px solid #444; border-radius: 6px; padding: 4px;
            }
            QMenu::item:selected { background-color: #4a4a6e; }
        """)

        c = self._cfg

        # 原文开关
        a1 = QAction(f"{'✓' if c.show_original else '  '} 显示原文", self)
        a1.triggered.connect(lambda: self.set_show_original(not c.show_original))
        menu.addAction(a1)

        # 翻译开关
        a2 = QAction(f"{'✓' if c.show_translated else '  '} 显示翻译", self)
        a2.triggered.connect(lambda: self.set_show_translated(not c.show_translated))
        menu.addAction(a2)

        menu.addSeparator()

        # 字号
        af_up = QAction("字号 +", self)
        af_up.triggered.connect(self._font_up)
        menu.addAction(af_up)

        af_dn = QAction("字号 -", self)
        af_dn.triggered.connect(self._font_down)
        menu.addAction(af_dn)

        menu.addSeparator()

        # 透明度
        ao_up = QAction("背景加深", self)
        ao_up.triggered.connect(lambda: self._set_opacity(min(1.0, c.opacity + 0.1)))
        menu.addAction(ao_up)

        ao_dn = QAction("背景减淡", self)
        ao_dn.triggered.connect(lambda: self._set_opacity(max(0.2, c.opacity - 0.1)))
        menu.addAction(ao_dn)

        menu.exec(QCursor.pos())

    def _font_up(self):
        c = self._cfg
        c.font_size_original = min(30, c.font_size_original + 2)
        c.font_size_translated = min(36, c.font_size_translated + 2)
        self._apply_fonts()

    def _font_down(self):
        c = self._cfg
        c.font_size_original = max(8, c.font_size_original - 2)
        c.font_size_translated = max(10, c.font_size_translated - 2)
        self._apply_fonts()

    def _apply_fonts(self):
        c = self._cfg
        self._lbl_orig.setFont(QFont(c.font_family, c.font_size_original))
        f = QFont(c.font_family, c.font_size_translated)
        f.setBold(True)
        self._lbl_trans.setFont(f)

    def _set_opacity(self, v: float):
        self._cfg.opacity = v
        self.update()

    @staticmethod
    def _format_translations(event: SubtitleEvent) -> str:
        if event.translations:
            return "\n".join(
                f"[{lang}] {text}" if len(event.translations) > 1 else text
                for lang, text in event.translations
            )
        return event.translated_text
