# Добавить в editor.py после импортов

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
)
from PySide6.QtWidgets import (
    QListWidget,
    QListWidgetItem,
)

from structure_checker import ProblemType, StructureProblem


class StructurePanel(QListWidget):
    """Панель со списком проблем структуры."""

    problem_activated = Signal(object)  # StructureProblem

    def __init__(self, parent=None):
        super().__init__(parent)
        self._problems: list[StructureProblem] = []
        self._theme = "light"
        self._apply_theme()
        self.itemClicked.connect(self._on_item_clicked)

    def set_theme(self, theme: str) -> None:
        self._theme = theme
        self._apply_theme()

    def _apply_theme(self) -> None:
        if self._theme == "dark":
            self.setStyleSheet(
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
            self.setStyleSheet(
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

    def update_problems(self, problems: list[StructureProblem]) -> None:
        """Обновить список проблем."""
        self._problems = problems
        self.clear()

        if not problems:
            item = QListWidgetItem("✓ Структура совпадает")
            item.setForeground(QColor("#188038"))
            self.addItem(item)
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

            self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        problem = item.data(Qt.ItemDataRole.UserRole)
        if problem is not None:
            self.problem_activated.emit(problem)
