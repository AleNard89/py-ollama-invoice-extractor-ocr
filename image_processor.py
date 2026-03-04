"""
File: image_processor.py
Description: Classe per il preprocessamento delle immagini
Author: Alessandro.Nardelli
Date: 2025-03-21
"""

import logging
import os

import cv2
import numpy as np

logger = logging.getLogger(__name__)

class ImageProcessor:
    def __init__(self, debug_mode=False):
        self.debug_mode = debug_mode
    
    def deskew(self, image_path):
        # Verifica se image_path è una stringa o un percorso
        if not isinstance(image_path, str) or not os.path.isfile(image_path):
            return image_path
        
        # Carica l'immagine
        img = cv2.imread(image_path, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return image_path
        
        # Trova i contorni
        coords = np.column_stack(np.where(img > 0))
        
        # Verifica se ci sono abbastanza punti
        if len(coords) < 100:
            return image_path
        
        # Calcola l'angolo di inclinazione
        angle = cv2.minAreaRect(coords.astype(np.float32))[-1]
        
        # Correggi l'angolo
        if angle < -45:
            angle = -(90 + angle)
        else:
            angle = -angle
        
        # Limita la correzione a piccole inclinazioni
        if abs(angle) > 10:
            return image_path
        
        # Ruota l'immagine
        (h, w) = img.shape[:2]
        center = (w // 2, h // 2)
        M = cv2.getRotationMatrix2D(center, angle, 1.0)
        rotated = cv2.warpAffine(
            img, M, (w, h), 
            flags=cv2.INTER_CUBIC, 
            borderMode=cv2.BORDER_REPLICATE
        )
        
        # Salva l'immagine raddrizzata
        deskewed_path = image_path.replace('.png', '_deskewed.png')
        filename = os.path.basename(deskewed_path)
        #print(f"Creata immagine: {filename}")
        cv2.imwrite(deskewed_path, rotated)
        
        return deskewed_path

    def preprocess_image(self, image_path, enhance_contrast=True):
        # Verifica se il percorso è valido
        if not isinstance(image_path, str) or not os.path.isfile(image_path):
            return image_path
            
        # Carica l'immagine
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        # Converti in scala di grigi
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Ridimensiona l'immagine se troppo grande (mantenendo l'aspect ratio)
        height, width = gray.shape
        if width > 2500:
            scale_factor = 2500 / width
            new_width = int(width * scale_factor)
            new_height = int(height * scale_factor)
            gray = cv2.resize(gray, (new_width, new_height), interpolation=cv2.INTER_AREA)
        
        # Applica riduzione del rumore
        denoised = cv2.fastNlMeansDenoising(gray, None, h=10, templateWindowSize=7, searchWindowSize=21)
        
        if enhance_contrast:
            # Migliora il contrasto con CLAHE (più aggressivo)
            clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))  # Aumentato da 2.0 a 3.0
            enhanced = clahe.apply(denoised)
            
            # Applica equalizzazione dell'istogramma per migliorare ulteriormente il contrasto
            enhanced = cv2.equalizeHist(enhanced)
            
            # Applica una leggera nitidezza (sharpening)
            kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
            enhanced = cv2.filter2D(enhanced, -1, kernel)
        else:
            # Applica miglioramento del contrasto standard
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            enhanced = clahe.apply(denoised)
        
        # Binarizzazione adattiva con parametri più aggressivi per i contrasti
        thresh = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 11, 4  # Aumentato il valore C da 2 a 4 per maggior contrasto
        )
        
        # Applicazione di morfologia matematica per migliorare la qualità del testo
        kernel = np.ones((1, 1), np.uint8)
        opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
        
        # Salva l'immagine elaborata sia in versione standard che ad alto contrasto
        processed_path = image_path.replace('.png', '_processed.png')
        cv2.imwrite(processed_path, opening)
        
        if enhance_contrast:
            high_contrast_path = image_path.replace('.png', '_high_contrast.png')
            cv2.imwrite(high_contrast_path, thresh)
            logger.debug("Creata immagine ad alto contrasto: %s", os.path.basename(high_contrast_path))
        
        # Applica deskew all'immagine processata
        deskewed_path = self.deskew(processed_path)
        
        return deskewed_path

    def extract_zone_from_image(self, image_path, zone_name, zones):
        if zone_name not in zones:
            return image_path
        
        # Verifica se il percorso è valido
        if not isinstance(image_path, str) or not os.path.isfile(image_path):
            return image_path
        
        # Carica l'immagine
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        height, width = img.shape[:2]
        
        # Calcola i limiti della zona
        start_percent, end_percent = zones[zone_name]
        start_y = int(height * start_percent)
        end_y = int(height * end_percent)
        
        # Estrai la zona
        zone_img = img[start_y:end_y, 0:width]
        
        # Salva l'immagine della zona
        zone_path = image_path.replace('.png', f'_{zone_name}.png')
        
        # Verifica che la directory esista
        os.makedirs(os.path.dirname(zone_path), exist_ok=True)
        
        cv2.imwrite(zone_path, zone_img)
        filename = os.path.basename(zone_path)
        #print(f"Creata immagine: {filename}")
        return zone_path


    def enhance_header_zone(self, image_path):
        """
        Migliora specificamente il contrasto della zona dell'intestazione per facilitare 
        l'estrazione dei campi critici come numero fattura e partita IVA.
        """
        if not isinstance(image_path, str) or not os.path.isfile(image_path):
            return image_path
        
        # Carica l'immagine
        img = cv2.imread(image_path)
        if img is None:
            return image_path
        
        # Estrai solo la zona superiore (intestazione) - primi 30% dell'altezza
        height, width = img.shape[:2]
        header_height = int(height * 0.30)
        header_img = img[0:header_height, 0:width]
        
        # Converti in scala di grigi
        gray = cv2.cvtColor(header_img, cv2.COLOR_BGR2GRAY)
        
        # Applica contrasto MOLTO elevato
        clahe = cv2.createCLAHE(clipLimit=4.0, tileGridSize=(4, 4))
        enhanced = clahe.apply(gray)
        
        # Equalizza l'istogramma per massimizzare il contrasto
        enhanced = cv2.equalizeHist(enhanced)
        
        # Applica binarizzazione con Otsu (più efficace per un contrasto elevato)
        _, binary = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Inverti l'immagine se necessario (testo bianco su sfondo nero -> testo nero su sfondo bianco)
        # Determina se l'immagine ha più pixel bianchi o neri
        white_pixels = np.sum(binary == 255)
        black_pixels = np.sum(binary == 0)
        if white_pixels < black_pixels:
            binary = cv2.bitwise_not(binary)
        
        # Salva l'immagine dell'intestazione migliorata
        header_path = image_path.replace('.png', '_header_enhanced.png')
        cv2.imwrite(header_path, binary)
        logger.debug("Creata immagine intestazione migliorata: %s", os.path.basename(header_path))
        
        return header_path




