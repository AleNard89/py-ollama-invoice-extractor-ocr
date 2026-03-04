"""
File: ocr_paddleocr.py
Description: OCR processor using PaddleOCR engine.
Author: Alessandro.Nardelli
Date: 2025-03-21
"""

import logging
import os

import cv2

from ocr_base import BaseOCRProcessor

logger = logging.getLogger(__name__)


class OCRProcessor(BaseOCRProcessor):
    def __init__(self, debug_mode: bool = False, use_gpu: bool = False, lang: str = "it") -> None:
        super().__init__(debug_mode=debug_mode)

        try:
            from paddleocr import PaddleOCR
            self.ocr = PaddleOCR(
                use_angle_cls=False,
                lang=lang,
                use_gpu=use_gpu,
                show_log=False,
                rec_batch_num=1,
                det_db_box_thresh=0.5,
                det_db_unclip_ratio=1.5,
            )
            self.ocr_available = True
            logger.info("PaddleOCR trovato e disponibile")
        except Exception as e:
            logger.warning("PaddleOCR non disponibile: %s", e)

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
            if max_dim > 1800:
                scale = 1800 / max_dim
                img = cv2.resize(img, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)

            try:
                result = self.ocr.ocr(img, cls=False)

                if result and isinstance(result, list) and len(result) > 0:
                    page_result = result[0]
                    extracted_text = ""
                    if page_result and isinstance(page_result, list):
                        for text_box in page_result:
                            if isinstance(text_box, list) and len(text_box) >= 2:
                                if isinstance(text_box[1], (list, tuple)):
                                    extracted_text += text_box[1][0] + "\n"
                                elif isinstance(text_box[1], str):
                                    extracted_text += text_box[1] + "\n"
                    return self._post_process_ocr_text(extracted_text)
                return ""

            except Exception as e:
                logger.error("Errore durante l'OCR principale: %s", e)

                try:
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    binary_path = image_path.replace(".png", "_binary_temp.png")
                    cv2.imwrite(binary_path, binary)

                    result = self.ocr.ocr(binary_path, cls=False, det=False)

                    if os.path.exists(binary_path):
                        os.remove(binary_path)

                    if result and isinstance(result, list) and len(result) > 0:
                        extracted_text = ""
                        for line in result:
                            if isinstance(line, str):
                                extracted_text += line + "\n"
                        return self._post_process_ocr_text(extracted_text)
                    return ""

                except Exception as e2:
                    logger.error("Errore nell'OCR di fallback: %s", e2)
                    return ""

        except Exception as e:
            logger.error("Errore durante l'elaborazione dell'immagine: %s", e)
            return ""

