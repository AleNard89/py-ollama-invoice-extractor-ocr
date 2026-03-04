"""
File: main.py
Description: Entry point for invoice data extraction pipeline.
Author: Alessandro.Nardelli
Date: 2025-03-27
"""

import os
import sys
import time
import argparse
import logging
from datetime import datetime

import yaml

from invoice_processor import InvoiceProcessor

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def check_ocr_availability(ocr_type: str | None) -> bool:
    if ocr_type == "easyocr":
        try:
            import easyocr  # noqa: F401
            return True
        except ImportError:
            return False
    elif ocr_type == "paddleocr":
        try:
            from paddleocr import PaddleOCR  # noqa: F401
            return True
        except ImportError:
            return False
    elif ocr_type == "tesseract":
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract structured data from PDF invoices using Ollama AI + optional OCR."
    )
    parser.add_argument(
        "-i", "--input",
        help="Path to the folder containing PDF invoices (default: ./invoice)",
    )
    parser.add_argument(
        "-o", "--output",
        help="Path for the output Excel file (default: auto-generated in input folder)",
    )
    parser.add_argument(
        "--ocr",
        choices=["easyocr", "paddleocr", "tesseract"],
        default=None,
        help="OCR engine to use as fallback (default: disabled)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (saves intermediate outputs)",
    )
    parser.add_argument(
        "--gpu",
        action="store_true",
        help="Use GPU acceleration for OCR (if available)",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Path to config.yaml (default: config.yaml in project root)",
    )
    return parser.parse_args()


def setup_logging(debug: bool) -> None:
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main() -> None:
    args = parse_args()

    script_dir = os.path.dirname(os.path.abspath(__file__))
    config_path = args.config or os.path.join(script_dir, "config.yaml")

    cfg: dict = {}
    if os.path.isfile(config_path):
        cfg = load_config(config_path)

    # Resolve settings: CLI args > config.yaml > defaults
    debug_mode = args.debug or cfg.get("output", {}).get("debug_mode", False)
    setup_logging(debug_mode)

    pdf_folder = (
        args.input
        or os.environ.get("PDF_FOLDER")
        or os.path.join(script_dir, "invoice")
    )
    output_excel = args.output
    ocr_type = args.ocr or cfg.get("ocr", {}).get("engine")
    use_gpu = args.gpu or cfg.get("ocr", {}).get("use_gpu", False)
    use_ocr = ocr_type is not None

    if use_ocr and not check_ocr_availability(ocr_type):
        logger.warning("%s non disponibile. Passaggio alla modalita' senza OCR.", ocr_type)
        use_ocr = False
        ocr_type = None

    logger.info("-" * 50)
    logger.info("AVVIO ESTRAZIONE FATTURE")
    logger.info("Directory: %s", pdf_folder)
    logger.info("Output: %s", output_excel or "Automatico")
    logger.info("Debug: %s", debug_mode)
    logger.info("OCR: %s", ocr_type if use_ocr else "Disabilitato")
    logger.info("GPU: %s", use_gpu)

    if not os.path.isdir(pdf_folder):
        logger.error("Directory non trovata: %s", pdf_folder)
        sys.exit(1)

    start_time = time.time()

    processor = InvoiceProcessor(
        pdf_folder,
        output_excel,
        debug_mode,
        use_ocr=use_ocr,
        ocr_type=ocr_type,
        use_gpu=use_gpu,
        config=cfg,
    )

    processor.process_all_pdfs()

    elapsed = time.time() - start_time
    logger.info("Elaborazione completata in %.1f secondi", elapsed)


if __name__ == "__main__":
    main()