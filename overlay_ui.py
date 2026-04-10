# ============================================================
# SubtitleLive - 悬浮字幕窗口 (Overlay UI)
# ============================================================
"""
基于 PyQt6 的无边框置顶悬浮窗口

特性:
- 无边框、置顶 (Always-on-Top)
- 半透明圆角背景
- 可拖动 (鼠标左键)
- 双语字幕显示 (原文 + 翻译)
- 右键菜单控制
- 自动淡出 (无新字幕时)
"""
from __future__ import annotations
import logging
import time
from typing import Optional

from PyQt6.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QMenu,
    QApplication, QSizeGrip,
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, pyqtSignal, pyqtSlot, QSize,
)
from PyQt6.QtGui import (
    QFont, QColor, QPainter, QPainterPath, QAction,
    QMouseEvent, QPaintEvent, QCursor,
)

from config import OverlayConfig
from plugin_registry import SubtitleEvent

logger = logging.getLogger(__name__)


class SubtitleOverlay(QWidget):
    """悬浮字幕窗口"""

    # 跨线程信号 (从管线线程安全地更新 UI)
    subtitle_signal = pyqtSignal(SubtitleEvent)
    clear_signal = pyqtSignal()

    def __init__(self, config: OverlayConfig, parent=None):
        super().__init__(parent)
        self._config = config
        self._drag_pos: Optional[QPoint] = None
        self._last_update_time: float = 0

        self._init_window()
        self._init_labels()
        self._init_timer()
        self._connect_signals()

    # ---------- 初始化 ----------

    def _init_window(self):
        """配置窗口属性"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint        # 无边框
            | Qt.WindowType.WindowStaysOnTopHint      # 置顶
            | Qt.WindowType.Tool                      # 不在任务栏显示
            | Qt.WindowType.WindowDoesNotAcceptFocus   # 不抢焦点
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        # 尺寸与位置
        cfg = self._config
        self.resize(cfg.width, cfg.height)
        self.setMinimumSize(QSize(300, 60))

        if cfg.x >= 0 and cfg.y >= 0:
            self.move(cfg.x, cfg.y)
        else:
            # 默认居中偏下
            screen = QApplication.primaryScreen()
            if screen:
                geo = screen.availableGeometry()
                x = (geo.width() - cfg.width) // 2
                y = geo.height() - cfg.height - 100
                self.move(x, y)

        # 右下角缩放手柄
        self._size_grip = QSizeGrip(self)
        self._size_grip.setFixedSize(16, 16)

    def _init_labels(self):
        """创建字幕标签"""
        cfg = self._config
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 10, 20, 10)
        layout.setSpacing(4)

        # 原文标签
        self._original_label = QLabel("")
        self._original_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._original_label.setWordWrap(True)
        self._original_label.setFont(QFont(cfg.font_family, cfg.font_size_original))
        self._original_label.setStyleSheet(f"color: {cfg.original_color};")
        self._original_label.setVisible(cfg.show_original)
        layout.addWidget(self._original_label)

        # 翻译标签
        self._translated_label = QLabel("")
        self._translated_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._translated_label.setWordWrap(True)
        font = QFont(cfg.font_family, cfg.font_size_translated)
        font.setBold(True)
        self._translated_label.setFont(font)
        self._translated_label.setStyleSheet(f"color: {cfg.translated_color};")
        self._translated_label.setVisible(cfg.show_translated)
        layout.addWidget(self._translated_label)

        self.setLayout(layout)

    def _init_timer(self):
        """自动隐藏定时器"""
        self._auto_hide_timer = QTimer(self)
        self._auto_hide_timer.setInterval(1000)  # 每秒检查
        self._auto_hide_timer.timeout.connect(self._check_auto_hide)
        self._auto_hide_timer.start()

    def _connect_signals(self):
        """连接跨线程信号"""
        self.subtitle_signal.connect(self._on_subtitle)
        self.clear_signal.connect(self._on_clear)

    # ---------- 公共接口 ----------

    def update_subtitle(self, event: SubtitleEvent) -> None:
        """
        更新字幕 (线程安全, 从任意线程调用)
        通过信号机制确保在 Qt 主线程中执行 UI 更新
        """
        self.subtitle_signal.emit(event)

    def clear_subtitle(self) -> None:
        """清空字幕 (线程安全)"""
        self.clear_signal.emit()

    def set_show_original(self, show: bool) -> None:
        self._config.show_original = show
        self._original_label.setVisible(show)

    def set_show_translated(self, show: bool) -> None:
        self._config.show_translated = show
        self._translated_label.setVisible(show)

    def save_position(self) -> None:
        """保存当前窗口位置到配置"""
        pos = self.pos()
        self._config.x = pos.x()
        self._config.y = pos.y()
        self._config.width = self.width()
        self._config.height = self.height()

    # ---------- 信号槽 ----------

    @pyqtSlot(SubtitleEvent)
    def _on_subtitle(self, event: SubtitleEvent):
        """接收字幕信号 (Qt 主线程)"""
        self._last_update_time = time.time()

        if self._config.show_original:
            self._original_label.setText(event.original_text)

        if self._config.show_translated:
            self._translated_label.setText(event.translated_text)

        if not self.isVisible():
            self.show()

    @pyqtSlot()
    def _on_clear(self):
        """清空字幕"""
        self._original_label.setText("")
        self._translated_label.setText("")

    def _check_auto_hide(self):
        """检查是否需要自动隐藏"""
        if self._last_update_time == 0:
            return
        elapsed = time.time() - self._last_update_time
        if elapsed > self._config.auto_hide_seconds:
            self._original_label.setText("")
            self._translated_label.setText("")

    # ---------- 绘制 ----------

    def paintEvent(self, event: QPaintEvent) -> None:
        """绘制半透明圆角背景"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 圆角路径
        path = QPainterPath()
        path.addRoundedRect(
            0.0, 0.0,
            float(self.width()), float(self.height()),
            self._config.border_radius, self._config.border_radius,
        )

        # 半透明背景
        bg_color = QColor(self._config.bg_color)
        bg_color.setAlphaF(self._config.opacity)
        painter.fillPath(path, bg_color)

        painter.end()

    # ---------- 鼠标事件 (拖动) ----------

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if (self._drag_pos is not None
                and event.buttons() & Qt.MouseButton.LeftButton):
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_pos = None
        self.save_position()

    # ---------- 右键菜单 ----------

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #2a2a3e;
                color: white;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 4px;
            }
            QMenu::item:selected {
                background-color: #4a4a6e;
            }
        """)

        # 显示/隐藏原文
        act_original = QAction(
            f"{'✓ ' if self._config.show_original else '  '}显示原文", self
        )
        act_original.triggered.connect(
            lambda: self.set_show_original(not self._config.show_original)
        )
        menu.addAction(act_original)

        # 显示/隐藏翻译
        act_translated = QAction(
            f"{'✓ ' if self._config.show_translated else '  '}显示翻译", self
        )
        act_translated.triggered.connect(
            lambda: self.set_show_translated(not self._config.show_translated)
        )
        menu.addAction(act_translated)

        menu.addSeparator()

        # 字号调节
        act_font_up = QAction("字号 +", self)
        act_font_up.triggered.connect(self._increase_font)
        menu.addAction(act_font_up)

        act_font_down = QAction("字号 -", self)
        act_font_down.triggered.connect(self._decrease_font)
        menu.addAction(act_font_down)

        menu.addSeparator()

        # 透明度
        act_more_opaque = QAction("背景加深", self)
        act_more_opaque.triggered.connect(
            lambda: self._set_opacity(min(1.0, self._config.opacity + 0.1))
        )
        menu.addAction(act_more_opaque)

        act_more_trans = QAction("背景减淡", self)
        act_more_trans.triggered.connect(
            lambda: self._set_opacity(max(0.2, self._config.opacity - 0.1))
        )
        menu.addAction(act_more_trans)

        menu.exec(QCursor.pos())

    def _increase_font(self):
        self._config.font_size_original = min(30, self._config.font_size_original + 2)
        self._config.font_size_translated = min(36, self._config.font_size_translated + 2)
        self._apply_fonts()

    def _decrease_font(self):
        self._config.font_size_original = max(8, self._config.font_size_original - 2)
        self._config.font_size_translated = max(10, self._config.font_size_translated - 2)
        self._apply_fonts()

    def _apply_fonts(self):
        cfg = self._config
        self._original_label.setFont(QFont(cfg.font_family, cfg.font_size_original))
        font = QFont(cfg.font_family, cfg.font_size_translated)
        font.setBold(True)
        self._translated_label.setFont(font)

    def _set_opacity(self, value: float):
        self._config.opacity = value
        self.update()  # 触发重绘
