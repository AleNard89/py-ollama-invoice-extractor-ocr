"""
File: main.py
descrizione: Questo script è il punto di partenza per l'estrazione delle informazioni dalle fatture PDF.
Author: Alessandro.Nardelli
Date: 2025-03-27
"""

import os
import time
from datetime import datetime
from invoice_processor import InvoiceProcessor

def check_ocr_availability(ocr_type):
    """Verifica la disponibilità del motore OCR richiesto"""
    if ocr_type == "easyocr":
        try:
            import easyocr
            return True
        except ImportError:
            return False
    elif ocr_type == "paddleocr":
        try:
            from paddleocr import PaddleOCR
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

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    pdf_folder = os.environ.get("PDF_FOLDER", os.path.join(script_dir, "invoice"))
    
    # Output Excel automatico (generato nella stessa directory)
    output_excel = None
    
    # Modalità debug (False per default)
    debug_mode = False
    
    # Modalità addestramento (False per default)
    train_mode = False
    
    # ============ CONFIGURAZIONE OCR ============
    # Scegli uno dei seguenti OCR: "easyocr", "paddleocr", "tesseract", o None per disabilitare OCR
    #ocr_type = "easyocr"
    #ocr_type = "paddleocr"
    ocr_type = "tesseract"
    ocr_type = None
    
    # Imposta use_ocr=True per abilitare OCR, False per disabilitarlo
    use_ocr = True if ocr_type else False
    # ============================================
    
    # Utilizza GPU (se disponibile)
    use_gpu = False
    
    # Verifica disponibilità OCR selezionato
    if use_ocr and not check_ocr_availability(ocr_type):
        print(f"{ocr_type} non disponibile. Passaggio automatico alla modalità senza OCR.")
        use_ocr = False
    
    print("\n")
    print("-" * 50)
    print(f"AVVIO ESTRAZIONE FATTURE")
    print(f"Process start at: {datetime.now().strftime('%Y%m%d_%H%M%S')} ")
    print(f"Directory: {pdf_folder}")
    print(f"Output: {output_excel or 'Automatico'}")
    print(f"Debug mode: {debug_mode}")
    print(f"Train mode: {train_mode}")
    print(f"OCR: {ocr_type if use_ocr else 'Disabilitato'}")
    print(f"Use GPU: {use_gpu}")
    
    start_time = time.time()
    
    # Crea il processore di fatture
    processor = InvoiceProcessor(
        pdf_folder, 
        output_excel, 
        debug_mode, 
        train_mode, 
        use_ocr, 
        ocr_type, 
        use_gpu
    )
    
    # Elabora tutti i PDF
    processor.process_all_pdfs()
    
    elapsed_time = time.time() - start_time
    print(f"\nElaborazione completata in {elapsed_time:.1f} secondi")

if __name__ == "__main__":
    main()