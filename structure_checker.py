#!/usr/bin/env python3
"""
Проверка соответствия структуры между оригиналом и переводом.
Фоновая проверка в отдельном потоке.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum

from PySide6.QtCore import QObject, QThread, Signal


class ProblemType(Enum):
    """Тип проблемы структуры."""

    EMPTY_TRANSLATION = "empty_translation"  # 🟡 пустой перевод
    STRUCTURE_MISMATCH = "structure_mismatch"  # 🔴 рассинхрон
    LENGTH_DIVERGENCE = "length_divergence"  # ⚠️ разная длина


@dataclass
class Paragraph:
    """Абзац Markdown."""

    text: str
    start_pos: int
    end_pos: int
    line_start: int
    line_end: int
    is_heading: bool = False
    is_list_item: bool = False
    is_code_block: bool = False
    is_empty: bool = False


@dataclass
class StructureProblem:
    """Проблема структуры."""

    en_para_idx: int | None
    ru_para_idx: int | None
    problem_type: ProblemType
    message: str
    en_pos: int | None = None
    ru_pos: int | None = None


class MarkdownParagraphParser:
    """Парсер Markdown-абзацев."""

    _HEADING_RE = re.compile(r"^#{1,6}\s+.+$")
    _LIST_ITEM_RE = re.compile(r"^(\s*[-*+]|\s*\d+\.)\s+.+$")
    _CODE_BLOCK_RE = re.compile(r"^```")
    _EMPTY_LINE_RE = re.compile(r"^\s*$")

    def parse(self, text: str) -> list[Paragraph]:
        """Разбить текст на абзацы."""
        paragraphs: list[Paragraph] = []
        lines = text.split("\n")
        current_para_lines: list[str] = []
        current_start_pos = 0
        current_line_start = 0
        in_code_block = False
        pos = 0

        def flush_paragraph():
            nonlocal current_para_lines, current_start_pos, current_line_start
            if not current_para_lines:
                return

            para_text = "\n".join(current_para_lines)
            is_empty = not para_text.strip()
            is_heading = bool(self._HEADING_RE.match(current_para_lines[0]))
            is_list_item = bool(self._LIST_ITEM_RE.match(current_para_lines[0]))

            para = Paragraph(
                text=para_text,
                start_pos=current_start_pos,
                end_pos=pos,
                line_start=current_line_start,
                line_end=current_line_start + len(current_para_lines),
                is_heading=is_heading,
                is_list_item=is_list_item,
                is_code_block=in_code_block,
                is_empty=is_empty,
            )
            paragraphs.append(para)
            current_para_lines = []

        for line_idx, line in enumerate(lines):
            line_len = len(line) + 1

            if self._CODE_BLOCK_RE.match(line):
                if in_code_block:
                    current_para_lines.append(line)
                    pos += line_len
                    flush_paragraph()
                    in_code_block = False
                    current_start_pos = pos
                    current_line_start = line_idx + 1
                    continue
                else:
                    if current_para_lines:
                        flush_paragraph()
                    in_code_block = True
                    current_start_pos = pos
                    current_line_start = line_idx
                    current_para_lines.append(line)
                    pos += line_len
                    continue

            if in_code_block:
                current_para_lines.append(line)
                pos += line_len
                continue

            if self._EMPTY_LINE_RE.match(line):
                if current_para_lines:
                    flush_paragraph()
                # Создаём пустой абзац для пустой строки
                para = Paragraph(
                    text="",
                    start_pos=pos,
                    end_pos=pos + line_len,
                    line_start=line_idx,
                    line_end=line_idx + 1,
                    is_heading=False,
                    is_list_item=False,
                    is_code_block=False,
                    is_empty=True,
                )
                paragraphs.append(para)
                current_start_pos = pos + line_len
                current_line_start = line_idx + 1
                pos += line_len
                continue

            if self._HEADING_RE.match(line):
                if current_para_lines:
                    flush_paragraph()
                current_start_pos = pos
                current_line_start = line_idx
                current_para_lines.append(line)
                pos += line_len
                flush_paragraph()
                current_start_pos = pos
                current_line_start = line_idx + 1
                continue

            if not current_para_lines:
                current_start_pos = pos
                current_line_start = line_idx
            current_para_lines.append(line)
            pos += line_len

        flush_paragraph()
        return paragraphs


class StructureChecker:
    """Проверка соответствия структуры."""

    LENGTH_THRESHOLD = 0.3

    def __init__(self):
        self.parser = MarkdownParagraphParser()

    def check(
        self,
        en_text: str,
        ru_text: str,
        filters: dict[ProblemType, bool] | None = None,
    ) -> list[StructureProblem]:
        """Проверить структуру и вернуть список проблем.

        filters — словарь {тип_проблемы: показывать_или_нет}
        """
        en_paras = self.parser.parse(en_text)
        ru_paras = self.parser.parse(ru_text)

        en_non_empty = [p for p in en_paras if not p.is_empty]
        ru_non_empty = [p for p in ru_paras if not p.is_empty]

        # По умолчанию все фильтры включены
        if filters is None:
            filters = {
                ProblemType.EMPTY_TRANSLATION: True,
                ProblemType.STRUCTURE_MISMATCH: True,
                ProblemType.LENGTH_DIVERGENCE: True,
            }

        problems: list[StructureProblem] = []

        # Проверяем количество непустых абзацев
        if len(en_non_empty) != len(ru_non_empty) and filters.get(
            ProblemType.STRUCTURE_MISMATCH, True
        ):
            problems.append(
                StructureProblem(
                    en_para_idx=None,
                    ru_para_idx=None,
                    problem_type=ProblemType.STRUCTURE_MISMATCH,
                    message=f"Разное количество абзацев: оригинал {len(en_non_empty)}, перевод {len(ru_non_empty)}",
                    en_pos=0,
                    ru_pos=0,
                )
            )

        # Сравниваем по индексу в полных списках
        max_len = max(len(en_paras), len(ru_paras))
        for idx in range(max_len):
            en_para = en_paras[idx] if idx < len(en_paras) else None
            ru_para = ru_paras[idx] if idx < len(ru_paras) else None

            # Пустой перевод при непустом оригинале
            if en_para and not en_para.is_empty:
                if ru_para is None or ru_para.is_empty:
                    if filters.get(ProblemType.EMPTY_TRANSLATION, True):
                        problems.append(
                            StructureProblem(
                                en_para_idx=idx,
                                ru_para_idx=idx if ru_para else None,
                                problem_type=ProblemType.EMPTY_TRANSLATION,
                                message=f"Абзац {idx + 1}: пустой перевод",
                                en_pos=en_para.start_pos,
                                ru_pos=ru_para.start_pos if ru_para else None,
                            )
                        )
                    continue

            # Пустой оригинал при непустом переводе
            if ru_para and not ru_para.is_empty:
                if en_para is None or en_para.is_empty:
                    if filters.get(ProblemType.EMPTY_TRANSLATION, True):
                        problems.append(
                            StructureProblem(
                                en_para_idx=idx if en_para else None,
                                ru_para_idx=idx,
                                problem_type=ProblemType.EMPTY_TRANSLATION,
                                message=f"Абзац {idx + 1}: пустой оригинал",
                                en_pos=en_para.start_pos if en_para else None,
                                ru_pos=ru_para.start_pos,
                            )
                        )
                    continue

            # Оба непустые — проверяем длину
            if en_para and ru_para and not en_para.is_empty and not ru_para.is_empty:
                en_len = len(en_para.text)
                ru_len = len(ru_para.text)
                if en_len > 0 and ru_len > 0:
                    ratio = abs(en_len - ru_len) / max(en_len, ru_len)
                    if ratio > self.LENGTH_THRESHOLD:
                        if filters.get(ProblemType.LENGTH_DIVERGENCE, True):
                            problems.append(
                                StructureProblem(
                                    en_para_idx=idx,
                                    ru_para_idx=idx,
                                    problem_type=ProblemType.LENGTH_DIVERGENCE,
                                    message=f"Абзац {idx + 1}: разная длина (оригинал {en_len}, перевод {ru_len}, расхождение {ratio:.0%})",
                                    en_pos=en_para.start_pos,
                                    ru_pos=ru_para.start_pos,
                                )
                            )

        return problems


class StructureCheckWorker(QObject):
    """Воркер для фоновой проверки структуры."""

    finished = Signal(list)  # list[StructureProblem]
    started = Signal()

    def __init__(self, checker: StructureChecker):
        super().__init__()
        self.checker = checker
        self._en_text = ""
        self._ru_text = ""
        self._filters = None
        self._cancelled = False

    def set_texts(
        self,
        en_text: str,
        ru_text: str,
        filters: dict[ProblemType, bool] | None = None,
    ) -> None:
        """Установить тексты и фильтры для проверки."""
        self._en_text = en_text
        self._ru_text = ru_text
        self._filters = filters
        self._cancelled = False

    def cancel(self) -> None:
        """Отменить текущую проверку."""
        self._cancelled = True

    def run(self) -> None:
        """Выполнить проверку."""
        self.started.emit()
        if self._cancelled:
            return
        problems = self.checker.check(self._en_text, self._ru_text, self._filters)
        if not self._cancelled:
            self.finished.emit(problems)


class StructureCheckThread(QObject):
    """Менеджер потоков для фоновой проверки структуры."""

    finished = Signal(list)  # list[StructureProblem]
    started = Signal()

    def __init__(self, checker: StructureChecker, parent=None):
        super().__init__(parent)
        self.checker = checker
        self._thread: QThread | None = None
        self._worker: StructureCheckWorker | None = None

    def check(
        self,
        en_text: str,
        ru_text: str,
        filters: dict[ProblemType, bool] | None = None,
    ) -> None:
        """Запустить проверку в новом потоке."""
        # Отменить предыдущий воркер
        if self._worker:
            self._worker.cancel()

        # Дождаться завершения предыдущего потока
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1000)
            self._thread = None  # ← обнуляем после wait

        # Создать новый воркер и поток
        self._worker = StructureCheckWorker(self.checker)
        self._worker.set_texts(en_text, ru_text, filters)

        self._thread = QThread()
        self._worker.moveToThread(self._thread)

        # Подключить сигналы
        self._thread.started.connect(self._worker.run)
        self._worker.started.connect(self.started)
        self._worker.finished.connect(self.finished)

        # Очистка после завершения
        self._worker.finished.connect(self._thread.quit)
        self._worker.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread.deleteLater)
        self._thread.finished.connect(self._cleanup_thread)  # ← обнулить ссылку

        # Запустить
        self._thread.start()

    def _cleanup_thread(self) -> None:
        """Обнулить ссылку на поток после завершения."""
        self._thread = None
        self._worker = None

    def cancel(self) -> None:
        """Отменить текущую проверку."""
        if self._worker:
            self._worker.cancel()
        if self._thread is not None and self._thread.isRunning():
            self._thread.quit()
            self._thread.wait(1000)
            self._thread = None
