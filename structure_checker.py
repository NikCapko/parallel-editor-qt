#!/usr/bin/env python3
"""
Проверка соответствия структуры между оригиналом и переводом.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterator


class ProblemType(Enum):
    """Тип проблемы структуры."""
    EMPTY_TRANSLATION = "empty_translation"  # 🟡 пустой перевод
    STRUCTURE_MISMATCH = "structure_mismatch"  # 🔴 рассинхрон
    LENGTH_DIVERGENCE = "length_divergence"  # ⚠️ разная длина


@dataclass
class Paragraph:
    """Абзац Markdown."""
    text: str
    start_pos: int  # позиция в тексте
    end_pos: int  # позиция конца
    line_start: int  # номер начальной строки (0-based)
    line_end: int  # номер конечной строки (exclusive)
    is_heading: bool = False
    is_list_item: bool = False
    is_code_block: bool = False
    is_empty: bool = False


@dataclass
class StructureProblem:
    """Проблема структуры."""
    en_para_idx: int | None  # индекс абзаца в оригинале (None если проблема только в переводе)
    ru_para_idx: int | None  # индекс абзаца в переводе
    problem_type: ProblemType
    message: str
    en_pos: int | None = None  # позиция для перехода
    ru_pos: int | None = None


class MarkdownParagraphParser:
    """Парсер Markdown-абзацев."""

    # Паттерны для определения типов блоков
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
            line_len = len(line) + 1  # +1 для \n

            # Проверка code block
            if self._CODE_BLOCK_RE.match(line):
                if in_code_block:
                    # Конец code block
                    current_para_lines.append(line)
                    pos += line_len
                    flush_paragraph()
                    in_code_block = False
                    current_start_pos = pos
                    current_line_start = line_idx + 1
                    continue
                else:
                    # Начало code block
                    if current_para_lines:
                        flush_paragraph()
                    in_code_block = True
                    current_start_pos = pos
                    current_line_start = line_idx
                    current_para_lines.append(line)
                    pos += line_len
                    continue

            if in_code_block:
                # Внутри code block — всё один абзац
                current_para_lines.append(line)
                pos += line_len
                continue

            # Пустая строка — разделитель абзацев
            if self._EMPTY_LINE_RE.match(line):
                if current_para_lines:
                    flush_paragraph()
                current_start_pos = pos + line_len
                current_line_start = line_idx + 1
                pos += line_len
                continue

            # Заголовок — всегда отдельный абзац
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

            # Обычная строка — добавляем к текущему абзацу
            if not current_para_lines:
                current_start_pos = pos
                current_line_start = line_idx
            current_para_lines.append(line)
            pos += line_len

        # Финальный абзац
        flush_paragraph()

        return paragraphs


class StructureChecker:
    """Проверка соответствия структуры между оригиналом и переводом."""

    LENGTH_THRESHOLD = 0.3  # 30% расхождение по длине

    def __init__(self):
        self.parser = MarkdownParagraphParser()

    def check(self, en_text: str, ru_text: str) -> list[StructureProblem]:
        """Проверить структуру и вернуть список проблем."""
        en_paras = self.parser.parse(en_text)
        ru_paras = self.parser.parse(ru_text)

        # Фильтруем пустые абзацы для сравнения
        en_non_empty = [p for p in en_paras if not p.is_empty]
        ru_non_empty = [p for p in ru_paras if not p.is_empty]

        problems: list[StructureProblem] = []

        # Проверяем количество абзацев
        if len(en_non_empty) != len(ru_non_empty):
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

        # Сравниваем по индексу
        max_len = max(len(en_non_empty), len(ru_non_empty))
        for idx in range(max_len):
            en_para = en_non_empty[idx] if idx < len(en_non_empty) else None
            ru_para = ru_non_empty[idx] if idx < len(ru_non_empty) else None

            # Пустой перевод при непустом оригинале
            if en_para and not en_para.is_empty:
                if ru_para is None or ru_para.is_empty:
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

            # Пустой оригинал при непустом переводе (редко, но бывает)
            if ru_para and not ru_para.is_empty:
                if en_para is None or en_para.is_empty:
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


# Пример использования
if __name__ == "__main__":
    en_text = """# Глава 1

Это первый абзац оригинала.

Это второй абзац оригинала. Он довольно длинный, чтобы проверить расхождение по длине.

# Глава 2

Третий абзац.
"""

    ru_text = """# Глава 1

Это первый абзац перевода.

# Глава 2

Третий абзац перевода. Он очень короткий.
"""

    checker = StructureChecker()
    problems = checker.check(en_text, ru_text)

    for p in problems:
        icon = {
            ProblemType.EMPTY_TRANSLATION: "🟡",
            ProblemType.STRUCTURE_MISMATCH: "🔴",
            ProblemType.LENGTH_DIVERGENCE: "⚠️",
        }[p.problem_type]
        print(f"{icon} {p.message}")
