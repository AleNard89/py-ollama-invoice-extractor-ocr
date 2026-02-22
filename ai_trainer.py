"""
File: ai_trainer.py
Description: Questo modulo contiene la classe AITrainer per l'addestramento del modello AI.
Author: Alessandro.Nardelli
Date: 2025-03-21
"""

import os
import json
import time
import pandas as pd
from ollama import Client

class AITrainer:
    def __init__(self, base_dir, fields, debug_mode=False):
        self.base_dir = base_dir
        self.fields = fields
        self.debug_mode = debug_mode
        self.client = Client()
        self.model = 'llama3.2-vision:latest'
        
        # Crea la directory per i dati di addestramento
        self.train_dir = os.path.join(base_dir, "training_data")
        os.makedirs(self.train_dir, exist_ok=True)
    
    def collect_training_data(self):
        """Raccoglie i dati di addestramento esistenti."""
        train_files = os.listdir(self.train_dir)
        train_data = []
        
        for file in train_files:
            if file.endswith('_train.json'):
                try:
                    with open(os.path.join(self.train_dir, file), 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        train_data.append(data)
                except Exception as e:
                    print(f"Errore nella lettura del file {file}: {str(e)}")
        
        return train_data
    
    def save_training_example(self, pdf_name, image_path, ocr_text, extracted_data, zone_name=None):
        timestamp = pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')
        example_id = f"{pdf_name.replace('.pdf', '')}_{timestamp}"
        
        if zone_name:
            example_id += f"_{zone_name}"
        
        example_data = {
            "id": example_id,
            "pdf_name": pdf_name,
            "image_path": image_path,
            "ocr_text": ocr_text,
            "extracted_data": extracted_data,
            "zone_name": zone_name,
            "timestamp": timestamp
        }
        
        # Salva l'esempio
        example_path = os.path.join(self.train_dir, f"{example_id}_example.json")
        with open(example_path, 'w', encoding='utf-8') as f:
            json.dump(example_data, f, indent=4, ensure_ascii=False)
        
        return example_path

    def generate_training_prompt(self, ocr_text, field_data, zone_name=None, ocr_used=True):
        # Crea il JSON atteso come output
        expected_json = {}
        for field in self.fields:
            if field in field_data and field_data[field] != "non trovato":
                expected_json[field] = field_data[field]
        
        expected_output = json.dumps(expected_json, ensure_ascii=False, indent=2)
        
        if zone_name:
            zone_context = f"Questa è la zona '{zone_name}' di una fattura."
        else:
            zone_context = "Questa è un'intera pagina di una fattura."
        
        # Sezione OCR solo se è stato utilizzato
        ocr_section = ""
        if ocr_used and ocr_text and ocr_text.strip():
            ocr_section = f"""
            ## Testo OCR:
            ```
            {ocr_text}
            ```
            """
        else:
            ocr_section = "Estrai i dati direttamente dall'immagine della fattura."
        
        prompt = f"""# Compito: Estrazione dati da fattura
        
        {zone_context}
        
        {ocr_section}
        
        ## Output atteso:
        ```json
        {expected_output}
        ```
        
        Analizza {'il testo OCR ed ' if ocr_used else ''}estrai esattamente i campi mostrati nell'output atteso.
        Segui queste regole precise:
        1. Estrai SOLO i campi presenti nell'output atteso
        2. Usa esattamente gli stessi valori dell'output atteso
        3. Per i campi monetari, riporta solo i numeri senza simboli di valuta
        4. Converti i numeri dal formato europeo (1.234,56 €) al formato con solo il punto decimale (1234.56)
        
        Rispondi SOLO con un oggetto JSON contenente i campi richiesti."""
        
        return prompt










