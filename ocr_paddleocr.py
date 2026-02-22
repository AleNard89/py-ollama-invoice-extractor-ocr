 
"""
File: ocr_paddleocr.py
Description: Questo script contiene la classe OCRProcessor, che estrae testo da immagini usando OCR.
Author: Alessandro.Nardelli
Date: 2025-03-21
"""

# ocr_processor.py
import os
import re
import numpy as np
import cv2
from paddleocr import PaddleOCR
import Levenshtein
from datetime import datetime

class OCRProcessor:
    def __init__(self, debug_mode=False, use_gpu=False, use_angle_cls=True, lang="it"):
        self.debug_mode = debug_mode
        
        # Inizializzazione di PaddleOCR con opzioni ottimizzate per Apple Silicon
        try:
            self.ocr = PaddleOCR(
                use_angle_cls=False,  # Disabilita il rilevamento dell'angolo (riduce il consumo di memoria)
                lang=lang,
                use_gpu=use_gpu,
                show_log=False,
                rec_batch_num=1,     # Riduce il batch size al minimo
                det_db_box_thresh=0.5,  # Aumenta la soglia per ridurre i falsi positivi
                det_db_unclip_ratio=1.5  # Valore equilibrato per il rilevamento delle caselle di testo
            )
            self.paddle_available = True
            print("PaddleOCR trovato e disponibile")
        except Exception as e:
            self.paddle_available = False
            print(f"Attenzione: PaddleOCR non disponibile: {str(e)}")
            print("L'estrazione OCR restituirà testi vuoti. Installare correttamente PaddleOCR o utilizzare la modalità senza OCR.")

    def _post_process_ocr_text(self, text):
        if not text:
            return ""
        
        # Correzioni comuni per errori OCR
        corrections = {
            'l': '1',
            'O': '0',
            '€uro': 'Euro',
            'lVA': 'IVA',
            'lmporto': 'Importo',
            'lmponibile': 'Imponibile',
            '|VA': 'IVA'
        }
        
        patterns = [
            (r'(\d) (\d)', r'\1\2'),
            (r'(\d{2})\.(\d{2})\.(\d{4})', r'\1/\2/\3'),
            (r'(\d+)[,\.](\d+)\s*o/o', r'\1.\2%'),
            (r'(\d+)[,\.](\d+)\s*€', r'\1.\2 Euro')
        ]
        
        result = text
        
        for wrong, correct in corrections.items():
            result = result.replace(wrong, correct)
        
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        result = re.sub(r'\n\s*\n', '\n\n', result)
        
        return result
    
    def _combine_ocr_results(self, texts):
        # Metodo esistente...
        if not texts:
            return ""
        
        normalized_texts = []
        for text in texts:
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            normalized_texts.append(lines)
        
        all_lines = set()
        for lines in normalized_texts:
            all_lines.update(lines)
        
        line_scores = {}
        for line in all_lines:
            score = sum(1 for lines in normalized_texts if line in lines)
            line_scores[line] = score
        
        sorted_lines = sorted(all_lines, key=lambda line: (-line_scores[line], -len(line)))
        
        final_lines = []
        for line in sorted_lines:
            if not any(self._are_lines_similar(line, existing) for existing in final_lines):
                final_lines.append(line)
        
        return "\n".join(final_lines)
    
    def _are_lines_similar(self, line1, line2, threshold=0.8):
        if abs(len(line1) - len(line2)) > 10:
            return False
            
        distance = Levenshtein.distance(line1, line2)
        max_len = max(len(line1), len(line2))
        if max_len == 0:
            return True
            
        similarity = 1 - (distance / max_len)
        return similarity > threshold

    def extract_ocr_text(self, image_path):
        """Estrae testo da un'immagine usando PaddleOCR con gestione robusta degli errori."""
        
        if not self.paddle_available:
            return ""
        
        try:
            # Carica l'immagine originale
            img = cv2.imread(image_path)
            if img is None:
                print(f"Errore: impossibile leggere l'immagine {image_path}")
                return ""
            
            # Ridimensiona l'immagine per ridurre i requisiti di memoria
            height, width = img.shape[:2]
            max_dimension = max(height, width)
            if max_dimension > 1800:  # Ridimensiona solo se necessario
                scale = 1800 / max_dimension
                new_width = int(width * scale)
                new_height = int(height * scale)
                img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)
                
                if self.debug_mode:
                    resized_path = image_path.replace('.png', '_resized.png')
                    cv2.imwrite(resized_path, img)
            
            # Estrattore OCR con gestione errori
            try:
                # Esegui OCR con opzioni limitate per M3 Pro
                result = self.ocr.ocr(img, cls=False)
                
                # Elabora i risultati in modo semplificato per minimizzare errori
                if result and isinstance(result, list) and len(result) > 0:
                    # Il formato dei risultati potrebbe variare in base alla versione di PaddleOCR
                    page_result = result[0]
                    
                    # Estrai solo il testo senza calcoli complessi
                    extracted_text = ""
                    if page_result and isinstance(page_result, list):
                        for text_box in page_result:
                            # Gestisci diversi formati di output
                            if isinstance(text_box, list) and len(text_box) >= 2:
                                # Formato [box, [text, confidence]]
                                if isinstance(text_box[1], list) or isinstance(text_box[1], tuple):
                                    extracted_text += text_box[1][0] + "\n"
                                # Formato più semplice [box, text]
                                elif isinstance(text_box[1], str):
                                    extracted_text += text_box[1] + "\n"
                    
                    # Post-processa il testo
                    return self._post_process_ocr_text(extracted_text)
                
                return ""
                
            except Exception as e:
                print(f"Errore durante l'OCR principale: {str(e)}")
                
                # Fallback: prova con un approccio ancora più semplice
                try:
                    # Converti in bianco e nero per ridurre al minimo il carico computazionale
                    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    
                    # Salva temporaneamente l'immagine binarizzata
                    binary_path = image_path.replace('.png', '_binary_temp.png')
                    cv2.imwrite(binary_path, binary)
                    
                    # Prova OCR sull'immagine binarizzata
                    result = self.ocr.ocr(binary_path, cls=False, det=False)  # Solo riconoscimento, no rilevamento
                    
                    # Elimina l'immagine temporanea
                    if os.path.exists(binary_path):
                        os.remove(binary_path)
                    
                    # Elabora i risultati in modo molto semplificato
                    if result and isinstance(result, list) and len(result) > 0:
                        extracted_text = ""
                        for line in result:
                            if isinstance(line, str):
                                extracted_text += line + "\n"
                        
                        return self._post_process_ocr_text(extracted_text)
                    
                    return ""
                    
                except Exception as e2:
                    print(f"Errore anche nell'OCR di fallback: {str(e2)}")
                    return ""
                
        except Exception as e:
            print(f"Errore durante l'elaborazione dell'immagine: {str(e)}")
            return ""

