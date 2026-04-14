from __future__ import annotations

from typing import Callable, Mapping

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QCheckBox, QGridLayout, QGroupBox,
)


class ControlPanel(QWidget):
    """跨平台可见的控制面板.

    用于兜底替代不稳定的托盘交互:
      - macOS: 默认显示
      - Windows: 可通过托盘打开
    """

    def __init__(
        self,
        source_options: Mapping[str, str],
        target_options: Mapping[str, str],
        model_options: Mapping[str, str],
        current_source: str,
        current_targets: tuple[str, ...],
        current_model: str,
        overlay_visible: bool = True,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("SubtitleLive Control Panel")
        self.setMinimumWidth(420)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, False)

        self._source_options = dict(source_options)
        self._target_options = dict(target_options)
        self._model_options = dict(model_options)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("SubtitleLive")
        title.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title)

        self._status = QLabel("状态: 未开始")
        layout.addWidget(self._status)

        self._btn_toggle = QPushButton("开始识别")
        layout.addWidget(self._btn_toggle)

        layout.addLayout(self._build_combo_row("识别语言", self._source_options, current_source, "_cmb_src"))
        self._target_checks = self._build_target_group(current_targets)
        layout.addWidget(self._target_group)
        layout.addLayout(self._build_combo_row("模型", self._model_options, current_model, "_cmb_model"))

        self._chk_overlay = QCheckBox("显示字幕窗口")
        self._chk_overlay.setChecked(overlay_visible)
        layout.addWidget(self._chk_overlay)

        actions = QHBoxLayout()
        self._btn_hide = QPushButton("隐藏面板")
        self._btn_quit = QPushButton("退出")
        actions.addWidget(self._btn_hide)
        actions.addStretch(1)
        actions.addWidget(self._btn_quit)
        layout.addLayout(actions)

    def _build_combo_row(
        self,
        label_text: str,
        options: Mapping[str, str],
        current: str,
        attr_name: str,
    ) -> QHBoxLayout:
        row = QHBoxLayout()
        label = QLabel(label_text)
        combo = QComboBox()
        for code, text in options.items():
            combo.addItem(text, code)
        index = combo.findData(current)
        if index >= 0:
            combo.setCurrentIndex(index)
        row.addWidget(label)
        row.addWidget(combo, 1)
        setattr(self, attr_name, combo)
        return row

    def _build_target_group(self, current_targets: tuple[str, ...]) -> dict[str, QCheckBox]:
        self._target_group = QGroupBox("翻译语言")
        grid = QGridLayout(self._target_group)
        checks: dict[str, QCheckBox] = {}
        current_set = set(current_targets)
        for index, (code, text) in enumerate(self._target_options.items()):
            check = QCheckBox(text)
            check.setChecked(code in current_set)
            grid.addWidget(check, index // 2, index % 2)
            checks[code] = check
        return checks

    def set_handlers(
        self,
        on_toggle: Callable[[], None],
        on_source: Callable[[str], None],
        on_targets: Callable[[list[str]], None],
        on_model: Callable[[str], None],
        on_overlay: Callable[[], None],
        on_quit: Callable[[], None],
    ) -> None:
        self._btn_toggle.clicked.connect(on_toggle)
        self._cmb_src.currentIndexChanged.connect(
            lambda _: on_source(self._cmb_src.currentData())
        )
        for _code, check in self._target_checks.items():
            check.clicked.connect(
                lambda _checked=False: on_targets(self.selected_targets())
            )
        self._cmb_model.currentIndexChanged.connect(
            lambda _: on_model(self._cmb_model.currentData())
        )
        self._chk_overlay.clicked.connect(on_overlay)
        self._btn_hide.clicked.connect(self.hide)
        self._btn_quit.clicked.connect(on_quit)

    def set_running(self, running: bool) -> None:
        self._status.setText("状态: 识别中" if running else "状态: 未开始")
        self._btn_toggle.setText("停止识别" if running else "开始识别")

    def set_source_language(self, lang: str) -> None:
        self._set_combo_value(self._cmb_src, lang)

    def set_target_languages(self, languages: tuple[str, ...]) -> None:
        selected = set(languages)
        for code, check in self._target_checks.items():
            check.blockSignals(True)
            check.setChecked(code in selected)
            check.blockSignals(False)

    def set_model(self, model: str) -> None:
        self._set_combo_value(self._cmb_model, model)

    def set_overlay_visible(self, visible: bool) -> None:
        self._chk_overlay.blockSignals(True)
        self._chk_overlay.setChecked(visible)
        self._chk_overlay.blockSignals(False)

    @staticmethod
    def _set_combo_value(combo: QComboBox, value: str) -> None:
        index = combo.findData(value)
        if index < 0 or combo.currentIndex() == index:
            return
        combo.blockSignals(True)
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

    def selected_targets(self) -> list[str]:
        targets = [
            code for code, check in self._target_checks.items()
            if check.isChecked()
        ]
        return targets or ["zh"]
