#!/usr/bin/env python3
"""
Сворачиваемый контейнер для панелей.
"""

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSettings,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class CollapsibleWidget(QWidget):
    """Сворачиваемый контейнер с кнопкой-стрелкой."""

    toggled = Signal(bool)  # expanded

    def __init__(self, title: str, settings_key: str = "", parent=None):
        super().__init__(parent)
        self._title = title
        self._settings_key = settings_key
        self._expanded = True
        self._theme = "light"

        # Основной layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Заголовок с кнопкой
        header = QFrame()
        header.setObjectName("collapsibleHeader")
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)
        header_layout.setSpacing(4)

        # Кнопка-стрелка
        self.toggle_btn = QPushButton("▼")
        self.toggle_btn.setFixedSize(20, 20)
        self.toggle_btn.setFlat(True)
        self.toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.toggle_btn.clicked.connect(self.toggle)
        self.toggle_btn.setStyleSheet(
            """
            QPushButton {
                border: none;
                font-size: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(0, 0, 0, 0.1);
                border-radius: 3px;
            }
            """
        )
        header_layout.addWidget(self.toggle_btn)

        # Заголовок
        self.title_label = QLabel(title)
        self.title_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header_layout.addWidget(self.title_label, 1)

        # Статус (опционально, можно установить через set_status)
        self.status_label = QLabel("")
        self.status_label.setStyleSheet("color: #188038; font-size: 11px;")
        header_layout.addWidget(self.status_label)

        main_layout.addWidget(header)

        # Контейнер для содержимого
        self.content = QFrame()
        self.content.setObjectName("collapsibleContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(8, 4, 8, 8)
        self.content_layout.setSpacing(4)

        main_layout.addWidget(self.content)

        # Анимация
        self.animation = QParallelAnimationGroup(self)

        self.content_anim = QPropertyAnimation(self.content, b"maximumHeight")
        self.content_anim.setDuration(200)
        self.content_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.addAnimation(self.content_anim)

        # Загрузить состояние из настроек
        if settings_key:
            self._expanded = QSettings().value(f"ui/{settings_key}_expanded", True, type=bool)
            self._update_visuals()

        self._apply_theme()

    def set_theme(self, theme: str) -> None:
        """Применить тему."""
        self._theme = theme
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Обновить стили для темы."""
        if self._theme == "dark":
            header_bg = "#2d2d30"
            header_border = "#3c3c3c"
            content_bg = "#252526"
            title_color = "#cccccc"
        else:
            header_bg = "#f5f5f5"
            header_border = "#e0e0e0"
            content_bg = "#fafafa"
            title_color = "#333"

        self.findChild(QFrame, "collapsibleHeader").setStyleSheet(
            f"""
            QFrame#collapsibleHeader {{
                background: {header_bg};
                border: 1px solid {header_border};
                border-radius: 4px;
            }}
            """
        )

        self.title_label.setStyleSheet(
            f"font-weight: bold; font-size: 13px; color: {title_color};"
        )

        self.content.setStyleSheet(
            f"""
            QFrame#collapsibleContent {{
                background: {content_bg};
                border: 1px solid {header_border};
                border-top: none;
                border-radius: 0 0 4px 4px;
            }}
            """
        )

    def add_widget(self, widget: QWidget) -> None:
        """Добавить виджет в содержимое."""
        self.content_layout.addWidget(widget)

    def toggle(self) -> None:
        """Переключить состояние."""
        self.set_expanded(not self._expanded)

    def set_expanded(self, expanded: bool) -> None:
        """Установить состояние развёрнутости."""
        if self._expanded == expanded:
            return

        self._expanded = expanded
        self._update_visuals()

        # Анимация
        if expanded:
            # Разворачиваем
            self.content.setVisible(True)
            self.content.setMaximumHeight(self.content.sizeHint().height())
            self.content_anim.setStartValue(0)
            self.content_anim.setEndValue(self.content.sizeHint().height())
        else:
            # Сворачиваем
            self.content_anim.setStartValue(self.content.height())
            self.content_anim.setEndValue(0)
            self.content.setMaximumHeight(0)
            self.content.setVisible(False)

        self.animation.start()

        # Сохранить состояние
        if self._settings_key:
            QSettings().setValue(f"ui/{self._settings_key}_expanded", expanded)

        self.toggled.emit(expanded)

    def _update_visuals(self) -> None:
        """Обновить визуальные элементы."""
        self.toggle_btn.setText("▼" if self._expanded else "▶")
        if self._expanded:
            self.content.setVisible(True)
            self.content.setMaximumHeight(16777215)  # QWIDGETSIZE_MAX
        else:
            self.content.setVisible(False)
            self.content.setMaximumHeight(0)

    def set_status(self, text: str, color: str = "#188038") -> None:
        """Установить текст статуса в заголовке."""
        self.status_label.setText(text)
        self.status_label.setStyleSheet(f"color: {color}; font-size: 11px;")
