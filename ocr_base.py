"""
File: ocr_base.py
Description: Base class for OCR processors with shared post-processing logic.
Author: Alessandro.Nardelli
Date: 2025-03-28
"""

import logging
import re
from abc import ABC, abstractmethod

import Levenshtein

logger = logging.getLogger(__name__)

OCR_CORRECTIONS = {
    "lVA": "IVA",
    "lmporto": "Importo",
    "lmponibile": "Imponibile",
    "|VA": "IVA",
}

OCR_PATTERNS = [
    (r"(\d) (\d)", r"\1\2"),
    (r"(\d{2})\.(\d{2})\.(\d{4})", r"\1/\2/\3"),
    (r"(\d+)[,\.](\d+)\s*o/o", r"\1.\2%"),
    (r"(\d+)[,\.](\d+)\s*€", r"\1.\2 Euro"),
]


class BaseOCRProcessor(ABC):
    def __init__(self, debug_mode: bool = False) -> None:
        self.debug_mode = debug_mode
        self.ocr_available = False

    @abstractmethod
    def extract_ocr_text(self, image_path: str) -> str:
        ...

    def _post_process_ocr_text(self, text: str) -> str:
        if not text:
            return ""

        result = text
        for wrong, correct in OCR_CORRECTIONS.items():
            result = result.replace(wrong, correct)

        for pattern, replacement in OCR_PATTERNS:
            result = re.sub(pattern, replacement, result)

        result = re.sub(r"\n\s*\n", "\n\n", result)
        return result

    def _combine_ocr_results(self, texts: list[str]) -> str:
        if not texts:
            return ""

        normalized_texts: list[list[str]] = []
        for text in texts:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            normalized_texts.append(lines)

        all_lines: set[str] = set()
        for lines in normalized_texts:
            all_lines.update(lines)

        line_scores: dict[str, int] = {}
        for line in all_lines:
            line_scores[line] = sum(1 for lines in normalized_texts if line in lines)

        sorted_lines = sorted(all_lines, key=lambda l: (-line_scores[l], -len(l)))

        final_lines: list[str] = []
        for line in sorted_lines:
            if not any(self._are_lines_similar(line, existing) for existing in final_lines):
                final_lines.append(line)

        return "\n".join(final_lines)

    @staticmethod
    def _are_lines_similar(line1: str, line2: str, threshold: float = 0.8) -> bool:
        if abs(len(line1) - len(line2)) > 10:
            return False

        distance = Levenshtein.distance(line1, line2)
        max_len = max(len(line1), len(line2))
        if max_len == 0:
            return True

        return (1 - distance / max_len) > threshold
