# Invoice Data Extraction with Ollama + OCR

Sistema modulare per l'estrazione automatica di dati da fatture PDF utilizzando modelli AI vision (Ollama) con supporto opzionale OCR.

## Panoramica

Il progetto converte fatture PDF in immagini, le analizza tramite un modello di linguaggio visivo locale (Ollama) e ne estrae i dati strutturati in formato Excel. Supporta tre motori OCR opzionali come fallback per migliorare l'accuratezza.

### Campi estratti

| Campo | Descrizione |
|-------|-------------|
| `numero_fattura` | Numero identificativo del documento |
| `data_emissione` | Data di emissione della fattura |
| `fornitore` | Ragione sociale del fornitore |
| `partita_iva_fornitore` | P.IVA del fornitore |
| `cliente` | Ragione sociale del cliente |
| `partita_iva_cliente` | P.IVA del cliente |
| `importo_totale` | Importo totale (IVA inclusa) |
| `imponibile` | Importo imponibile (prima dell'IVA) |
| `percentuale_iva` | Aliquota IVA applicata |
| `importo_iva` | Importo dell'IVA |
| `metodo_pagamento` | Modalita' di pagamento |

## Architettura

```
main.py                  # Entry point e configurazione
├── invoice_processor.py # Orchestratore pipeline di elaborazione
│   ├── pdf_processor.py     # Conversione PDF -> immagini (300 DPI)
│   ├── image_processor.py   # Preprocessing (deskew, denoise, contrast, binarize)
│   ├── ocr_factory.py       # Factory pattern per motori OCR
│   │   ├── ocr_EasyOCR.py
│   │   ├── ocr_tesseract.py
│   │   └── ocr_paddleocr.py
│   ├── ai_extractor_v2.py   # Estrazione dati via Ollama (vision model)
│   └── data_validator.py    # Validazione e normalizzazione risultati
```

### Flusso di elaborazione

1. **Conversione PDF**: Ogni pagina viene convertita in PNG a 300 DPI
2. **Preprocessing immagini**: Grayscale, riduzione rumore, miglioramento contrasto, binarizzazione, correzione inclinazione
3. **Segmentazione a zone**: L'immagine viene divisa in intestazione (0-35%), corpo (25-75%) e pie' di pagina (65-100%)
4. **Fase 1 - Analisi AI**: Il modello vision analizza ogni zona per estrarre i dati
5. **Fase 2 - Documento completo**: Per i campi mancanti, analizza l'immagine intera
6. **Fase 3 - OCR + AI** (opzionale): Per i campi ancora mancanti, esegue OCR e rianalizza con supporto testuale
7. **Validazione**: Normalizzazione date, importi, verifica coerenza imponibile/IVA/totale
8. **Output Excel**: Salvataggio risultati strutturati

## Prerequisiti

- Python 3.10+
- [Ollama](https://ollama.ai/) installato e in esecuzione
- [Poppler](https://poppler.freedesktop.org/) (richiesto da `pdf2image`)

### Installazione Poppler

```bash
# macOS
brew install poppler

# Ubuntu/Debian
sudo apt-get install poppler-utils

# Windows
# Scaricare da https://github.com/oschwartz10612/poppler-windows/releases
```

### Modello Ollama

```bash
ollama pull qwen2.5vl:7b
```

## Installazione

```bash
# Clona il repository
git clone https://github.com/AleNard89/ollama_ocr_v4.git
cd ollama_ocr_v4

# Crea e attiva il virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

# Installa le dipendenze principali
pip install pandas numpy opencv-python pdf2image ollama Levenshtein Pillow

# (Opzionale) Installa un motore OCR
pip install easyocr                    # EasyOCR
pip install pytesseract                # Tesseract (richiede anche tesseract-ocr di sistema)
pip install paddlepaddle paddleocr     # PaddleOCR
```

## Utilizzo

1. Inserisci i file PDF nella cartella `invoice/` (o imposta la variabile d'ambiente `PDF_FOLDER`)
2. Configura le opzioni in `main.py`:
   - `ocr_type`: `"tesseract"`, `"easyocr"`, `"paddleocr"`, o `None` per disabilitare OCR
   - `debug_mode`: `True` per salvare output intermedi
   - `use_gpu`: `True` se disponibile una GPU compatibile
3. Esegui:

```bash
python main.py
```

Il file Excel con i risultati viene generato automaticamente nella cartella `invoice/`.

## Motori OCR supportati

| Motore | Pro | Contro |
|--------|-----|--------|
| **Nessuno** (solo AI vision) | Veloce, nessuna dipendenza extra | Meno accurato su testi piccoli |
| **Tesseract** | Leggero, ben documentato | Richiede installazione di sistema |
| **EasyOCR** | Buon supporto multilingua | Piu' lento, usa piu' memoria |
| **PaddleOCR** | Ottimo per layout complessi | Installazione piu' complessa |

## Struttura del progetto

```
ollama_ocr_v4/
├── main.py                 # Entry point
├── invoice_processor.py    # Orchestratore pipeline
├── ai_extractor_v2.py      # Estrattore AI (Ollama)
├── data_validator.py       # Validatore dati
├── image_processor.py      # Preprocessor immagini
├── pdf_processor.py        # Convertitore PDF
├── ocr_factory.py          # Factory OCR
├── ocr_EasyOCR.py          # Adapter EasyOCR
├── ocr_tesseract.py        # Adapter Tesseract
├── ocr_paddleocr.py        # Adapter PaddleOCR
├── Prompt.txt              # Prompt di riferimento per l'AI
├── req.txt                 # Dipendenze
├── invoice/                # Cartella input PDF (gitignored)
└── .gitignore
```

## Requisiti di sistema

- **RAM**: Minimo 8 GB (consigliati 16 GB per modelli vision)
- **Disco**: ~5 GB per il modello `qwen2.5vl:7b`
- **CPU/GPU**: Funziona su CPU; GPU opzionale per accelerazione OCR

## Licenza

Questo progetto e' distribuito con licenza MIT.

## Autore

Alessandro Nardelli
