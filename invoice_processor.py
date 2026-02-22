"""
File: invoice_processor.py
Description: Versione aggiornata compatibile con AIExtractor semplificato
Author: Alessandro.Nardelli
Date: 2025-03-28
"""

import os
import glob
import json
import time
import re
import pandas as pd
import tempfile
from datetime import datetime
from pdf_processor import PDFProcessor
from image_processor import ImageProcessor
from ocr_factory import OCRFactory
from ai_extractor_v2 import AIExtractor
from data_validator import DataValidator


class InvoiceProcessor:
    def __init__(self, base_dir, output_excel=None, debug_mode=False, train_mode=False, 
                 use_ocr=True, ocr_type="easyocr", use_gpu=False):
        self.base_dir = base_dir
        self.output_excel_path = output_excel or os.path.join(base_dir, f"Fatture_Estratte_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
        self.debug_mode = debug_mode
        self.train_mode = train_mode
        self.use_ocr = use_ocr
        self.ocr_type = ocr_type
        self.use_gpu = use_gpu
        
        # Campi che vogliamo estrarre dalle fatture
        self.fields = [
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
            "metodo_pagamento"
        ]
        
        # Definizione delle zone della fattura (in percentuale dell'altezza dell'immagine)
        self.zones = {
            'intestazione': (0, 0.35),    # Primi 35% dell'immagine
            'corpo': (0.25, 0.75),        # Dal 25% al 75% dell'immagine (sovrapposizione)
            'pie_pagina': (0.65, 1.0)     # Dal 65% alla fine (sovrapposizione)
        }
        
        # Inizializza i processori
        self.pdf_processor = PDFProcessor(debug_mode=debug_mode)
        self.image_processor = ImageProcessor(debug_mode=debug_mode)
        
        # Inizializza OCR usando la factory
        if use_ocr:
            self.ocr_processor = OCRFactory.create_ocr_processor(
                ocr_type=ocr_type,
                debug_mode=debug_mode,
                use_gpu=use_gpu,
                lang="it"
            )
            
            if not hasattr(self.ocr_processor, 'ocr_available') or not self.ocr_processor.ocr_available:
                print("OCR non disponibile, passaggio alla modalità senza OCR")
                self.use_ocr = False
        else:
            self.ocr_processor = None
            
        # Inizializza AIExtractor con l'interfaccia semplificata (nota che ora non passiamo self.zones)
        self.ai_extractor = AIExtractor(self.fields, debug_mode=debug_mode)
        self.data_validator = DataValidator(self.fields, debug_mode=debug_mode)

    def extract_ocr_from_pdf(self, pdf_path, temp_dir):
        pdf_name = os.path.basename(pdf_path)
        
        # Directory per i file temporanei specifici di questo PDF
        pdf_temp_dir = os.path.join(temp_dir, pdf_name.replace('.pdf', ''))
        os.makedirs(pdf_temp_dir, exist_ok=True)
        
        # Converte il PDF in immagini ad alta risoluzione (aumentato a 300 DPI)
        print("  - Conversione PDF in immagini ad alta risoluzione (300 DPI)")
        image_paths = self.pdf_processor.convert_pdf_to_images(pdf_path, pdf_temp_dir)
        
        # Pre-elabora le immagini per migliorare la qualità
        print("  - Miglioramento qualità delle immagini")
        processed_paths = []
        for image_path in image_paths:
            processed_path = self.image_processor.preprocess_image(image_path)
            processed_paths.append(processed_path)
        
        # Estrai le zone dalla prima pagina
        print("  - Estrazione delle zone dalla prima pagina")
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

    def analyze_invoice(self, pdf_ocr_data):
        """
        Analizza una fattura seguendo il flusso richiesto:
        1. Analizza ogni sezione individualmente senza OCR
        2. Analizza il documento completo per i campi mancanti senza OCR
        3. Usa OCR solo se necessario e solo per le sezioni con campi mancanti
        """
        results = {field: "non trovato" for field in self.fields}
        results['nome_file'] = pdf_ocr_data['pdf_name']
        
        # FASE 1: Analizza ogni sezione individualmente senza OCR
        print("  - Fase 1: Analisi delle sezioni senza OCR")
        zone_results = self.analyze_sections_without_ocr(pdf_ocr_data['zones'])
        
        # Aggiorna i risultati con i dati trovati nelle zone
        for field in self.fields:
            for zone_name, zone_data in zone_results.items():
                if field in zone_data and zone_data[field] != "non trovato":
                    results[field] = zone_data[field]
                    print(f"    - Campo '{field}' trovato nella zona '{zone_name}'")
        
        # Controlla quali campi sono ancora mancanti
        missing_fields = [field for field in self.fields if results[field] == "non trovato"]
        print(f"    - Campi ancora mancanti dopo analisi delle sezioni: {len(missing_fields)}/{len(self.fields)}")
        
        # FASE 2: Analizza il documento completo per i campi mancanti
        if missing_fields:
            print(f"  - Fase 2: Analisi del documento completo per {len(missing_fields)} campi mancanti")
            main_image_path = pdf_ocr_data['pages'][0]['image_path']
            full_doc_results = self.analyze_full_document_without_ocr(main_image_path, missing_fields)
            
            # Aggiorna i risultati con i dati trovati nel documento completo
            for field, value in full_doc_results.items():
                if value != "non trovato":
                    results[field] = value
                    print(f"    - Campo '{field}' trovato nell'analisi del documento completo")
            
            # Aggiorna la lista dei campi mancanti
            missing_fields = [field for field in self.fields if results[field] == "non trovato"]
            print(f"    - Campi ancora mancanti dopo analisi completa: {len(missing_fields)}/{len(self.fields)}")
        
        # FASE 3: Usa OCR solo per le sezioni con campi mancanti se necessario
        if missing_fields and self.use_ocr:
            print(f"  - Fase 3: Utilizzo OCR per {len(missing_fields)} campi ancora mancanti")
            ocr_results = self.analyze_sections_with_ocr(pdf_ocr_data['zones'], missing_fields)
            
            # Aggiorna i risultati con i dati trovati tramite OCR
            for field, value in ocr_results.items():
                if value != "non trovato":
                    results[field] = value
                    print(f"    - Campo '{field}' trovato con supporto OCR")
        
        # Validazione finale dei risultati
        results = self.data_validator.validate_results(results)
        
        # Mostra riepilogo finale
        found_fields = sum(1 for f in results.values() if f != "non trovato" and f != pdf_ocr_data['pdf_name'])
        total_fields = len(self.fields)
        print(f"  - Riepilogo finale: Trovati {found_fields}/{total_fields} campi")
        
        return results

    def analyze_sections_without_ocr(self, zones_data):
        """Analizza tutte le sezioni del documento senza usare OCR"""
        zone_results = {}
        
        for zone_name, zone_data in zones_data.items():
            print(f"    - Analisi zona '{zone_name}' senza OCR")
            
            # Verifica che il percorso dell'immagine esista
            image_path = zone_data['image_path']
            if not os.path.isfile(image_path):
                print(f"    - Warning: File not found: {image_path}")
                continue
            
            try:
                # Analizza la zona con il modello AI (senza OCR)
                # Nota: nella nuova API, passiamo zone_name solo per debug
                zone_results[zone_name] = self.ai_extractor.analyze_zone(
                    image_path, 
                    zone_name  # Ora opzionale e solo per debug
                )
                
                # Conta campi trovati
                found_in_zone = sum(1 for v in zone_results[zone_name].values() if v != "non trovato")
                print(f"      - Trovati {found_in_zone} campi nella zona '{zone_name}'")
            except Exception as e:
                print(f"    - Errore nell'analisi della zona '{zone_name}': {str(e)}")
                zone_results[zone_name] = {}
        
        return zone_results

    def analyze_full_document_without_ocr(self, image_path, missing_fields):
        """Analizza l'intero documento senza OCR per trovare i campi mancanti"""
        if not missing_fields:
            return {}
        
        try:
            # Nella versione semplificata, non abbiamo più analyze_missing_fields
            # Usiamo la stessa analyze_zone ma sul documento principale
            document_results = self.ai_extractor.analyze_zone(
                image_path,
                "documento_completo"  # solo per debug
            )
            
            # Filtra solo i campi mancanti che abbiamo trovato
            filtered_results = {k: v for k, v in document_results.items() 
                              if k in missing_fields and v != "non trovato"}
            
            # Conta campi trovati
            found_fields = len(filtered_results)
            print(f"      - Trovati {found_fields}/{len(missing_fields)} campi nell'analisi completa")
            
            return filtered_results
        except Exception as e:
            print(f"    - Errore nell'analisi del documento completo: {str(e)}")
            return {}

    def analyze_sections_with_ocr(self, zones_data, missing_fields):
        """Analizza le sezioni con OCR, ma solo per i campi ancora mancanti"""
        if not missing_fields or not self.use_ocr or not self.ocr_processor:
            return {}
        
        combined_results = {}
        
        # Mappa dei campi più probabilmente trovabili in ciascuna zona
        zone_field_mapping = {
            'intestazione': ["numero_fattura", "data_emissione", "fornitore", "partita_iva_fornitore", 
                            "cliente", "partita_iva_cliente"],
            'corpo': ["imponibile", "percentuale_iva", "importo_iva"],
            'pie_pagina': ["importo_totale", "metodo_pagamento"]
        }
        
        # Per ogni zona, verifica se ci sono campi mancanti che potrebbero essere in quella zona
        for zone_name, zone_data in zones_data.items():
            # Filtra i campi mancanti che sono più probabilmente in questa zona
            zone_missing_fields = [field for field in missing_fields 
                                if field in zone_field_mapping.get(zone_name, [])]
            
            if not zone_missing_fields:
                continue
            
            print(f"    - Analisi zona '{zone_name}' con OCR per {len(zone_missing_fields)} campi")
            
            # Verifica che il percorso dell'immagine esista
            image_path = zone_data['image_path']
            if not os.path.isfile(image_path):
                print(f"    - Warning: File not found: {image_path}")
                continue
            
            try:
                # Esegui OCR solo ora, e solo su questa zona
                ocr_text = self.ocr_processor.extract_ocr_text(image_path)
                
                # Aggiorna i dati della zona con il testo OCR
                zone_data['ocr_text'] = ocr_text
                
                # Analizza la zona con il supporto OCR
                # Nota l'ordine dei parametri cambiato nella nuova API
                zone_results = self.ai_extractor.analyze_zone_with_ocr(
                    image_path,
                    ocr_text,
                    zone_name  # solo per debug
                )
                
                # Filtra solo i campi che stiamo cercando
                filtered_results = {k: v for k, v in zone_results.items() 
                                if k in zone_missing_fields and v != "non trovato"}
                
                # Aggiorna i risultati combinati
                combined_results.update(filtered_results)
                
                # Conta campi trovati
                found_with_ocr = len(filtered_results)
                print(f"      - Trovati {found_with_ocr}/{len(zone_missing_fields)} campi con OCR nella zona '{zone_name}'")
                
            except Exception as e:
                print(f"    - Errore nell'analisi OCR della zona '{zone_name}': {str(e)}")
        
        return combined_results

    def process_all_pdfs(self):
        """Elabora tutti i file PDF nella directory specificata, uno alla volta."""
        # Ottieni tutti i file PDF
        pdf_files = glob.glob(os.path.join(self.base_dir, "*.pdf"))
        if not pdf_files:
            print("Nessun file PDF trovato nella directory")
            return
        
        print(f"Numero di file da gestire: {len(pdf_files)}")
        
        # Lista per raccogliere tutti i risultati
        all_results = []
        
        # Crea cartelle temporanee
        temp_dir = os.path.join(self.base_dir, "temp")
        os.makedirs(temp_dir, exist_ok=True)
        
        if self.debug_mode:
            debug_dir = os.path.join(self.base_dir, "debug_reports")
            os.makedirs(debug_dir, exist_ok=True)
        
        # Elabora ogni PDF completamente prima di passare al successivo
        for i, pdf_file in enumerate(pdf_files, 1):
            pdf_name = os.path.basename(pdf_file)
            print("-" * 50)
            print(f"Inizio elaborazione file {i}/{len(pdf_files)} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"File Name: {pdf_name}")
            start_time = time.time()
            
            try:
                # Fase 1: Conversione del PDF in immagini e preprocessamento
                print(f"Fase 1: Conversione PDF in immagini e preprocessamento")
                pdf_ocr_data = self.extract_ocr_from_pdf(pdf_file, temp_dir)
                
                # Fase 2: Analisi della fattura con il nuovo flusso
                print(f"Fase 2: Analisi della fattura con il nuovo flusso")
                results = self.analyze_invoice(pdf_ocr_data)
                
                # Aggiungi nome_file ai risultati
                results['nome_file'] = pdf_name
                
                # Fase 3: Salva i risultati in modalità debug
                if self.debug_mode:
                    print(f"Fase 3: Debug mode - Salvataggio report dettagliato")
                    report_path = os.path.join(debug_dir, f"{pdf_name}_report.json")
                    with open(report_path, 'w', encoding='utf-8') as f:
                        json.dump(results, f, indent=4, ensure_ascii=False)
                
                # Fase 4: Addestramento (se attivo)
                if self.train_mode:
                    print(f"Fase 4: Train mode - Salvataggio dati di addestramento")
                    self.save_training_data(pdf_name, results, pdf_ocr_data, temp_dir)
                
                # Aggiungi i risultati alla lista principale
                all_results.append(results)
                
            except Exception as e:
                print(f"Errore nell'elaborazione di {pdf_name}: {str(e)}")
                # Aggiungi comunque un risultato vuoto con il nome del file
                empty_result = {field: "non trovato" for field in self.fields}
                empty_result['nome_file'] = pdf_name
                all_results.append(empty_result)
            
            # Calcola e mostra il tempo di elaborazione per questo file
            elapsed_time = time.time() - start_time
            print(f"File elaborato in {elapsed_time:.1f} secondi - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Crea il dataframe con tutti i risultati
        final_df = pd.DataFrame(all_results)
        
        # Riordina le colonne per avere nome_file e numero_fattura all'inizio
        columns = final_df.columns.tolist()
        if "nome_file" in columns and "numero_fattura" in columns:
            columns.remove("nome_file")
            columns.remove("numero_fattura")
            column_order = ["nome_file", "numero_fattura"] + columns
            final_df = final_df[column_order]
        
        # Salva i risultati in Excel (solo una volta alla fine dell'elaborazione)
        final_df.to_excel(self.output_excel_path, index=False)
        print(f"\nFile Excel salvato in: {self.output_excel_path}")
        
        print("\nElaborazione completata con successo!")
        return final_df