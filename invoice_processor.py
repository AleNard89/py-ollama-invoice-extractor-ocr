"""
File: invoice_processor.py
Description: Pipeline orchestrator for invoice data extraction.
Author: Alessandro.Nardelli
Date: 2025-03-28
"""

import os
import glob
import json
import logging
import shutil
import time
from typing import Any

import pandas as pd

from pdf_processor import PDFProcessor
from image_processor import ImageProcessor
from ocr_factory import OCRFactory
from ai_extractor_v2 import AIExtractor
from data_validator import DataValidator

logger = logging.getLogger(__name__)

DEFAULT_FIELDS = [
    "numero_fattura",
    "data_emissione",
    "fornitore",
    "partita_iva_fornitore",
    "cliente",
    "partita_iva_cliente",
    "importo_totale",
    "imponibile",
    "percentuale_iva",
    "importo_iva",
    "metodo_pagamento",
]

DEFAULT_ZONES = {
    "intestazione": (0, 0.35),
    "corpo": (0.25, 0.75),
    "pie_pagina": (0.65, 1.0),
}


class InvoiceProcessor:
    def __init__(
        self,
        base_dir: str,
        output_excel: str | None = None,
        debug_mode: bool = False,
        use_ocr: bool = True,
        ocr_type: str | None = "easyocr",
        use_gpu: bool = False,
        config: dict[str, Any] | None = None,
    ) -> None:
        self.base_dir = base_dir
        self.debug_mode = debug_mode
        self.use_ocr = use_ocr
        self.ocr_type = ocr_type
        self.use_gpu = use_gpu
        self.config = config or {}

        self.output_excel_path = output_excel or os.path.join(
            base_dir,
            f"Fatture_Estratte_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
        )

        self.fields = self.config.get("fields", DEFAULT_FIELDS)

        zones_cfg = self.config.get("zones", {})
        self.zones = {
            k: tuple(v) for k, v in zones_cfg.items()
        } if zones_cfg else DEFAULT_ZONES

        self.pdf_processor = PDFProcessor(debug_mode=debug_mode)
        self.image_processor = ImageProcessor(debug_mode=debug_mode)

        if use_ocr:
            self.ocr_processor = OCRFactory.create_ocr_processor(
                ocr_type=ocr_type,
                debug_mode=debug_mode,
                use_gpu=use_gpu,
                lang="it",
            )
            if not getattr(self.ocr_processor, "ocr_available", False):
                logger.warning("OCR non disponibile, passaggio alla modalita' senza OCR")
                self.use_ocr = False
        else:
            self.ocr_processor = None

        ai_cfg = self.config.get("ai", {})
        self.ai_extractor = AIExtractor(
            self.fields,
            debug_mode=debug_mode,
            model=ai_cfg.get("model"),
            temperature=ai_cfg.get("temperature", 0.1),
        )
        self.data_validator = DataValidator(self.fields, debug_mode=debug_mode)

    def extract_ocr_from_pdf(self, pdf_path, temp_dir):
        pdf_name = os.path.basename(pdf_path)
        
        # Directory per i file temporanei specifici di questo PDF
        pdf_temp_dir = os.path.join(temp_dir, pdf_name.replace('.pdf', ''))
        os.makedirs(pdf_temp_dir, exist_ok=True)
        
        logger.info("Conversione PDF in immagini ad alta risoluzione (300 DPI)")
        image_paths = self.pdf_processor.convert_pdf_to_images(pdf_path, pdf_temp_dir)
        
        logger.info("Miglioramento qualita' delle immagini")
        processed_paths = []
        for image_path in image_paths:
            processed_path = self.image_processor.preprocess_image(image_path)
            processed_paths.append(processed_path)
        
        logger.info("Estrazione delle zone dalla prima pagina")
        zones_data = {}
        if processed_paths:
            main_image = processed_paths[0]
            for zone_name in self.zones:
                zone_path = self.image_processor.extract_zone_from_image(
                    main_image, zone_name, self.zones)
                zones_data[zone_name] = {
                    'image_path': zone_path,
                    'ocr_text': ""  # OCR sarà eseguito solo se necessario in una fase successiva
                }
        
        return {
            'pages': [{'index': i, 'image_path': path, 'ocr_text': ""} for i, path in enumerate(processed_paths)],
            'zones': zones_data,
            'pdf_name': pdf_name
        }

    def analyze_invoice(self, pdf_ocr_data: dict) -> dict:
        results = {field: "non trovato" for field in self.fields}
        results["nome_file"] = pdf_ocr_data["pdf_name"]

        # FASE 1: Analizza ogni sezione individualmente senza OCR
        logger.info("Fase 1: Analisi delle sezioni senza OCR")
        zone_results = self.analyze_sections_without_ocr(pdf_ocr_data["zones"])

        for field in self.fields:
            for zone_name, zone_data in zone_results.items():
                if field in zone_data and zone_data[field] != "non trovato":
                    results[field] = zone_data[field]
                    logger.debug("Campo '%s' trovato nella zona '%s'", field, zone_name)

        missing_fields = [f for f in self.fields if results[f] == "non trovato"]
        logger.info("Campi mancanti dopo analisi zone: %d/%d", len(missing_fields), len(self.fields))

        # FASE 2: Analizza il documento completo per i campi mancanti
        if missing_fields:
            logger.info("Fase 2: Analisi documento completo per %d campi mancanti", len(missing_fields))
            main_image_path = pdf_ocr_data["pages"][0]["image_path"]
            full_doc_results = self.analyze_full_document_without_ocr(main_image_path, missing_fields)

            for field, value in full_doc_results.items():
                if value != "non trovato":
                    results[field] = value
                    logger.debug("Campo '%s' trovato nell'analisi documento completo", field)

            missing_fields = [f for f in self.fields if results[f] == "non trovato"]
            logger.info("Campi mancanti dopo analisi completa: %d/%d", len(missing_fields), len(self.fields))

        # FASE 3: OCR solo per campi ancora mancanti
        if missing_fields and self.use_ocr:
            logger.info("Fase 3: OCR per %d campi mancanti", len(missing_fields))
            ocr_results = self.analyze_sections_with_ocr(pdf_ocr_data["zones"], missing_fields)

            for field, value in ocr_results.items():
                if value != "non trovato":
                    results[field] = value
                    logger.debug("Campo '%s' trovato con supporto OCR", field)

        results = self.data_validator.validate_results(results)

        found = sum(1 for v in results.values() if v != "non trovato" and v != pdf_ocr_data["pdf_name"])
        logger.info("Riepilogo: trovati %d/%d campi", found, len(self.fields))
        return results

    def analyze_sections_without_ocr(self, zones_data: dict) -> dict:
        zone_results: dict = {}

        for zone_name, zone_data in zones_data.items():
            logger.info("Analisi zona '%s' senza OCR", zone_name)
            image_path = zone_data["image_path"]

            if not os.path.isfile(image_path):
                logger.warning("File non trovato: %s", image_path)
                continue

            try:
                zone_results[zone_name] = self.ai_extractor.analyze_zone(image_path, zone_name)
                found = sum(1 for v in zone_results[zone_name].values() if v != "non trovato")
                logger.info("Trovati %d campi nella zona '%s'", found, zone_name)
            except Exception as e:
                logger.error("Errore nell'analisi della zona '%s': %s", zone_name, e)
                zone_results[zone_name] = {}

        return zone_results

    def analyze_full_document_without_ocr(self, image_path: str, missing_fields: list[str]) -> dict:
        if not missing_fields:
            return {}

        try:
            document_results = self.ai_extractor.analyze_zone(image_path, "documento_completo")
            filtered = {k: v for k, v in document_results.items()
                        if k in missing_fields and v != "non trovato"}
            logger.info("Trovati %d/%d campi nell'analisi completa", len(filtered), len(missing_fields))
            return filtered
        except Exception as e:
            logger.error("Errore nell'analisi del documento completo: %s", e)
            return {}

    def analyze_sections_with_ocr(self, zones_data: dict, missing_fields: list[str]) -> dict:
        if not missing_fields or not self.use_ocr or not self.ocr_processor:
            return {}

        combined_results: dict = {}

        zone_field_mapping = {
            "intestazione": ["numero_fattura", "data_emissione", "fornitore",
                             "partita_iva_fornitore", "cliente", "partita_iva_cliente"],
            "corpo": ["imponibile", "percentuale_iva", "importo_iva"],
            "pie_pagina": ["importo_totale", "metodo_pagamento"],
        }

        for zone_name, zone_data in zones_data.items():
            zone_missing = [f for f in missing_fields if f in zone_field_mapping.get(zone_name, [])]
            if not zone_missing:
                continue

            logger.info("Analisi zona '%s' con OCR per %d campi", zone_name, len(zone_missing))
            image_path = zone_data["image_path"]

            if not os.path.isfile(image_path):
                logger.warning("File non trovato: %s", image_path)
                continue

            try:
                ocr_text = self.ocr_processor.extract_ocr_text(image_path)
                zone_data["ocr_text"] = ocr_text

                zone_results = self.ai_extractor.analyze_zone_with_ocr(image_path, ocr_text, zone_name)
                filtered = {k: v for k, v in zone_results.items()
                            if k in zone_missing and v != "non trovato"}
                combined_results.update(filtered)
                logger.info("Trovati %d/%d campi con OCR nella zona '%s'", len(filtered), len(zone_missing), zone_name)
            except Exception as e:
                logger.error("Errore nell'analisi OCR della zona '%s': %s", zone_name, e)

        return combined_results

    def _cleanup_temp(self, temp_dir: str) -> None:
        if os.path.isdir(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.debug("Rimossa cartella temporanea: %s", temp_dir)

    def process_all_pdfs(self) -> pd.DataFrame | None:
        pdf_files = glob.glob(os.path.join(self.base_dir, "*.pdf"))
        if not pdf_files:
            logger.warning("Nessun file PDF trovato nella directory")
            return None

        logger.info("File da elaborare: %d", len(pdf_files))

        all_results: list[dict] = []
        temp_dir = os.path.join(self.base_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)

        if self.debug_mode:
            debug_dir = os.path.join(self.base_dir, "debug_reports")
            os.makedirs(debug_dir, exist_ok=True)

        for i, pdf_file in enumerate(pdf_files, 1):
            pdf_name = os.path.basename(pdf_file)
            logger.info("-" * 50)
            logger.info("Elaborazione file %d/%d: %s", i, len(pdf_files), pdf_name)
            start_time = time.time()

            try:
                logger.info("Fase 1: Conversione PDF e preprocessing")
                pdf_ocr_data = self.extract_ocr_from_pdf(pdf_file, temp_dir)

                logger.info("Fase 2: Analisi fattura")
                results = self.analyze_invoice(pdf_ocr_data)
                results["nome_file"] = pdf_name

                if self.debug_mode:
                    logger.debug("Salvataggio report debug")
                    report_path = os.path.join(debug_dir, f"{pdf_name}_report.json")
                    with open(report_path, "w", encoding="utf-8") as f:
                        json.dump(results, f, indent=4, ensure_ascii=False)

                all_results.append(results)

            except Exception as e:
                logger.error("Errore nell'elaborazione di %s: %s", pdf_name, e)
                empty_result = {field: "non trovato" for field in self.fields}
                empty_result["nome_file"] = pdf_name
                all_results.append(empty_result)

            elapsed = time.time() - start_time
            logger.info("File elaborato in %.1f secondi", elapsed)

        # Pulizia file temporanei
        if not self.debug_mode:
            self._cleanup_temp(temp_dir)

        final_df = pd.DataFrame(all_results)

        columns = final_df.columns.tolist()
        if "nome_file" in columns and "numero_fattura" in columns:
            columns.remove("nome_file")
            columns.remove("numero_fattura")
            final_df = final_df[["nome_file", "numero_fattura"] + columns]

        final_df.to_excel(self.output_excel_path, index=False)
        logger.info("File Excel salvato in: %s", self.output_excel_path)
        logger.info("Elaborazione completata con successo!")
        return final_df