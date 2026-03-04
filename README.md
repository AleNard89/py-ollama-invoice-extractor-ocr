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

I campi sono configurabili tramite `config.yaml`.

## Architettura

```
main.py                      # Entry point, CLI, config loading
├── config.yaml              # Configurazione centralizzata
├── invoice_processor.py     # Orchestratore pipeline
│   ├── pdf_processor.py         # PDF -> immagini PNG (300 DPI)
│   ├── image_processor.py       # Preprocessing (deskew, denoise, contrast, binarize)
│   ├── ocr_factory.py           # Factory pattern per motori OCR
│   │   ├── ocr_base.py              # Classe base con logica OCR condivisa
│   │   ├── ocr_EasyOCR.py           # Adapter EasyOCR
│   │   ├── ocr_tesseract.py         # Adapter Tesseract (con preservazione layout)
│   │   └── ocr_paddleocr.py         # Adapter PaddleOCR
│   ├── ai_extractor_v2.py      # Estrazione dati via Ollama (vision model)
│   └── data_validator.py       # Validazione e normalizzazione risultati
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
9. **Pulizia**: Rimozione automatica dei file temporanei (disabilitata in debug mode)

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
git clone https://github.com/AleNard89/py-ollama-invoice-extractor-ocr.git
cd py-ollama-invoice-extractor-ocr

python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate   # Windows

pip install -r requirements.txt

# (Opzionale) Installa un motore OCR
pip install easyocr                    # EasyOCR
pip install pytesseract                # Tesseract (richiede anche tesseract-ocr di sistema)
pip install paddlepaddle paddleocr     # PaddleOCR
```

## Utilizzo

### CLI

```bash
# Utilizzo base (legge da ./invoice, scrive Excel nella stessa cartella)
python main.py

# Specificare cartella input
python main.py --input /path/to/fatture

# Abilitare OCR con Tesseract
python main.py --ocr tesseract

# Debug mode (salva output intermedi, non cancella file temporanei)
python main.py --debug

# Combinare opzioni
python main.py --input ./fatture --ocr easyocr --debug --gpu

# Specificare file di configurazione custom
python main.py --config /path/to/config.yaml
```

### Opzioni CLI

| Opzione | Descrizione |
|---------|-------------|
| `-i`, `--input` | Cartella contenente i PDF (default: `./invoice`) |
| `-o`, `--output` | Percorso file Excel di output (default: auto-generato) |
| `--ocr` | Motore OCR: `easyocr`, `paddleocr`, `tesseract` (default: disabilitato) |
| `--debug` | Attiva debug mode |
| `--gpu` | Usa GPU per OCR |
| `--config` | Percorso al file `config.yaml` |

### Configurazione

Il file `config.yaml` permette di configurare tutti i parametri senza modificare il codice:

```yaml
ai:
  model: "qwen2.5vl:7b"
  temperature: 0.1

ocr:
  engine: null        # easyocr, paddleocr, tesseract, o null
  use_gpu: false

output:
  debug_mode: false

fields:
  - numero_fattura
  - data_emissione
  # ... altri campi
```

Le opzioni CLI hanno priorita' sul file di configurazione.

## Motori OCR supportati

| Motore | Pro | Contro |
|--------|-----|--------|
| **Nessuno** (solo AI vision) | Veloce, nessuna dipendenza extra | Meno accurato su testi piccoli |
| **Tesseract** | Leggero, ben documentato | Richiede installazione di sistema |
| **EasyOCR** | Buon supporto multilingua | Piu' lento, usa piu' memoria |
| **PaddleOCR** | Ottimo per layout complessi | Installazione piu' complessa |

## Requisiti di sistema

- **RAM**: Minimo 8 GB (consigliati 16 GB per modelli vision)
- **Disco**: ~5 GB per il modello `qwen2.5vl:7b`
- **CPU/GPU**: Funziona su CPU; GPU opzionale per accelerazione OCR

## Licenza

Questo progetto e' distribuito con licenza MIT.

## Autore

Alessandro Nardelli
