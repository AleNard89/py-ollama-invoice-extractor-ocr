"""
File: ocr_factory.py
Description: Factory class for creating the appropriate OCR engine instance.
Author: Alessandro.Nardelli
Date: 2025-03-27
"""

import logging

logger = logging.getLogger(__name__)


class OCRFactory:
    @staticmethod
    def create_ocr_processor(
        ocr_type: str = "easyocr",
        debug_mode: bool = False,
        use_gpu: bool = False,
        lang: str = "it",
    ):
        ocr_type = ocr_type.lower()

        if ocr_type == "easyocr":
            try:
                from ocr_EasyOCR import OCRProcessor
                return OCRProcessor(debug_mode=debug_mode, use_gpu=use_gpu, lang=lang)
            except ImportError as e:
                logger.warning("EasyOCR non disponibile: %s", e)
                return DummyOCRProcessor(debug_mode)

        elif ocr_type == "paddleocr":
            try:
                from ocr_paddleocr import OCRProcessor
                return OCRProcessor(debug_mode=debug_mode, use_gpu=use_gpu, lang=lang)
            except ImportError as e:
                logger.warning("PaddleOCR non disponibile: %s", e)
                return DummyOCRProcessor(debug_mode)

        elif ocr_type == "tesseract":
            try:
                from ocr_tesseract import OCRProcessor
                return OCRProcessor(debug_mode=debug_mode)
            except ImportError as e:
                logger.warning("Tesseract non disponibile: %s", e)
                return DummyOCRProcessor(debug_mode)

        else:
            logger.warning("Tipo OCR '%s' non riconosciuto (validi: easyocr, paddleocr, tesseract)", ocr_type)
            return DummyOCRProcessor(debug_mode)


class DummyOCRProcessor:
    def __init__(self, debug_mode: bool = False) -> None:
        self.debug_mode = debug_mode
        self.ocr_available = False
        logger.info("Modalita' senza OCR attivata")

    def extract_ocr_text(self, image_path: str) -> str:
        return ""