# Добавить в editor.py после импортов

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from structure_checker import ProblemType, StructureProblem


class StructurePanel(QWidget):
    """Панель со списком проблем структуры и фильтрами."""

    problem_activated = Signal(object)  # StructureProblem
    filters_changed = Signal()  # Сигнал при изменении фильтров

    def __init__(self, parent=None):
        super().__init__(parent)
        self._problems: list[StructureProblem] = []
        self._theme = "light"

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Фильтры
        filters_box = QHBoxLayout()
        filters_box.setSpacing(8)

        self.cb_empty = QCheckBox("🟡 Пустые")
        self.cb_empty.setChecked(True)
        self.cb_empty.setToolTip("Показывать пустые переводы/оригиналы")

        filters_box.addWidget(self.cb_empty)

        self.cb_mismatch = QCheckBox("🔴 Рассинхрон")
        self.cb_mismatch.setChecked(True)
        self.cb_mismatch.setToolTip("Показывать разное количество абзацев")

        filters_box.addWidget(self.cb_mismatch)

        self.cb_length = QCheckBox("⚠️ Длина")
        self.cb_length.setChecked(True)
        self.cb_length.setToolTip("Показывать расхождение по длине")

        filters_box.addWidget(self.cb_length)

        filters_box.addStretch()
        layout.addLayout(filters_box)

        # Список проблем
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(120)
        self.list_widget.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self.list_widget)

        # Загрузить настройки
        self._load_filters()
        self._apply_theme()

        self.cb_empty.toggled.connect(self._on_filter_changed)
        self.cb_mismatch.toggled.connect(self._on_filter_changed)
        self.cb_length.toggled.connect(self._on_filter_changed)

    def set_theme(self, theme: str) -> None:
        """Применить тему."""
        self._theme = theme
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Обновить стили для темы."""
        if self._theme == "dark":
            self.list_widget.setStyleSheet(
                """
                QListWidget {
                    background: #252526;
                    border: 1px solid #3c3c3c;
                    font-size: 12px;
                }
                QListWidget::item {
                    padding: 4px 6px;
                    color: #cccccc;
                }
                QListWidget::item:selected {
                    background: #094771;
                }
                """
            )
        else:
            self.list_widget.setStyleSheet(
                """
                QListWidget {
                    background: #fafafa;
                    border: 1px solid #e0e0e0;
                    font-size: 12px;
                }
                QListWidget::item {
                    padding: 4px 6px;
                    color: #333;
                }
                QListWidget::item:selected {
                    background: #1a73e8;
                    color: white;
                }
                """
            )

    def _on_filter_changed(self) -> None:
        """Обработчик изменения фильтров."""
        self._save_filters()
        self.filters_changed.emit()

    def _load_filters(self) -> None:
        """Загрузить фильтры из настроек."""
        settings = QSettings()
        self.cb_empty.setChecked(
            settings.value("ui/structure_filter_empty", True, type=bool)
        )
        self.cb_mismatch.setChecked(
            settings.value("ui/structure_filter_mismatch", True, type=bool)
        )
        self.cb_length.setChecked(
            settings.value("ui/structure_filter_length", True, type=bool)
        )

    def _save_filters(self) -> None:
        """Сохранить фильтры в настройки."""
        settings = QSettings()
        settings.setValue("ui/structure_filter_empty", self.cb_empty.isChecked())
        settings.setValue("ui/structure_filter_mismatch", self.cb_mismatch.isChecked())
        settings.setValue("ui/structure_filter_length", self.cb_length.isChecked())

    def get_filters(self) -> dict[ProblemType, bool]:
        """Получить текущие фильтры."""
        return {
            ProblemType.EMPTY_TRANSLATION: self.cb_empty.isChecked(),
            ProblemType.STRUCTURE_MISMATCH: self.cb_mismatch.isChecked(),
            ProblemType.LENGTH_DIVERGENCE: self.cb_length.isChecked(),
        }

    def update_problems(self, problems: list[StructureProblem]) -> None:
        """Обновить список проблем."""

        if problems == self._problems:
            return

        self._problems = problems
        self.list_widget.clear()

        if not problems:
            item = QListWidgetItem("✓ Структура совпадает")
            item.setForeground(QColor("#188038"))
            self.list_widget.addItem(item)
            return

        for p in problems:
            icon = {
                ProblemType.EMPTY_TRANSLATION: "🟡",
                ProblemType.STRUCTURE_MISMATCH: "🔴",
                ProblemType.LENGTH_DIVERGENCE: "⚠️",
            }[p.problem_type]

            item = QListWidgetItem(f"{icon} {p.message}")
            item.setData(Qt.ItemDataRole.UserRole, p)

            # Цвет текста
            if p.problem_type == ProblemType.STRUCTURE_MISMATCH:
                item.setForeground(QColor("#c5221f"))
            elif p.problem_type == ProblemType.EMPTY_TRANSLATION:
                item.setForeground(QColor("#f9ab00"))
            else:
                item.setForeground(QColor("#188038"))

            self.list_widget.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        problem = item.data(Qt.ItemDataRole.UserRole)
        if problem is not None:
            self.problem_activated.emit(problem)
