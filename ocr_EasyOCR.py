"""
File: ocr_EasyOCR.py
Description: Questo script contiene la classe OCRProcessor, che estrae testo da immagini usando OCR.
Author: Alessandro.Nardelli
Date: 2025-03-21
"""

import os
import re
import cv2
import numpy as np
import Levenshtein
from datetime import datetime

class OCRProcessor:
    def __init__(self, debug_mode=False, use_gpu=False, lang="it"):
        self.debug_mode = debug_mode
        self.use_gpu = use_gpu
        
        # Inizializzazione di EasyOCR
        try:
            import easyocr
            self.reader = easyocr.Reader(['it', 'en'], gpu=use_gpu, quantize=True)
            self.ocr_available = True
            print("EasyOCR trovato e disponibile")
        except Exception as e:
            self.ocr_available = False
            print(f"Attenzione: EasyOCR non disponibile: {str(e)}")
            print("L'estrazione OCR restituirà testi vuoti. Installare EasyOCR o utilizzare la modalità senza OCR.")

    def _post_process_ocr_text(self, text):
        """Applica correzioni post-OCR per migliorare la qualità dei risultati."""
        if not text:
            return ""
        
        # Correzioni comuni per errori OCR
        corrections = {
            'l': '1',  # Spesso l'OCR confonde 'l' minuscola con '1'
            'O': '0',  # Spesso l'OCR confonde 'O' maiuscola con '0'
            '€uro': 'Euro',
            'lVA': 'IVA',
            'lmporto': 'Importo',
            'lmponibile': 'Imponibile',
            '|VA': 'IVA'
        }
        
        # Applica correzioni specifiche per parti numeriche (es. nelle fatture)
        patterns = [
            # Correggi formato numeri con spazi
            (r'(\d) (\d)', r'\1\2'),
            # Correggi date con formati errati
            (r'(\d{2})\.(\d{2})\.(\d{4})', r'\1/\2/\3'),
            # Correggi IVA e percentuali
            (r'(\d+)[,\.](\d+)\s*o/o', r'\1.\2%'),
            # Correggi Euro e simboli di valuta
            (r'(\d+)[,\.](\d+)\s*€', r'\1.\2 Euro')
        ]
        
        result = text
        
        # Applica le correzioni di base
        for wrong, correct in corrections.items():
            result = result.replace(wrong, correct)
        
        # Applica pattern di correzione più complessi
        for pattern, replacement in patterns:
            result = re.sub(pattern, replacement, result)
        
        # Correggi righe vuote multiple
        result = re.sub(r'\n\s*\n', '\n\n', result)
        
        return result
    
    def _combine_ocr_results(self, texts):
        """Combina i risultati OCR usando tecniche avanzate."""
        if not texts:
            return ""
        
        # Normalizza e prepara i testi
        normalized_texts = []
        for text in texts:
            # Dividi in righe e rimuovi righe vuote
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            normalized_texts.append(lines)
        
        # Costruisci un set di righe uniche
        all_lines = set()
        for lines in normalized_texts:
            all_lines.update(lines)
        
        # Ordina le righe per popolarità (quante volte appaiono nei diversi testi)
        line_scores = {}
        for line in all_lines:
            score = sum(1 for lines in normalized_texts if line in lines)
            line_scores[line] = score
        
        # Ordina le righe per punteggio e poi per lunghezza (privilegia linee più lunghe)
        sorted_lines = sorted(all_lines, key=lambda line: (-line_scores[line], -len(line)))
        
        # Identifica e rimuovi linee duplicate o molto simili
        final_lines = []
        for line in sorted_lines:
            # Controlla se questa linea è molto simile a una già inclusa
            if not any(self._are_lines_similar(line, existing) for existing in final_lines):
                final_lines.append(line)
        
        return "\n".join(final_lines)
    
    def _are_lines_similar(self, line1, line2, threshold=0.8):
        """Verifica se due righe sono simili usando la distanza di Levenshtein."""
        if abs(len(line1) - len(line2)) > 10:
            return False
            
        # Calcola la similarità
        distance = Levenshtein.distance(line1, line2)
        max_len = max(len(line1), len(line2))
        if max_len == 0:
            return True
            
        similarity = 1 - (distance / max_len)
        return similarity > threshold

    def extract_ocr_text(self, image_path):
        """Estrae testo da un'immagine usando EasyOCR."""
        if not self.ocr_available:
            return ""
        
        try:
            # Carica e preelabora l'immagine
            img = cv2.imread(image_path)
            if img is None:
                print(f"Errore: impossibile leggere l'immagine {image_path}")
                return ""
            
            # Ridimensiona l'immagine se troppo grande
            height, width = img.shape[:2]
            max_dim = max(height, width)
            if max_dim > 2000:
                scale = 2000 / max_dim
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                
                if self.debug_mode:
                    resized_path = image_path.replace('.png', '_resized.png')
                    cv2.imwrite(resized_path, img)
            
            # Estrai testo con EasyOCR
            result = self.reader.readtext(img)
            
            # Elabora i risultati
            extracted_text = []
            for detection in result:
                text = detection[1]
                confidence = detection[2]
                
                # Filtra risultati a bassa confidenza
                if confidence > 0.3:
                    extracted_text.append(text)
            
            # Unisci il testo estratto
            combined_text = "\n".join(extracted_text)
            
            # Applica correzioni post-OCR
            processed_text = self._post_process_ocr_text(combined_text)
            
            if self.debug_mode:
                # Salva il risultato finale
                combined_file = image_path.replace('.png', '_ocr_combined.txt')
                with open(combined_file, 'w', encoding='utf-8') as f:
                    f.write(processed_text)
            
            return processed_text
        except Exception as e:
            print(f"Errore durante l'OCR: {str(e)}")
            return ""