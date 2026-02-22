"""
File: data_validator.py
Description: Questo modulo contiene la classe DataValidator per la validazione dei dati estratti dalle fatture.
Author: Alessandro.Nardelli
Date: 2025-03-21
"""


import re
import pandas as pd

class DataValidator:
    def __init__(self, fields, debug_mode=False):
        self.fields = fields
        self.debug_mode = debug_mode
    
    def validate_results(self, results):
        validated = results.copy()
        
        # Validazione numero fattura
        if validated.get('numero_fattura') and validated['numero_fattura'] != "non trovato":
            # Rimuovi spazi e caratteri comuni non necessari
            validated['numero_fattura'] = validated['numero_fattura'].strip().replace(' ', '').replace('#', '').replace('N.', '')
        
        # Validazione data
        if validated.get('data_emissione') and validated['data_emissione'] != "non trovato":
            try:
                # Prova diversi formati di data
                formats = ["%d/%m/%Y", "%d-%m-%Y", "%Y-%m-%d", "%d.%m.%Y", "%m/%d/%Y"]
                parsed_date = None
                
                # Pulizia preliminare della data
                date_str = validated['data_emissione'].strip()
                
                # Gestione date in formato testuale italiano
                italian_months = {
                    'gennaio': '01', 'febbraio': '02', 'marzo': '03', 'aprile': '04',
                    'maggio': '05', 'giugno': '06', 'luglio': '07', 'agosto': '08',
                    'settembre': '09', 'ottobre': '10', 'novembre': '11', 'dicembre': '12'
                }
                
                for month_name, month_num in italian_months.items():
                    if month_name in date_str.lower():
                        # Estrai giorno e anno
                        day_pattern = r'(\d{1,2})\s+' + month_name
                        year_pattern = month_name + r'\s+(\d{4})'
                        
                        day_match = re.search(day_pattern, date_str.lower())
                        year_match = re.search(year_pattern, date_str.lower())
                        
                        if day_match and year_match:
                            day = day_match.group(1).zfill(2)
                            year = year_match.group(1)
                            date_str = f"{day}/{month_num}/{year}"
                            break

                # Prova i formati standard
                for fmt in formats:
                    try:
                        parsed_date = pd.to_datetime(date_str, format=fmt)
                        break
                    except:
                        continue
                
                # Se ancora non funziona, prova l'analisi più flessibile
                if not parsed_date:
                    try:
                        parsed_date = pd.to_datetime(date_str)
                    except:
                        pass
                
                if parsed_date:
                    validated['data_emissione'] = parsed_date.strftime("%d/%m/%Y")
                
            except Exception:
                pass
        
        # Validazione importi
        for field in ['importo_totale', 'imponibile', 'importo_iva']:
            if validated.get(field) and validated[field] != "non trovato":
                try:
                    # Pulisci e standardizza il valore
                    value = validated[field]
                    if isinstance(value, str):
                        # Rimuovi tutto tranne cifre, punti e virgole
                        value = ''.join(c for c in value if c.isdigit() or c in ['.', ','])
                        value = value.replace(',', '.')
                        # Assicurati che ci sia al massimo un punto decimale
                        if value.count('.') > 1:
                            parts = value.split('.')
                            value = ''.join(parts[:-1]) + '.' + parts[-1]
                        # Converti in float e arrotonda a 2 decimali
                        validated[field] = str(round(float(value), 2))
                except Exception:
                    pass
        
        # Continua dalla validazione percentuale IVA
        if validated.get('percentuale_iva') and validated['percentuale_iva'] != "non trovato":
            try:
                value = validated['percentuale_iva']
                if isinstance(value, str):
                    # Rimuovi tutto tranne cifre, punti e virgole
                    value = ''.join(c for c in value if c.isdigit() or c in ['.', ',', '%'])
                    value = value.replace(',', '.').replace('%', '')
                    # Assicurati che ci sia al massimo un punto decimale
                    if value.count('.') > 1:
                        parts = value.split('.')
                        value = ''.join(parts[:-1]) + '.' + parts[-1]
                    # Converti in float e arrotonda a 1 decimale
                    validated['percentuale_iva'] = str(round(float(value), 1))
            except Exception:
                pass

        # Verifica la coerenza tra imponibile, percentuale IVA e importo IVA
        if (validated.get('imponibile') and validated['imponibile'] != "non trovato" and
            validated.get('percentuale_iva') and validated['percentuale_iva'] != "non trovato" and
            validated.get('importo_iva') and validated['importo_iva'] != "non trovato"):
            try:
                imp = float(validated['imponibile'])
                perc = float(validated['percentuale_iva'])
                iva = float(validated['importo_iva'])
                
                # Calcola l'IVA attesa
                expected_iva = round(imp * perc / 100, 2)
                
                # Se c'è grande discrepanza, controlla quale dato potrebbe essere errato
                if abs(expected_iva - iva) > 1.0:
                    # Se l'importo totale è presente, verifica se può aiutare a determinare il valore corretto
                    if validated.get('importo_totale') and validated['importo_totale'] != "non trovato":
                        tot = float(validated['importo_totale'])
                        
                        # Verifica se tot = imp + iva
                        if abs((imp + iva) - tot) < 1.0:
                            # La somma di imponibile e IVA corrisponde al totale, mantengo i valori
                            pass
                        else:
                            # Verifica se tot = imp + expected_iva
                            if abs((imp + expected_iva) - tot) < 1.0:
                                validated['importo_iva'] = str(expected_iva)
            except Exception:
                pass
        
        # Validazione del metodo di pagamento
        if validated.get('metodo_pagamento') and validated['metodo_pagamento'] != "non trovato":
            # Normalizza i metodi di pagamento comuni
            payment_method = validated['metodo_pagamento'].lower()
            
            # Mapping di termini comuni per i metodi di pagamento
            payment_mapping = {
                'bonifico': 'Bonifico bancario',
                'bank transfer': 'Bonifico bancario',
                'iban': 'Bonifico bancario',
                'sepa': 'Bonifico bancario SEPA',
                'contanti': 'Contanti',
                'cash': 'Contanti',
                'carta': 'Carta di credito/debito',
                'card': 'Carta di credito/debito',
                'visa': 'Carta di credito/debito',
                'mastercard': 'Carta di credito/debito',
                'assegno': 'Assegno',
                'cheque': 'Assegno',
                'check': 'Assegno',
                'riba': 'Ricevuta bancaria',
                'rid': 'Addebito diretto',
                'paypal': 'PayPal'
            }
            
            # Cerca corrispondenze nel mapping
            for term, normalized in payment_mapping.items():
                if term in payment_method:
                    validated['metodo_pagamento'] = normalized
                    break
        
        #print(validated)
        return validated

