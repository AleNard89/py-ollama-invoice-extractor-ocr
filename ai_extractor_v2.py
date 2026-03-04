"""
File: ai_extractor_v3.py
Description: Modulo contenente la classe AIExtractor semplificata per estrarre dati da fatture usando un modello AI.
Author: Alessandro.Nardelli
Date: 2025-03-28
"""

import os
import json
import re
from ollama import Client

class AIExtractor:
    def __init__(self, fields, debug_mode=False, model=None, temperature=0.1):
        """ Inizializza l'estrattore AI per documenti. """
        self.fields = fields
        self.debug_mode = debug_mode
        self.temperature = temperature
        self.client = Client()
        self.model = model or 'qwen2.5vl:7b'

    def _extract_json(self, text):
        """Estrai dati in formato JSON dalla risposta del modello."""
        try:
            # Strategie di estrazione JSON
            extraction_strategies = [
                # Strategia 1: l'intero testo è JSON
                lambda t: json.loads(t),
                
                # Strategia 2: cerca delimitatori JSON standard
                lambda t: json.loads(t[t.find('{'):t.rfind('}')+1]) if t.find('{') != -1 and t.rfind('}') != -1 else None,
                
                # Strategia 3: cerca ```json ... ``` pattern
                lambda t: json.loads(t[t.find('{', t.find('```json')):t.rfind('```', t.find('{', t.find('```json')))]) 
                    if t.find('```json') != -1 and t.find('{', t.find('```json')) != -1 else None,
                
                # Strategia 4: cerca ``` ... ``` pattern
                lambda t: json.loads(t[t.find('{', t.find('```')):t.rfind('```', t.find('{', t.find('```')))]) 
                    if t.find('```') != -1 and t.find('{', t.find('```')) != -1 else None,
                
                # Strategia 5: cerca { ... } in qualsiasi punto del testo
                lambda t: json.loads(t[t.find('{'):t.rfind('}')+1]) 
                    if t.find('{') != -1 and t.rfind('}') != -1 else None
            ]
            
            # Prova tutte le strategie di estrazione JSON
            extracted_json = None
            
            for strategy in extraction_strategies:
                try:
                    extracted_json = strategy(text)
                    if extracted_json is not None:
                        break
                except:
                    continue
            
            # Se non è stato possibile estrarre un JSON, prova con regex
            if extracted_json is None:
                # Risultato da costruire
                constructed_json = {}
                
                # Pattern per la ricerca di campi nel testo strutturato
                field_patterns = {
                    'numero_fattura': [
                        r'(?:numero\s*(?:documento|fattura))(?:[:\s]+)([A-Za-z0-9\-\/\.]+)',
                        r'(?:invoice|document)\s*(?:number|no\.?)(?:[:\s]+)([A-Za-z0-9\-\/\.]+)',
                        r'(?:n(?:°|\.)[:\s]*)([A-Za-z0-9\-\/\.]+)'
                    ],
                    'data_emissione': [
                        r'(?:data\s*(?:emissione|documento|fattura))(?:[:\s]+)(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4})',
                        r'(?:date|issue\s*date)(?:[:\s]+)(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4})',
                        r'(?:data)(?:[:\s]+)(\d{1,2}[\/\.\-]\d{1,2}[\/\.\-]\d{2,4})'
                    ],
                    'fornitore': [
                        r'(?:fornitore|mittente|sender|from)(?:[:\s]+)(.*?)(?:[\n\r]|$)',
                        r'(?:nome\s*azienda)(?:[:\s]+)(.*?)(?:[\n\r]|$)',
                    ],
                    'partita_iva_fornitore': [
                        r'(?:p\.?iva|vat|codice\s*fiscale|tax\s*id)(?:[:\s]+)([A-Za-z0-9]+)',
                    ],
                    'cliente': [
                        r'(?:cliente|destinatario|recipient|to|bill\s*to)(?:[:\s]+)(.*?)(?:[\n\r]|$)',
                    ],
                    'partita_iva_cliente': [
                        r'(?:p\.?iva\s*cliente|customer\s*vat)(?:[:\s]+)([A-Za-z0-9]+)',
                    ],
                    'imponibile': [
                        r'(?:imponibile|subtotale|base\s*imponibile|net\s*amount)(?:[:\s]+)([0-9.,]+)',
                    ],
                    'percentuale_iva': [
                        r'(?:percentuale\s*(?:iva|imposta)|tax\s*rate|vat\s*rate)(?:[:\s]+)([0-9.,]+)',
                        r'iva\s*([0-9.,]+)\s*%',
                        r'([0-9.,]+)\s*%'
                    ],
                    'importo_iva': [
                        r'(?:importo\s*(?:iva|imposta)|tax\s*amount|vat\s*amount)(?:[:\s]+)([0-9.,]+)',
                    ],
                    'importo_totale': [
                        r'(?:totale|importo\s*totale|total|amount\s*due)(?:[:\s]+)([0-9.,]+)',
                    ],
                    'metodo_pagamento': [
                        r'(?:metodo\s*di\s*pagamento|payment\s*method|terms)(?:[:\s]+)(.*?)(?:[\n\r]|$)',
                    ],
                    'valuta': [
                        r'(?:valuta|currency)(?:[:\s]+)([A-Za-z€$£¥]+)',
                    ],
                    'note': [
                        r'(?:note|annotazioni|comments)(?:[:\s]+)(.*?)(?:[\n\r]|$)',
                    ],
                }
                
                # Cerchiamo di costruire un JSON utilizzando espressioni regolari
                for field, patterns in field_patterns.items():
                    for pattern in patterns:
                        matches = re.search(pattern, text, re.IGNORECASE)
                        if matches and matches.group(1) and matches.group(1).strip():
                            constructed_json[field] = matches.group(1).strip()
                            break
                            
                # Se abbiamo trovato almeno un campo, usiamo il JSON costruito
                if constructed_json:
                    extracted_json = constructed_json
                else:
                    # Altrimenti, creiamo un JSON con "non trovato" per tutti i campi
                    return {field: "non trovato" for field in self.fields}
            
            # Normalizza i campi
            result = {}
            
            for field in self.fields:
                if field in extracted_json and extracted_json[field] and extracted_json[field] != "non trovato":
                    # Normalizza i valori numerici
                    if field in ["imponibile", "importo_totale", "importo_iva", "prezzo_unitario", "quantita"]:
                        if isinstance(extracted_json[field], str):
                            # Pulisci e normalizza il formato numerico
                            value_str = extracted_json[field]
                            for symbol in ['€', '$', '£', '¥', '₽', 'CHF', 'USD', 'EUR', 'GBP']:
                                value_str = value_str.replace(symbol, '')
                            value_str = value_str.strip()
                            
                            # Gestisci diversi formati numerici
                            if ',' in value_str and '.' in value_str:
                                if value_str.find(',') > value_str.find('.'):  # Formato europeo 1.234,56
                                    value_str = value_str.replace('.', '').replace(',', '.')
                                else:  # Formato inglese 1,234.56
                                    value_str = value_str.replace(',', '')
                            elif ',' in value_str:  # Solo virgole
                                value_str = value_str.replace(',', '.')
                            
                            # Rimuovi eventuali caratteri non numerici rimanenti
                            value_str = ''.join(c for c in value_str if c.isdigit() or c == '.')
                            
                            try:
                                # Assicurati che ci sia solo un punto decimale
                                if value_str.count('.') > 1:
                                    parts = value_str.split('.')
                                    value_str = ''.join(parts[:-1]) + '.' + parts[-1]
                                    
                                result[field] = str(float(value_str))
                            except:
                                result[field] = extracted_json[field]
                        else:
                            result[field] = str(extracted_json[field])
                    elif field == "percentuale_iva":
                        if isinstance(extracted_json[field], str):
                            # Rimuovi caratteri non numerici e converti la virgola in punto
                            value_str = ''.join(c for c in extracted_json[field] if c.isdigit() or c in [',', '.', '%'])
                            value_str = value_str.replace(',', '.').replace('%', '')
                            try:
                                result[field] = str(float(value_str))
                            except:
                                result[field] = extracted_json[field]
                        else:
                            result[field] = str(extracted_json[field])
                    else:
                        # Per gli altri campi, rimuovi spazi extra
                        if isinstance(extracted_json[field], str):
                            result[field] = extracted_json[field].strip()
                        else:
                            result[field] = str(extracted_json[field])
            
            return result
        except Exception as e:
            print(f"Errore nell'estrazione JSON: {str(e)}")
            return {field: "non trovato" for field in self.fields}

    def analyze_zone(self, image_path, zone_name=None, temperature=None):
        """ Analizza una zona del documento per estrarre informazioni rilevanti. """
        # Usa la temperatura di default se non specificata
        if temperature is None:
            temperature = self.temperature

        # Usa lo stesso prompt standardizzato per tutte le zone
        prompt = self._create_prompt()
        
        # Invia la richiesta al modello
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Sei un sistema esperto nell'estrazione di dati da documenti finanziari. Il tuo compito è analizzare attentamente l'immagine e restituire SOLO i dati richiesti in formato JSON." 
                },
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_path]
                }
            ],
            options={"temperature": temperature, "num_predict": 1024}
        )
        
        # Estrai il JSON dalla risposta
        response_text = response['message']['content']
        
        # Salva la risposta completa per debug
        if self.debug_mode:
            debug_dir = os.path.dirname(image_path)
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            zone_suffix = f"_{zone_name}" if zone_name else ""
            response_path = image_path.replace('.png', f'_response{zone_suffix}.txt')
            with open(response_path, 'w', encoding='utf-8') as f:
                f.write(response_text)
        
        # Estrai i risultati JSON
        results = self._extract_json(response_text)
        
        return results

    def analyze_zone_with_ocr(self, image_path, ocr_text, zone_name=None, temperature=None):
        """ Analizza una zona del documento utilizzando anche i dati OCR. """
        # Usa la temperatura di default se non specificata
        if temperature is None:
            temperature = self.temperature

        # Usa lo stesso prompt standardizzato per tutte le zone, con OCR
        prompt = self._create_prompt(ocr_text)
        
        # Invia la richiesta al modello
        response = self.client.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": "Sei un sistema esperto nell'estrazione di dati da documenti finanziari. Il tuo compito è analizzare attentamente l'immagine e il testo OCR per restituire SOLO i dati richiesti in formato JSON."
                },
                {
                    "role": "user",
                    "content": prompt,
                    "images": [image_path]
                }
            ],
            options={"temperature": temperature, "num_predict": 1024}
        )
        
        # Estrai il JSON dalla risposta
        response_text = response['message']['content']
        
        # Salva la risposta completa per debug
        if self.debug_mode:
            debug_dir = os.path.dirname(image_path)
            if not os.path.exists(debug_dir):
                os.makedirs(debug_dir)
            zone_suffix = f"_{zone_name}" if zone_name else ""
            response_path = image_path.replace('.png', f'_response{zone_suffix}_ocr.txt')
            with open(response_path, 'w', encoding='utf-8') as f:
                f.write(response_text)
        
        # Estrai i risultati JSON
        results = self._extract_json(response_text)
        
        return results

    def _create_prompt(self, ocr_text=None):
        # Costruisci la sezione OCR (se disponibile)
        ocr_section = ""
        if ocr_text and ocr_text.strip():
            ocr_section = f"""
            Il testo OCR estratto è:
            ```
            {ocr_text}
            ```
            
            Usa questo testo come supporto, ma dai priorità alla tua analisi visiva dell'immagine.
            """
        else: ocr_section = ""

        # Crea un elenco di tutti i campi che potrebbero essere estratti
        fields_str = ', '.join(self.fields)

        # Prompt standard per tutte le zone
        prompt = f"""Sei un esperto nell'estrazione di dati da documenti finanziari.

        COMPITO: Analizza attentamente questa immagine ed estrai i seguenti dati:
        {fields_str}
        
        ISTRUZIONI GENERALI:
        - Per valori monetari, estrai SOLO i numeri senza simboli di valuta
        - Converti i numeri dal formato locale al formato con punto decimale (1234.56)
        - Cerca informazioni in tutte le lingue più comuni (italiano, inglese, francese, tedesco, spagnolo)
        - Attenzione a tabelle, colonne, e layout non standard
        - Alcuni valori potrebbero essere sotto alle loro etichette, non accanto
        - Non confondere codici cliente con numeri fattura o P.IVA
        - I numeri fattura si trovano spesso in alto nel documento vicino alla data
        - Le informazioni fiscali (P.IVA) sono spesso vicino ai dati dell'azienda
        - Gli importi totali sono generalmente nella parte inferiore del documento
        
        {ocr_section}
        
        FORMATO RISPOSTA: Fornisci SOLO un JSON con i campi trovati, in questo formato:
        {{
        "campo1": "valore1",
        "campo2": "valore2"
        }}
        
        È preferibile non includere un dato piuttosto che includerlo erroneamente.
        """
        
        return prompt

    def merge_results(self, *result_sets):
        """Unisce i risultati da diverse analisi, dando priorità ai valori non vuoti."""
        merged = {field: "non trovato" for field in self.fields}
        
        for results in result_sets:
            for field, value in results.items():
                # Aggiorna solo se il campo è nei campi di interesse e se il valore attuale è "non trovato"
                if field in self.fields and (merged.get(field) == "non trovato" or merged.get(field) is None):
                    merged[field] = value
        
        return merged




