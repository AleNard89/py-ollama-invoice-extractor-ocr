"""
File: pdf_processor.py
Description: Questo modulo contiene la classe PDFProcessor che fornisce metodi per convertire un PDF in immagini.
Author: Alessandro.Nardelli
Date: 2025-03-21
"""

import os
import tempfile
from pdf2image import convert_from_path
from datetime import datetime

class PDFProcessor:
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
    
    def convert_pdf_to_images(self, pdf_path, output_dir):
        # Assicurati che la directory di output esista
        os.makedirs(output_dir, exist_ok=True)
        
        # Converte il PDF in immagini con risoluzione aumentata a 300 DPI
        images = convert_from_path(pdf_path, dpi=300)
        
        # Salva le immagini
        image_paths = []
        for i, image in enumerate(images):
            image_path = os.path.join(output_dir, f'page_{i+1}.png')
            filename = os.path.basename(image_path)
            #print(f"Creata immagine: {filename}")
            image.save(image_path, 'PNG')
            image_paths.append(image_path)
        
        return image_paths
 