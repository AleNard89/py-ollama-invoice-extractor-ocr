"""
File: ocr_factory.py
Description: Factory class per creare l'istanza OCR appropriata in base alla scelta dell'utente
Author: Alessandro.Nardelli
Date: 2025-03-27
"""

class OCRFactory:
    @staticmethod
    def create_ocr_processor(ocr_type="easyocr", debug_mode=False, use_gpu=False, lang="it"):
        ocr_type = ocr_type.lower()
        
        if ocr_type == "easyocr":
            try:
                from ocr_EasyOCR import OCRProcessor
                return OCRProcessor(debug_mode=debug_mode, use_gpu=use_gpu, lang=lang)
            except ImportError as e:
                print(f"EasyOCR non disponibile: {str(e)}")
                print("Passaggio alla modalità senza OCR.")
                return DummyOCRProcessor(debug_mode)
                
        elif ocr_type == "paddleocr":
            try:
                from ocr_paddleocr import OCRProcessor
                return OCRProcessor(debug_mode=debug_mode, use_gpu=use_gpu, lang=lang)
            except ImportError as e:
                print(f"PaddleOCR non disponibile: {str(e)}")
                print("Passaggio alla modalità senza OCR.")
                return DummyOCRProcessor(debug_mode)
                
        elif ocr_type == "tesseract":
            try:
                from ocr_tesseract import OCRProcessor
                return OCRProcessor(debug_mode=debug_mode)
            except ImportError as e:
                print(f"Tesseract non disponibile: {str(e)}")
                print("Passaggio alla modalità senza OCR.")
                return DummyOCRProcessor(debug_mode)
        
        else:
            print(f"Tipo OCR '{ocr_type}' non riconosciuto. Opzioni valide: easyocr, paddleocr, tesseract")
            print("Passaggio alla modalità senza OCR.")
            return DummyOCRProcessor(debug_mode)


class DummyOCRProcessor:
    """Classe OCR fittizia che restituisce sempre testo vuoto (usata quando l'OCR richiesto non è disponibile)"""
    
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
        self.ocr_available = False
        print("Modalità senza OCR attivata")
    
    def extract_ocr_text(self, image_path):
        """Restituisce sempre una stringa vuota"""
        return ""