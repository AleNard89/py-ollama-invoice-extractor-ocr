"""
File: ocr_EasyOCR.py
Description: OCR processor using EasyOCR engine.
Author: Alessandro.Nardelli
Date: 2025-03-21
"""

import logging

import cv2

from ocr_base import BaseOCRProcessor

logger = logging.getLogger(__name__)


class OCRProcessor(BaseOCRProcessor):
    def __init__(self, debug_mode: bool = False, use_gpu: bool = False, lang: str = "it") -> None:
        super().__init__(debug_mode=debug_mode)
        self.use_gpu = use_gpu

        try:
            import easyocr
            self.reader = easyocr.Reader(["it", "en"], gpu=use_gpu, quantize=True)
            self.ocr_available = True
            logger.info("EasyOCR trovato e disponibile")
        except Exception as e:
            logger.warning("EasyOCR non disponibile: %s", e)

    def extract_ocr_text(self, image_path: str) -> str:
        if not self.ocr_available:
            return ""

        try:
            img = cv2.imread(image_path)
            if img is None:
                logger.error("Impossibile leggere l'immagine: %s", image_path)
                return ""

            height, width = img.shape[:2]
            max_dim = max(height, width)
            if max_dim > 2000:
                scale = 2000 / max_dim
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)

            result = self.reader.readtext(img)

            extracted_text = [
                detection[1] for detection in result if detection[2] > 0.3
            ]

            combined_text = "\n".join(extracted_text)
            processed_text = self._post_process_ocr_text(combined_text)

            if self.debug_mode:
                combined_file = image_path.replace(".png", "_ocr_combined.txt")
                with open(combined_file, "w", encoding="utf-8") as f:
                    f.write(processed_text)

            return processed_text
        except Exception as e:
            logger.error("Errore durante l'OCR: %s", e)
            return ""