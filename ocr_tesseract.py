"""
File: ocr_tesseract.py
Description: Questo script contiene la classe OCRProcessor, che estrae testo da immagini usando OCR e preserva il formato.
Author: Alessandro.Nardelli
Date: 2025-03-27 (modificato)
"""

import os
import re
import pytesseract
import Levenshtein
from PIL import Image, ImageEnhance
from datetime import datetime

class OCRProcessor:

    def __init__(self, debug_mode=False, preserve_format=True):
        self.debug_mode = debug_mode
        self.preserve_format = preserve_format
        
        # Verifica la disponibilità di Tesseract
        try:
            import pytesseract
            import shutil
            tesseract_path = shutil.which('tesseract')
            if tesseract_path:
                pytesseract.pytesseract.tesseract_cmd = tesseract_path
            
            pytesseract.get_tesseract_version()
            self.tesseract_available = True
            self.ocr_available = True
            print("Tesseract OCR trovato e disponibile")
        except Exception as e:
            self.tesseract_available = False
            print(f"Attenzione: Tesseract OCR non disponibile: {str(e)}")
            print("L'estrazione OCR restituirà testi vuoti. Configurare il percorso di Tesseract o utilizzare la modalità senza OCR.")
 
    def _post_process_ocr_text(self, text, preserve_format=None):
        """
        Applica correzioni post-OCR per migliorare la qualità dei risultati.
        Se preserve_format è True, mantiene il layout del testo.
        """
        if preserve_format is None:
            preserve_format = self.preserve_format
            
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
        
        # Dividi il testo in linee per mantenere il formato
        lines = text.splitlines()
        processed_lines = []
        
        for line in lines:
            processed_line = line
            
            # Applica le correzioni di base
            for wrong, correct in corrections.items():
                processed_line = processed_line.replace(wrong, correct)
            
            # Applica pattern di correzione più complessi
            for pattern, replacement in patterns:
                processed_line = re.sub(pattern, replacement, processed_line)
                
            processed_lines.append(processed_line)
        
        result = "\n".join(processed_lines)
        
        if not preserve_format:
            # Se non dobbiamo preservare il formato, rimuoviamo le righe vuote multiple
            result = re.sub(r'\n\s*\n', '\n\n', result)
        
        return result
    
    def _combine_ocr_results(self, texts, preserve_format=None):
        """
        Combina i risultati OCR usando tecniche avanzate.
        Se preserve_format è True, mantiene la posizione relativa delle righe.
        """
        if preserve_format is None:
            preserve_format = self.preserve_format
            
        if not texts:
            return ""
        
        # Se non dobbiamo preservare il formato, usiamo l'algoritmo originale
        if not preserve_format:
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
        else:
            # Versione che preserva il formato
            
            # Trova il testo con la migliore qualità complessiva
            # (calcolata come numero di caratteri non spazi e lunghezza totale)
            best_text = ""
            best_score = 0
            
            for text in texts:
                # Calcola un punteggio di qualità basato su vari fattori
                non_space_chars = sum(1 for c in text if not c.isspace())
                total_length = len(text)
                line_count = len(text.splitlines())
                
                # Favorisce testi con più caratteri non spazio, più lunghi, e con più linee
                score = non_space_chars * 2 + total_length + line_count * 10
                
                if score > best_score:
                    best_score = score
                    best_text = text
            
            # Utilizza il miglior risultato come base, ma correggi possibili errori
            # usando le informazioni dagli altri risultati
            best_lines = best_text.splitlines()
            
            # Identifica parole che appaiono in modo consistente in più risultati OCR
            word_confidence = {}
            for text in texts:
                for word in re.findall(r'\b\w+\b', text):
                    word = word.lower()
                    word_confidence[word] = word_confidence.get(word, 0) + 1
            
            # Correggi possibili errori nelle linee del miglior testo
            corrected_lines = []
            for line in best_lines:
                # Mantieni le linee vuote per preservare il formato
                if not line.strip():
                    corrected_lines.append(line)
                    continue
                
                corrected_line = line
                # Per ogni parola nel dizionario di confidenza
                for word, confidence in word_confidence.items():
                    if confidence >= len(texts) / 2:  # Se la parola appare in almeno metà dei risultati
                        # Cerca varianti simili della parola nella linea corrente
                        for word_in_line in re.findall(r'\b\w+\b', line):
                            if len(word) > 3 and len(word_in_line) > 3:  # Solo per parole abbastanza lunghe
                                # Se le parole sono simili ma non identiche
                                similarity = self._word_similarity(word, word_in_line.lower())
                                if 0.7 < similarity < 0.95:  # Abbastanza simili ma non identiche
                                    # Sostituisci con la versione più frequente
                                    corrected_line = re.sub(r'\b' + re.escape(word_in_line) + r'\b', 
                                                            word_in_line[0].upper() + word[1:] if word_in_line[0].isupper() else word,
                                                            corrected_line)
                
                corrected_lines.append(corrected_line)
            
            return "\n".join(corrected_lines)
    
    def _word_similarity(self, word1, word2):
        """Calcola la similarità tra due parole usando la distanza di Levenshtein."""
        distance = Levenshtein.distance(word1, word2)
        max_len = max(len(word1), len(word2))
        if max_len == 0:
            return 1.0
        return 1.0 - (distance / max_len)
    
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
        """Estrae testo da un'immagine usando diverse tecniche OCR e le combina, preservando il formato."""
        
        if not self.tesseract_available:
            # Se Tesseract non è disponibile, restituisce una stringa vuota
            return ""
        
        # Configurazioni OCR ottimizzate per diversi tipi di testo
        # Se vogliamo preservare il formato, adattiamo le configurazioni
        if self.preserve_format:
            custom_configs = [
                r'--oem 3 --psm 6 -l ita+eng',  # Blocco di testo uniforme
                r'--oem 3 --psm 3 -l ita+eng',  # Layout completo della pagina
                r'--oem 3 --psm 4 -l ita+eng',  # Singola colonna di testo
                # Aggiunto per preservare il formato
                r'--oem 3 --psm 1 -l ita+eng',  # Layout completo con orientamento automatico
                r'--oem 3 --psm 13 -l ita+eng'  # Testo come singola linea
            ]
        else:
            custom_configs = [
                r'--oem 3 --psm 6 -l ita+eng',  # Blocco di testo uniforme
                r'--oem 3 --psm 3 -l ita+eng',  # Layout completo della pagina
                r'--oem 3 --psm 4 -l ita+eng',  # Singola colonna di testo
                r'--oem 3 --psm 11 -l ita+eng',  # Testo sparso
                r'--oem 3 --psm 12 -l ita+eng -c tessedit_char_whitelist="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz,.-:/€$% "'
            ]
        
        # Prova diverse configurazioni e diverse tecniche di miglioramento immagine
        all_texts = []
        original_img = Image.open(image_path)
        
        # Se vogliamo preservare il formato, aggiungiamo tecniche specifiche
        if self.preserve_format:
            # Tecniche di enhancement per l'immagine originale
            enhancement_techniques = [
                lambda img: img,  # Immagine originale
                lambda img: ImageEnhance.Contrast(img).enhance(1.2),  # Leggero aumento del contrasto
                lambda img: ImageEnhance.Brightness(img).enhance(1.1)  # Leggero aumento della luminosità
            ]
        else:
            # Tecniche originali
            enhancement_techniques = [
                lambda img: img,  # Immagine originale
                lambda img: ImageEnhance.Contrast(img).enhance(1.5),  # Aumenta contrasto
                lambda img: ImageEnhance.Sharpness(img).enhance(2.0),  # Aumenta nitidezza
            ]
        
        if self.debug_mode:
            print(f"{datetime.now().strftime('%Y%m%d_%H%M%S')} - Lettura tramite OCR avanzata" + 
                 (" (preservazione formato)" if self.preserve_format else ""))
            print("-" * 50)
        
        # Applica ogni tecnica di enhancement con ogni configurazione OCR
        for enhance_func in enhancement_techniques:
            enhanced_img = enhance_func(original_img)
            
            # Salva temporaneamente l'immagine migliorata
            enhanced_path = image_path.replace('.png', f'_enhanced_temp.png')
            enhanced_img.save(enhanced_path)
            
            for config in custom_configs:
                try:
                    # Metodo aggiuntivo per preservare il formato quando richiesto
                    if self.preserve_format and 'psm 3' in config:
                        # Usa image_to_data per ottenere informazioni sulla posizione del testo
                        data = pytesseract.image_to_data(enhanced_path, config=config, output_type=pytesseract.Output.DICT)
                        
                        # Raggruppa il testo per linee basate sulla posizione Y
                        y_groups = {}
                        for i, text in enumerate(data['text']):
                            if text.strip():  # Considera solo testo non vuoto
                                y_pos = data['top'][i]
                                # Raggruppa con una tolleranza di 5 pixel
                                group_y = y_pos // 5 * 5
                                if group_y not in y_groups:
                                    y_groups[group_y] = []
                                y_groups[group_y].append((data['left'][i], text))
                        
                        # Ordina per posizione Y e poi per posizione X
                        lines = []
                        for y in sorted(y_groups.keys()):
                            line_items = sorted(y_groups[y])
                            line = ' '.join(text for _, text in line_items)
                            lines.append(line)
                        
                        text = '\n'.join(lines)
                    else:
                        # Estrai testo dall'immagine migliorata usando il metodo standard
                        text = pytesseract.image_to_string(enhanced_path, config=config)
                    
                    # Applica correzioni post-OCR, rispettando il formato se richiesto
                    text = self._post_process_ocr_text(text)
                    #print("-" * 30)
                    #print(text)
                    
                    if self.debug_mode:
                        print(f"Configurazione: {config[:30]}...")
                        print(f"Primi 100 caratteri: {text[:100]}...")
                        print("-" * 30)
                    
                    all_texts.append(text)
                except Exception as e:
                    if self.debug_mode:
                        print(f"Errore OCR con config {config}: {str(e)}")
            
            # Rimuovi il file temporaneo
            try:
                os.remove(enhanced_path)
            except:
                pass
        
        # Combina i risultati rispettando il formato se richiesto
        combined_text = self._combine_ocr_results(all_texts)
        
        if self.debug_mode:
            # Salva il risultato finale
            combined_file = image_path.replace('.png', '_ocr_combined.txt')
            with open(combined_file, 'w', encoding='utf-8') as f:
                f.write(combined_text)
            
            if self.preserve_format:
                print(f"Risultato finale salvato in {combined_file} (con preservazione formato)")
            else:
                print(f"Risultato finale salvato in {combined_file}")
        
        return combined_text

    def extract_ocr_text_with_hocr(self, image_path):
        """
        Estrae testo mantenendo informazioni precise sul layout usando hOCR.
        Questo metodo è specifico per la preservazione del formato.
        """
        if not self.tesseract_available:
            return ""
            
        if not self.preserve_format:
            # Se non è richiesta la preservazione del formato, usa il metodo standard
            return self.extract_ocr_text(image_path)
            
        try:
            # Usa hOCR per ottenere informazioni dettagliate sul layout
            hocr_output = pytesseract.image_to_pdf_or_hocr(
                image_path, 
                extension='hocr',
                config=r'--oem 3 --psm 1 -l ita+eng'  # Usa PSM 1 per rilevare il layout completo
            )
            
            # Estrai il testo mantenendo le informazioni sulla posizione
            import bs4
            soup = bs4.BeautifulSoup(hocr_output, 'html.parser')
            
            # Estrai tutte le parole con le loro coordinate
            words = []
            for word in soup.find_all('span', class_='ocrx_word'):
                text = word.get_text().strip()
                if text:
                    # Estrai le coordinate dal titolo
                    title = word['title']
                    bbox = re.search(r'bbox (\d+) (\d+) (\d+) (\d+)', title)
                    if bbox:
                        x1, y1, x2, y2 = map(int, bbox.groups())
                        words.append({
                            'text': text,
                            'x1': x1,
                            'y1': y1,
                            'x2': x2,
                            'y2': y2,
                            'line_y': (y1 + y2) // 2  # Centro verticale per raggruppare in linee
                        })
            
            # Raggruppa le parole in linee (tolleranza di 10 pixel)
            lines = {}
            for word in words:
                line_y = word['line_y'] // 10 * 10
                if line_y not in lines:
                    lines[line_y] = []
                lines[line_y].append(word)
            
            # Ordina le parole in ogni linea da sinistra a destra
            for line_y in lines:
                lines[line_y].sort(key=lambda w: w['x1'])
            
            # Genera il testo formatato
            result_lines = []
            for line_y in sorted(lines.keys()):
                line_words = lines[line_y]
                
                # Calcola gli spazi tra le parole in base alla distanza x
                line_text = ""
                for i, word in enumerate(line_words):
                    if i > 0:
                        prev_word = line_words[i-1]
                        # Calcola la distanza tra parole
                        distance = word['x1'] - prev_word['x2']
                        
                        # Aggiungi spazi proporzionali alla distanza
                        if distance < 10:
                            line_text += " "  # Spazio normale
                        elif distance < 30:
                            line_text += "  "  # Spazio doppio
                        else:
                            # Calcola quanti tab (o spazi) inserire
                            tabs = distance // 40  # Ogni 40 pixel un nuovo tab
                            line_text += "\t" * min(3, tabs)  # Massimo 3 tab
                    
                    line_text += word['text']
                
                result_lines.append(line_text)
            
            # Unisci le linee con newline
            result = "\n".join(result_lines)
            
            # Applica post-processing standard
            result = self._post_process_ocr_text(result, preserve_format=True)
            
            if self.debug_mode:
                # Salva il risultato hOCR
                hocr_file = image_path.replace('.png', '_ocr_hocr.txt')
                with open(hocr_file, 'w', encoding='utf-8') as f:
                    f.write(result)
                print(f"Risultato hOCR salvato in {hocr_file}")
            
            return result
            
        except Exception as e:
            if self.debug_mode:
                print(f"Errore nell'estrazione hOCR: {str(e)}")
            # In caso di errore, ricorri al metodo standard
            return self.extract_ocr_text(image_path)
        


