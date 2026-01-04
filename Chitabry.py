# Chitabry - Studio sulla Chitarra e sulla teoria musicale - di Gabriele Battaglia e Gemini 2.5 Pro
# Data concepimento: venerdì 7 febbraio 2020.
# 28 giugno 2024 copiato su Github
# 22 ottobre 2025, versione 4 con importante refactoring
# 27 ottobre ora usiamo music21

from time import sleep as aspetta
from scipy import signal
from collections import deque
from music21 import pitch, chord, scale, interval, harmony
from GBUtils import dgt, manuale, menu, key
from typing import Dict
from pathlib import Path
import numpy as np
import sounddevice as sd
import sys, json, re, inspect, random, threading, clitronomo, midistudy

# --- Costanti ---
VERSIONE = "4.7.0 del 4 gennaio 2026."
# --- Costanti Diteggiatura Flauto ---

_FLAUTO_INTRO = """
Benvenuto nel modulo di diteggiatura del Flauto Traverso.

Questo assistente descrive la posizione delle dita per ogni nota.
La nomenclatura usata per le chiavi è la seguente:

MANO SINISTRA (MS):
- Pollice: PS-Si (leva grande), PS-Sib (leva piccola)
- Indice: IS-Do (seconda chiave)
- Medio: MS-La (quarta chiave)
- Anulare: AS-Sol (quinta chiave)
- Mignolo: mS-Sol diesis (leva laterale)

MANO DESTRA (MD):
- Indice: ID-Fa (prima chiave principale)
- Medio: MD-Mi (seconda chiave principale)
- Anulare: AD-Re (terza chiave principale)
- Mignolo: mD-Mib (leva grande), mD-Do (leva con rullo), mD-Do diesis (leva piatta)
- Trillo: TR-1 (superiore), TR-2 (inferiore)

Inserisci la nota nel formato: OTTAVA NOTA (es. '2 FA#', '1 SIb', '3 DO')
Il segno # indica diesis, la b bemolle. Le ottave valide sono 1, 2, 3 e 4 (solo per DO e RE).
"""

# Dizionario helper per la logica di descrizione verbale.
# Associa ogni codice chiave alla sua mano e al dito principale.
_FLAUTO_NOMENCLATURA = {
    # Mano Sinistra
    'PS-Si':  {'mano': 'sinistra', 'dito': 'Pollice'},
    'PS-Sib': {'mano': 'sinistra', 'dito': 'Pollice'},
    'IS-Do':  {'mano': 'sinistra', 'dito': 'Indice'},
    'MS-La':  {'mano': 'sinistra', 'dito': 'Medio'},
    'AS-Sol': {'mano': 'sinistra', 'dito': 'Anulare'},
    'mS-Sol#':{'mano': 'sinistra', 'dito': 'Mignolo'},
    # Mano Destra
    'ID-Fa':  {'mano': 'destra', 'dito': 'Indice'},
    'MD-Mi':  {'mano': 'destra', 'dito': 'Medio'},
    'AD-Re':  {'mano': 'destra', 'dito': 'Anulare'},
    'mD-Mib': {'mano': 'destra', 'dito': 'Mignolo'},
    'mD-Do':  {'mano': 'destra', 'dito': 'Mignolo'},
    'mD-Do#': {'mano': 'destra', 'dito': 'Mignolo'},
    'TR-1':   {'mano': 'destra', 'dito': 'Trillo-1 (Indice/Medio)'}, # Dito speciale
    'TR-2':   {'mano': 'destra', 'dito': 'Trillo-2 (Indice/Medio)'}  # Dito speciale
}

# Dizionari per la conversione dell'input utente in note standard (Sharps)
_FLAUTO_MAPPE_NOTE = {
    "LATINO_STD": {
        'DO': 'C', 'DO#': 'C#', 'REb': 'C#',
        'RE': 'D', 'RE#': 'D#', 'MIb': 'D#',
        'MI': 'E', 'FA': 'F',
        'FA#': 'F#', 'SOLb': 'F#',
        'SOL': 'G', 'SOL#': 'G#', 'LAb': 'G#',
        'LA': 'A', 'LA#': 'A#', 'SIb': 'A#',
        'SI': 'B'
    },
    "ANGLO_STD": {
        'C': 'C', 'C#': 'C#', 'DB': 'C#',
        'D': 'D', 'D#': 'D#', 'EB': 'D#',
        'E': 'E', 'F': 'F',
        'F#': 'F#', 'GB': 'F#',
        'G': 'G', 'G#': 'G#', 'AB': 'G#',
        'A': 'A', 'A#': 'A#', 'BB': 'A#',
        'B': 'B'
    }
}


# La tavola di diteggiatura completa.
# La chiave è la nota in formato standard (music21)
# Il valore è un dizionario con le chiavi da premere,
# consigli (per ottava 3) e alternative.
_DITEGGIATURE_FLAUTO = {
    # --- PRIMA OTTAVA (Utente '1') ---
    'C4':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Do')},
    'C#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Do#')},
    'D4':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re')},
    'D#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Mib')},
    'E4':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'mD-Mib')},
    'F4':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'mD-Mib')},
    'F#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'AD-Re', 'mD-Mib')},
    'G4':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mD-Mib')},
    'G#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib')},
    'A4':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'mD-Mib')},
    'A#4': {'keys': ('PS-Si', 'IS-Do', 'ID-Fa', 'mD-Mib'),
            'alt': [{'keys': ('PS-Sib', 'IS-Do', 'mD-Mib'), 'desc': 'Diteggiatura alternativa comune (con leva Sib)'}]},
    'B4':  {'keys': ('PS-Si', 'IS-Do', 'mD-Mib')},

    # --- SECONDA OTTAVA (Utente '2') ---
    'C5':  {'keys': ('IS-Do', 'mD-Mib')},
    'C#5': {'keys': ('mD-Mib',)}, # "Nessuna chiave premuta, solo mD-Mib"
    'D5':  {'keys': ('PS-Si', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re')},
    'D#5': {'keys': ('PS-Si', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Mib')},
    'E5':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'mD-Mib')},
    'F5':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'mD-Mib')},
    'F#5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'AD-Re', 'mD-Mib')},
    'G5':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mD-Mib')},
    'G#5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib')},
    'A5':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'mD-Mib')},
    'A#5': {'keys': ('PS-Si', 'IS-Do', 'ID-Fa', 'mD-Mib'),
            'alt': [{'keys': ('PS-Sib', 'IS-Do', 'mD-Mib'), 'desc': 'Diteggiatura alternativa comune (con leva Sib)'}]},
    'B5':  {'keys': ('PS-Si', 'IS-Do', 'mD-Mib')},

    # --- TERZA OTTAVA (Utente '3' e '4') ---
    'C6':  {'keys': ('IS-Do', 'mD-Mib')}, # Identica a C5
    'C#6': {'keys': ('MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib'), 'consigli': "Flusso d'aria molto veloce e stretto."},
    'D6':  {'keys': ('PS-Si', 'MS-La', 'AS-Sol', 'mD-Mib'), 'consigli': 'Supporto diaframmatico intenso.'},
    'D#6': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Mib'), 'consigli': 'Molto supporto, apertura labiale minima.'},
    'E6':  {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'ID-Fa', 'MD-Mi', 'mD-Mib'), 'consigli': "Lo 'Split E' aiuta la stabilità."},
    'F6':  {'keys': ('PS-Si', 'IS-Do', 'AS-Sol', 'ID-Fa', 'mD-Mib'), 'consigli': "Dirigere l'aria leggermente più in alto."},
    'F#6': {'keys': ('PS-Si', 'IS-Do', 'AS-Sol', 'AD-Re', 'mD-Mib'), 'consigli': "Non usare il pollice Sib. Flusso d'aria molto rapido."},
    'G6':  {'keys': ('IS-Do', 'MS-La', 'AS-Sol', 'mD-Mib'), 'consigli': 'Molto stabile, mantenere il supporto.'},
    'G#6': {'keys': ('MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib'), 'consigli': 'Tende a essere crescente, rilassare l\'imboccatura.'},
    'A6':  {'keys': ('PS-Si', 'MS-La', 'ID-Fa', 'mD-Mib'), 'consigli': 'Flusso d\'aria molto focalizzato.'},
    'A#6': {'keys': ('PS-Si', 'ID-Fa', 'TR-2'), 'consigli': "Richiede precisione nell'imboccatura."},
    'B6':  {'keys': ('PS-Si', 'IS-Do', 'AS-Sol', 'TR-2'), 'consigli': 'Mantenere la gola aperta.'},
    'C7':  {'keys': ('IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'ID-Fa'), 'consigli': 'Supporto massimo.'},
    'C#7': {'keys': ('MS-La', 'mS-Sol#', 'ID-Fa', 'mD-Mib')},
    'D7':  {'keys': ('PS-Si', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'mD-Do')},
}
# --- Variabile Globale per il dizionario generato ---
SCALE_CATALOG: list[Dict] = [] # Catalogo completo (lista di dizionari)
USER_CHORD_DICT: Dict[str, str] = {}
SCALE_TYPES_DICT: Dict[str, str] = {}
FILE_IMPOSTAZIONI = "chitabry-settings.json"
archivio_modificato = False
impostazioni = {} # Conterrà l'intera configurazione caricata/default

MAINMENU = {
    "Accordi": "Gestisci le tue Tablature Accordi (salvate)",
    "Costruttore Accordi": "Analizza/Scopri le note di un accordo",
    "Flauto": "Consulta la diteggiatura del flauto traverso",
    "Metronomo": "Avvia Clitronomo",
    "MidiStudy": "Analizza e studia file MIDI",
    "Scale": "Visualizza, esercitati e gestisci le scale",
    "Impostazioni": "Configura i suoni e la notazione delle note",
    "Nota sul manico": "Trova le posizioni di una nota sul manico",
    "Trova Posizione": "Indica la nota su una corda/tasto (C.T)",
    "Guida": "Mostra la guida di Chitabry",
    "Esci": "Salva ed esci dall'applicazione"
}

# --- Motore Audio Live (per Accordi e C.T.) ---
FS = 22050 # Frequenza di campionamento (Hz)
BLOCK_SIZE = 256 # Blocchi audio
HARMONICS = [1, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.125, 0.11, 0.1, 0.09, 0.08, 0.07]
def note_to_freq(note):
    """Converte la notazione (es. "C4") in frequenza (Hz)."""
    if isinstance(note, (int, float)): return float(note)
    if isinstance(note, str):
        note_lower = note.lower()
        if note_lower == 'p': return 0.0 # Restituisce 0 per pausa
        match = re.match(r"^([a-g])([#b]?)(\d)$", note_lower)
        if not match: return 0.0 # Nota non valida
        note_letter, accidental, octave_str = match.groups()
        try: octave = int(octave_str)
        except ValueError: return 0.0
        note_base = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        semitone = note_base[note_letter]
        if accidental == '#': semitone += 1
        elif accidental == 'b': semitone -= 1
        midi_num = 12 + semitone + 12 * octave
        freq = 440.0 * (2.0 ** ((midi_num - 69) / 12.0))
        return freq
    return 0.0

#QF
def _formatta_mano_flauto(mano: str, dita: set) -> str:
    """
    Funzione helper per generare la descrizione verbale di una singola mano.
    Riceve 'sinistra' o 'destra' e un set di dita (es. {'Pollice', 'Indice'}).
    """
    # Lista ordinata delle dita per una descrizione coerente
    ordine_dita = ['Pollice', 'Indice', 'Medio', 'Anulare', 'Mignolo', 'Trillo-1 (Indice/Medio)', 'Trillo-2 (Indice/Medio)']
    
    # Filtra il set in base all'ordine
    dita_ordinate = [d for d in ordine_dita if d in dita]
    
    if not dita_ordinate:
        return f"Nessun dito della mano {mano}."

    # Casi speciali per descrizioni più naturali
    dita_principali_sx = {'Pollice', 'Indice', 'Medio', 'Anulare', 'Mignolo'}
    dita_principali_dx = {'Indice', 'Medio', 'Anulare', 'Mignolo'}

    if mano == 'sinistra' and dita == dita_principali_sx:
        return "Tutte le dita della mano sinistra."
    if mano == 'destra' and dita == dita_principali_dx:
        return "Tutte le dita della mano destra (Indice, Medio, Anulare, Mignolo)."

    # Descrizione standard
    desc = f"Mano {mano}: " + ", ".join(dita_ordinate)
    
    # Sostituzioni per chiarezza
    desc = desc.replace("Indice, Medio, Anulare, Mignolo", "tutte le dita (Indice, Medio, Anulare, Mignolo)")
    desc = desc.replace("Indice, Medio, Anulare", "Indice, Medio e Anulare")
    desc = desc.replace("Trillo-1 (Indice/Medio), Trillo-2 (Indice/Medio)", "entrambe le chiavi del trillo")
    
    return desc + "."

def _genera_descrizione_flauto(keys_tuple: tuple) -> str:
    """
    Riceve una tupla di chiavi (es. ('PS-Si', 'IS-Do', 'mD-Mib'))
    e la converte in una descrizione verbale completa.
    """
    if not keys_tuple:
        return "Nessuna chiave premuta (richiede un'imboccatura molto precisa)."
        
    dita_sinistra = set()
    dita_destra = set()
    
    # 1. Raccogli le dita usate per ogni mano
    for key_code in keys_tuple:
        if key_code in _FLAUTO_NOMENCLATURA:
            info = _FLAUTO_NOMENCLATURA[key_code]
            if info['mano'] == 'sinistra':
                dita_sinistra.add(info['dito'])
            else:
                dita_destra.add(info['dito'])

    # 2. Formatta la descrizione per ogni mano
    desc_sinistra = _formatta_mano_flauto('sinistra', dita_sinistra)
    desc_destra = _formatta_mano_flauto('destra', dita_destra)
    
    # 3. Gestione del caso speciale C#5 ("solo mignolo destro")
    if keys_tuple == ('mD-Mib',):
        return "Nessun dito della mano sinistra. Solo il Mignolo della mano destra (su Mib)."

    # 4. Gestione di tutte le dita (C4, D#4, etc.)
    tutte_le_dita_sx = {'Pollice', 'Indice', 'Medio', 'Anulare'}
    tutte_le_dita_dx = {'Indice', 'Medio', 'Anulare'}
    
    if dita_sinistra >= tutte_le_dita_sx and dita_destra >= tutte_le_dita_dx:
         desc_base = "Tutte le dita della mano sinistra e tutte le principali della destra (Indice, Medio, Anulare)"
         # Controlla cosa fa il mignolo destro
         mignolo_dx_desc = []
         if 'mD-Do' in keys_tuple: mignolo_dx_desc.append("leva Do")
         if 'mD-Do#' in keys_tuple: mignolo_dx_desc.append("leva Do#")
         if 'mD-Mib' in keys_tuple: mignolo_dx_desc.append("leva Mib")
         
         if mignolo_dx_desc:
             return desc_base + f", più il Mignolo destro (su {', '.join(mignolo_dx_desc)})."
         else:
             return desc_base + "."
    
    return desc_sinistra + "\n" + desc_destra

def GestoreFlauto():
    """
    Funzione principale per il sottomenu Flauto.
    Chiede all'utente Ottava/Nota e stampa la diteggiatura.
    """
    global impostazioni # Per leggere la nomenclatura
    
    print(_FLAUTO_INTRO)
    
    # Scegli la mappa di conversione corretta
    if impostazioni['nomenclatura'] == 'latino':
        mappa_note = _FLAUTO_MAPPE_NOTE["LATINO_STD"]
    else:
        mappa_note = _FLAUTO_MAPPE_NOTE["ANGLO_STD"]

    while True:
        # L'input rimane invariato, accetta '#'
        input_str = dgt("\nOttava e Nota (es. '2 FA#') [Invio per uscire]: ", kind="s").strip().upper()
        
        if not input_str:
            print("Ritorno al menu principale.")
            break
            
        try:
            parti = input_str.split(None, 1)
            if len(parti) != 2: raise ValueError("Formato non valido")
            
            ottava_str, nota_utente = parti # es. '2', 'FA#'
            
            # 1. Validare Ottava
            if ottava_str not in ('1', '2', '3', '4'):
                print("Errore: L'ottava deve essere 1, 2, 3 o 4.")
                continue

            # 2. Normalizzare Nota
            nota_std = mappa_note.get(nota_utente) # Cerca 'FA#'
            if nota_std is None:
                print(f"Errore: Nota '{nota_utente}' non riconosciuta.")
                continue
            
            # 3. Costruire la chiave di ricerca (es. "F#5")
            ottava_m21 = int(ottava_str) + 3
            lookup_key = f"{nota_std}{ottava_m21}" # Es. F# + 5 = "F#5"

            # 4. Cercare la diteggiatura
            diteggiatura_info = _DITEGGIATURE_FLAUTO.get(lookup_key)
            
            # 5. MODIFICA: Formatta la nota utente per la stampa
            nota_display = nota_utente.replace("#", " diesis").title()
            
            if not diteggiatura_info:
                # Usa la nota formattata nel messaggio di errore
                print(f"Diteggiatura non trovata per {nota_display} (Ottava {ottava_str}) [Chiave: {lookup_key}]")
                continue

            # 6. Generare e stampare la descrizione
            # Usa la nota formattata nel titolo
            print(f"\n--- Diteggiatura per {nota_display} (Ottava {ottava_str}) ---")
            
            descrizione = _genera_descrizione_flauto(diteggiatura_info['keys'])
            print(descrizione)
            
            if diteggiatura_info.get('consigli'):
                print(f"Consigli: {diteggiatura_info['consigli']}")
                
            # 7. Gestire e stampare alternative
            if diteggiatura_info.get('alt'):
                for i, alt in enumerate(diteggiatura_info['alt']):
                    desc_alt = _genera_descrizione_flauto(alt['keys'])
                    print(f"\n--- Alternativa {i+1} ({alt.get('desc', 'alternativa')}) ---")
                    print(desc_alt)

        except ValueError:
            # Il messaggio di errore qui è corretto, perché l'input è '#'
            print("Errore: formato non valido. Inserire OTTAVA NOTA (es. '2 FA#').")
        except Exception as e:
            print(f"Errore imprevisto: {e}")
def visualizza_note_su_manico(lista_note: list[str], maninf: int = 0, mansup: int = 21):
    """
    Funzione helper unificata per visualizzare un elenco di note sul manico.
    Riceve un elenco di note STANDARD (es. ['C', 'E', 'G']) 
    e i limiti del manico, quindi stampa il diagramma.
    """
    
    # 1. Costruisce una struttura dati {corda: [tasti...]}
    #    Questo dizionario conterrà solo le note che ci interessano.
    manico_filtrato = {
        6: [], 5: [], 4: [], 3: [], 2: [], 1: []
    }
    
    # Nota: lista_note contiene nomi base (es. 'C#', 'Bb', 'A')
    # Li mettiamo in un set per una ricerca velocissima (O(1))
    note_da_cercare = set(lista_note)

    # 2. Itera su CORDE (l'intero manico) UNA SOLA VOLTA
    for posizione, nota_std_con_ottava in CORDE.items():
        try:
            corda_str, tasto_str = posizione.split(".")
            tasto = int(tasto_str)
            
            # 3. Filtra per limiti del manico
            if not (maninf <= tasto <= mansup):
                continue
                
            # 4. Filtra per nota
            # Rimuove l'ottava dalla nota (es. "C4" -> "C")
            nota_base_std = nota_std_con_ottava[:-1] 
            
            if nota_base_std in note_da_cercare:
                corda = int(corda_str)
                # Aggiunge il tasto (come stringa) alla corda corrispondente
                manico_filtrato[corda].append(tasto_str)
                
        except ValueError:
            continue # Ignora posizioni malformate se ce ne fossero

    # 5. Stampa il risultato formattato (logica simile a Spacchetta)
    print(f"\nPosizioni sul manico (Tasti {maninf}-{mansup}):")
    
    trovate_note = False
    # Itera sulle corde dalla 6 alla 1
    for corda in range(6, 0, -1):
        tasti_trovati = manico_filtrato[corda]
        
        if tasti_trovati:
            trovate_note = True
            # Ordina i tasti numericamente (visto che sono stringhe)
            tasti_ordinati_str = " ".join(sorted(tasti_trovati, key=int))
            print(f"Corda {corda}, tasti: {tasti_ordinati_str}")

    if not trovate_note:
        print("Nessuna nota trovata in quest'area del manico.")
    
    print("-" * 30)
def fuzzy_search_and_select(search_dict: Dict, search_prompt: str, item_type: str = "elemento") -> str | None:
    """
    Esegue una ricerca fuzzy case-insensitive sui valori di un dizionario,
    mostra i risultati e chiede all'utente di selezionare.

    Args:
        search_dict: Il dizionario su cui cercare {key: display_name}.
        search_prompt: La domanda da porre all'utente per il termine di ricerca.
        item_type: Il nome del tipo di elemento cercato (es. "scala", "accordo").

    Returns:
        La chiave selezionata dall'utente, o None se annullato o non trovato.
    """
    while True:
        search_term = dgt(search_prompt, kind="s").strip().lower()
        if not search_term:
            print("Ricerca annullata.")
            return None

        # Filtra il dizionario (cerca nei VALORI, ignora case)
        # Escludi la chiave "..." o "manuale" dalla ricerca stessa
        matches = {
            key: display_name
            for key, display_name in search_dict.items()
            if key not in ["...", "manuale"] and search_term in display_name.lower()
        }

        num_matches = len(matches)

        if num_matches == 0:
            print(f"Nessun {item_type} trovato contenente '{search_term}'. Riprova o premi Invio per annullare.")
            continue # Chiedi di nuovo

        if num_matches > 20:
            print(f"Trovati troppi risultati ({num_matches} > 20). Affina la ricerca o premi Invio per annullare.")
            continue # Chiedi di nuovo

        # Mostra risultati numerati (1-20)
        print(f"\nRisultati trovati per '{search_term}':")
        match_list = list(matches.items()) # Converti in lista per indicizzazione numerica
        for i, (key, display_name) in enumerate(match_list):
            print(f" {i+1}: {display_name}")

        # Chiedi selezione numerica
        while True:
            choice_str = dgt(f"Scegli il numero (1-{num_matches}) o Invio per annullare: ", kind="s").strip()
            if not choice_str:
                print("Selezione annullata.")
                return None # Annullato dall'utente

            try:
                choice_idx = int(choice_str) - 1 # Converte in indice 0-based
                if 0 <= choice_idx < num_matches:
                    # Selezione valida, restituisci la CHIAVE corrispondente
                    selected_key, selected_name = match_list[choice_idx]
                    print(f"Selezionato: {selected_name}")
                    return selected_key # Restituisce la chiave!
                else:
                    print("Numero non valido.")
            except ValueError:
                print("Inserisci un numero.")
            # Se l'input non era valido, il loop while interno ripete la richiesta del numero

def setup_note_constants():
    """Crea le costanti per le note e i dizionari di conversione."""
    NOTE_STD = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
    NOTE_LATINE = ['DO', 'DO#', 'RE', 'RE#', 'MI', 'FA', 'FA#', 'SOL', 'SOL#', 'LA', 'LA#', 'SI']
    NOTE_ANGLO = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

    STD_TO_LATINO = dict(zip(NOTE_STD, NOTE_LATINE))
    STD_TO_ANGLO = dict(zip(NOTE_STD, NOTE_ANGLO))
    STD_TO_LATINO.update({
        'Db': 'REb', 'Eb': 'MIb', 'Gb': 'SOLb', 'Ab': 'LAb', 'Bb': 'SIb'
    })
    STD_TO_ANGLO.update({
        'Db': 'Db', 'Eb': 'Eb', 'Gb': 'Gb', 'Ab': 'Ab', 'Bb': 'Bb'
    })
    
    return NOTE_STD, NOTE_LATINE, NOTE_ANGLO, STD_TO_LATINO, STD_TO_ANGLO

def build_fretboard_data(NOTE_STD):
    """Costruisce i dizionari che rappresentano il manico della chitarra."""
    SCALACROMATICA_STD = {}
    i = 0
    for j in range(0, 8):
        for nota in NOTE_STD:
            i += 1
            SCALACROMATICA_STD[i] = nota + str(j)

    CAPOTASTI = {}
    i = 6
    for j in [29, 34, 39, 44, 48, 53]:
        CAPOTASTI[i] = j
        i -= 1

    CORDE = {}
    for corda in range(6, 0, -1):
        for tasto in range(CAPOTASTI[corda], CAPOTASTI[corda] + 22):
            CORDE[str(corda) + "." + str(tasto - CAPOTASTI[corda])] = SCALACROMATICA_STD[tasto]
            
    return SCALACROMATICA_STD, CAPOTASTI, CORDE

NOTE_STD, NOTE_LATINE, NOTE_ANGLO, STD_TO_LATINO, STD_TO_ANGLO = setup_note_constants()
SCALACROMATICA_STD, CAPOTASTI, CORDE = build_fretboard_data(NOTE_STD)

# --- Funzioni per generare dizionari da music21 (da chiamare una volta all'avvio) ---

class ScaleException(Exception):
    """Classe base per errori relativi alle scale in questo modulo."""
    pass

class InvalidUSIFormatError(ScaleException):
    """Sollevata quando una stringa USI non è nel formato atteso."""
    def __init__(self, usi_string):
        message = (
            f"La stringa USI '{usi_string}' non è valida. "
            "Il formato atteso è 'paradigm:tonic:scale_id'."
        )
        super().__init__(message)
class UnknownScaleError(ScaleException):
    """Sollevata quando uno scale_id non può essere trovato o istanziato."""
    def __init__(self, paradigm, scale_id):
        message = (
            f"Impossibile trovare/istanziare la scala con id '{scale_id}' "
            f"per il paradigma '{paradigm}'."
        )
        super().__init__(message)

# --- Funzioni Helper per Introspezione (dal documento) ---

def _find_scale_subclasses(base_class):
    """
    Funzione helper ricorsiva per trovare tutte le sottoclassi
    ConcreteScale valide, escludendo il modulo key.
    """
    found_classes = set()
    try:
        subclasses = base_class.__subclasses__()
    except TypeError:
        subclasses = []

    for subclass in subclasses:
        if subclass.__module__.startswith('music21.key'):
            continue
        if not inspect.isabstract(subclass) and issubclass(subclass, scale.ConcreteScale):
            found_classes.add(subclass)
        found_classes.update(_find_scale_subclasses(subclass))
    return found_classes

def _format_friendly_name(programmatic_id, paradigm):
    """Helper per creare nomi leggibili."""
    name = programmatic_id
    if paradigm == 'concrete':
        if name.endswith('Scale'):
            name = name[:-5]
        # Modifica suggerita per inserire spazi: usa regex
        name = re.sub(r'(?<!^)(?=[A-Z])', ' ', name).title()
    elif paradigm == 'scala':
        name = ' '.join(a.capitalize() for a in name.split('_'))
    return name.strip()

def get_user_chord_dictionary() -> Dict[str, str]:
    """
    Esegue l'introspezione di music21.harmony per costruire un
    dizionario pulito di tipi di accordi per l'interfaccia utente.

    Ritorna:
        Dict[str, str]: Un dizionario dove la chiave è
        l'abbreviazione (shorthand) primaria usata per la costruzione
        e il valore è il nome leggibile per il menu.
    """
    user_dict = {}
    processed_types = set() # Per evitare duplicati dovuti a shorthand non unici

    # Itera sull'elenco master dei tipi di accordo canonici
    for chord_type in harmony.CHORD_TYPES:

        # Salta tipi già processati (se getCurrentAbbreviationFor non è univoco)
        if chord_type in processed_types:
            continue

        # 1. Ottiene l'abbreviazione "preferita" dalla libreria -> CHIAVE
        primary_shorthand = harmony.getCurrentAbbreviationFor(chord_type)

        # Evita di sovrascrivere una chiave già assegnata (es. '' per major)
        # Diamo priorità alla prima assegnazione trovata (che di solito è quella corretta)
        if primary_shorthand in user_dict:
             continue

        # 2. Pulisce il nome canonico per la visualizzazione -> VALORE
        readable_name = chord_type.replace('-', ' ').title()

        # Correzioni specifiche per leggibilità
        if primary_shorthand == '' and chord_type == 'major':
            readable_name = 'Major' # Triade Maggiore
        elif primary_shorthand == 'm' and chord_type == 'minor':
            readable_name = 'Minor' # Triade Minore
        elif primary_shorthand == 'dim' and chord_type == 'diminished':
            readable_name = 'Diminished' # Triade Diminuita
        elif primary_shorthand == 'aug' and chord_type == 'augmented':
            readable_name = 'Augmented' # Triade Aumentata
        elif primary_shorthand == 'm7b5':
             readable_name = 'Half-Diminished (m7b5)' # Più chiaro
        elif chord_type == 'power':
             readable_name = 'Power Chord (5)'
        # Aggiungi altre correzioni se necessario per migliorare la leggibilità

        user_dict[primary_shorthand] = readable_name
        processed_types.add(chord_type) # Segna il tipo canonico come processato


    # --- MODIFICA CHIAVE ---
    # Ordina il dizionario principale PER VALORE (nome leggibile)
    sorted_dict = dict(sorted(user_dict.items(), key=lambda item: item[1]))

    # Aggiungi l'opzione di ricerca fuzzy ALLA FINE con la chiave '...'
    sorted_dict["..."] = ">> Cerca tipo di accordo..."
    # --- FINE MODIFICA CHIAVE ---

    return sorted_dict
def build_scale_catalog() -> list[Dict]:
    """
    Esegue l'introspezione di music21 per costruire un dizionario
    unificato di tutte le scale disponibili (Concrete e Scala).

    Restituisce:
        list[dict]: Un elenco di dizionari, ognuno
                    rappresentante una scala.
    """
    catalog = []
    processed_ids = set() # Per evitare ID duplicati

    # --- Paradigma 1: Sottoclassi ConcreteScale ---
    print("   Analisi classi ConcreteScale...")
    try:
        # Usiamo scale.Scale come base per la ricorsione iniziale,
        # _find_scale_subclasses filtrerà per ConcreteScale e non astratte.
        concrete_classes = _find_scale_subclasses(scale.Scale)

        for cls in sorted(list(concrete_classes), key=lambda x: x.__name__):
            prog_id = cls.__name__
            if prog_id not in processed_ids:
                catalog.append({
                    'programmatic_id': prog_id,
                    'friendly_name': _format_friendly_name(prog_id, 'concrete'),
                    'paradigm': 'concrete'
                    # 'class': cls # Rimosso per semplicità
                })
                processed_ids.add(prog_id)
    except Exception as e:
         print(f"Attenzione: Errore durante introspezione classi ConcreteScale: {e}")

    # --- Paradigma 2: Archivio ScalaScale ---
    print("   Analisi archivio Scala (.scl)...")
    try:
        scala_paths = scale.scala.getPaths()

        # Ordina in modo robusto
        def get_sort_key(p):
            try: return Path(p).stem.lower()
            except Exception: return str(p).lower()
        sorted_scala_paths = sorted(scala_paths, key=get_sort_key)

        for scl_path_obj in sorted_scala_paths:
            try:
                scl_path = Path(scl_path_obj) # Assicura sia Path
                prog_id = scl_path.stem
                filename_scl = scl_path.name

                if prog_id not in processed_ids and scl_path.is_file():
                    friendly_name_raw = _format_friendly_name(prog_id, 'scala')
                    description = friendly_name_raw
                    try:
                         scale_info_data = scale.scala.getScaleInfo(filename_scl)
                         description = scale_info_data.get('description', friendly_name_raw)
                    except Exception: pass # Ignora errori lettura descrizione

                    catalog.append({
                        'programmatic_id': prog_id,
                        'friendly_name': description if description else friendly_name_raw,
                        'paradigm': 'scala'
                        # 'class': scale.scala.ScalaScale # Rimosso per semplicità
                    })
                    processed_ids.add(prog_id)
            except Exception as path_error:
                 print(f"Attenzione: Errore nell'elaborare il percorso Scala '{scl_path_obj}': {path_error}")

    except ImportError: print("Attenzione: Modulo 'scala.scala' non trovato.")
    except AttributeError: print("Attenzione: Funzione 'getPaths' non trovata in scala.scala.")
    except Exception as e: print(f"Attenzione: Impossibile caricare l'archivio Scala. {e}")

    # Ordina catalogo finale
    catalog.sort(key=lambda x: x.get('friendly_name', '').lower())

    print(f"   ...Catalogo scale costruito con {len(catalog)} voci.")
    return catalog

def get_scale_from_usi(usi_string: str) -> scale.Scale:
    """
    Analizza un Identificatore di Scala Univoco (USI) e
    restituisce un'istanza di music21.scale.Scale.
    (Basato sulla Sezione 4.2 del documento)
    """
    try:
        parts = usi_string.split(':', 2)
        if len(parts) != 3: raise ValueError("Formato non valido")
        paradigm, tonic_str, scale_id = parts
    except ValueError:
        raise InvalidUSIFormatError(usi_string)

    try:
        tonic_pitch = pitch.Pitch(tonic_str)
    except Exception as e:
        raise ScaleException(f"Tonica non valida '{tonic_str}': {e}")

    # --- Routing del Paradigma ---
    if paradigm == 'concrete':
        try:
            scale_class = getattr(scale, scale_id) # Recupera classe da music21.scale
            # Istanzia passando solo la tonica
            return scale_class(tonic_pitch)
        except AttributeError:
            raise UnknownScaleError(paradigm, scale_id)
        except Exception as e:
            raise ScaleException(f"Errore istanziazione {scale_id}({tonic_str}): {e}")

    elif paradigm == 'scala':
        scl_filename = scale_id + ".scl"
        try:
            # Istanzia ScalaScale (accedendo da scale, come corretto prima)
            return scale.ScalaScale(tonic_pitch, scl_filename)
        except FileNotFoundError:
             raise UnknownScaleError(paradigm, f"File {scl_filename} non trovato.")
        except AttributeError: # Se scale.ScalaScale non esiste
             raise ScaleException("Classe ScalaScale non trovata.")
        except Exception as e:
            raise ScaleException(f"Errore istanziazione ScalaScale('{tonic_str}', '{scl_filename}'): {e}")

    elif paradigm == 'custom':
        try:
            pitch_list_str = scale_id.split(',')
            pitch_list = [pitch.Pitch(p.strip()) for p in pitch_list_str if p.strip()]
            if not pitch_list: raise ValueError("Lista pitch vuota")
            # Istanzia ConcreteScale con pitches e tonic
            return scale.ConcreteScale(pitches=pitch_list, tonic=tonic_pitch)
        except Exception as e:
            raise ScaleException(f"Errore parsing/creazione scala 'custom' da '{scale_id}': {e}")

    else:
        raise ScaleException(f"Paradigma USI sconosciuto: '{paradigm}'")

#QF
def _generate_harmonic_pluck(buffer_length_N, pluck_hardness_float):
    """
    Genera un "pluck" di eccitazione ibrido basato sulla sintesi additiva
    dalla Tabella 1, lungo N campioni, scolpito dalla durezza.
    
    Questo sostituisce il metodo a rumore filtrato, che è inaffidabile
    alle basse frequenze.
    """
    N = buffer_length_N
    t = np.linspace(0., 1., N, endpoint=False) # Genera 1 ciclo di base
    
    # Dati dalla Tabella 1 (Amplitudini base normalizzate)
    # n = 1,  2,    3,    4,    5,    6,    7,    8,    9,   10
    base_amplitudes = np.array([
        1.00, 0.15, 0.34, 0.30, 0.09, 0.03, 0.08, 0.03, 0.06, 0.04
    ])
    
    # Usa pluck_hardness (0.1 morbido, 0.9 duro) per "scolpire" queste armoniche.
    # Un plettro morbido (0.1) attenua molto le armoniche alte.
    # Un plettro duro (0.9) le attenua poco.
    
    # Convertiamo [0.1, 0.9] in un fattore di attenuazione
    # 0.1 -> 1.0 (attenuazione alta)
    # 0.9 -> 0.1 (attenuazione bassa)
    roll_off_strength = 1.0 - pluck_hardness_float 
    
    # Creiamo un array scalare: [1.0, strength, strength^2, strength^3, ...]
    n = np.arange(0, len(base_amplitudes))
    hardness_scalar = np.power(roll_off_strength, n)
    
    # Applichiamo la durezza alle ampiezze base
    amplitudes = base_amplitudes * hardness_scalar
    
    waveform = np.zeros(N, dtype=np.float32)
    
    # Costruiamo il ciclo d'onda sommando le armoniche
    for i in range(len(amplitudes)):
        n_harmonic = i + 1
        if amplitudes[i] > 0.001: # Ottimizzazione: salta armoniche troppo deboli
            phase = 2 * np.pi * n_harmonic * t
            waveform += amplitudes[i] * np.sin(phase)
            
    # Rimuovi DC offset (molto importante)
    waveform -= np.mean(waveform)
    
    # Normalizza il pluck finale
    max_val = np.max(np.abs(waveform))
    if max_val > 0:
        waveform /= max_val
        
    return waveform

def _generate_filtered_pluck_burst(buffer_length_N, sample_rate, pluck_hardness=0.5):
    """
    Genera un burst di rumore filtrato realistico per l'eccitazione KS.
    (Versione corretta con rimozione DC offset)
    """
    # Normalizza l'hardness in un range fisico
    pluck_hardness = np.clip(pluck_hardness, 0.1, 0.9)
    noise = np.random.normal(0, 0.5, buffer_length_N)
    
    # Mappa hardness a frequenza di cutoff
    cutoff_freq = 1000 + (pluck_hardness * 9000)
    nyquist = 0.5 * sample_rate
    if cutoff_freq >= nyquist:  
        cutoff_freq = nyquist - 1
        
    b, a = signal.butter(2, cutoff_freq / nyquist, btype='low')
    filtered_noise = signal.lfilter(b, a, noise)
    
    decay = np.exp(-np.linspace(0, 5, buffer_length_N))
    
    burst = (filtered_noise * decay).astype(np.float32)
    
    # --- INIZIO CORREZIONE ---
    # 1. Rimuovi qualsiasi DC offset dal burst
    burst -= np.mean(burst)
    
    # 2. Normalizza di nuovo dopo la rimozione del DC
    max_abs = np.max(np.abs(burst))
    if max_abs > 0:
        burst /= max_abs
    # --- FINE CORREZIONE ---
        
    return burst

class NoteRenderer:
    """
    Gestisce il rendering "one-shot" di una singola nota.
    Usa l'algoritmo Karplus-Strong per suoni di chitarra (suono_1)
    o la sintesi additiva standard per altri suoni (suono_2).
    """
    def __init__(self, fs=FS):
        self.fs = fs
        self.freq = 0.0
        self.vol = 0.0
        self.dur = 0
        self.pan_l, self.pan_r = 0.707, 0.707
        
        # Parametri legacy (per suono_2)
        self.adsr_list = [0, 0, 0, 0]
        self.kind = 0
        
        # Nuovi parametri (per suono_1)
        self.pluck_hardness = 0.0
        self.damping_factor = 0.0

    # QUESTA è la firma corretta che accetta **kwargs
    def set_params(self, freq, dur, vol, pan, **kwargs):
        """
        Memorizza i parametri per il rendering.
        kwargs può contenere parametri legacy (adsr_list, kind)
        o nuovi parametri (pluck_hardness, damping_factor).
        """
        self.freq = freq
        self.dur = dur
        self.vol = vol
        
        # Impostazioni Panning
        pan_clipped = np.clip(pan, -1.0, 1.0)
        pan_angle = pan_clipped * (np.pi / 4.0)
        self.pan_l = np.cos(pan_angle + np.pi / 4.0)
        self.pan_r = np.sin(pan_angle + np.pi / 4.0)
        
        # Resetta i flag
        self.kind = 0
        self.pluck_hardness = 0.0
        
        # Controlla quali parametri sono stati passati
        if 'kind' in kwargs: # Chiamata Legacy (suono_2)
            self.adsr_list = kwargs.get('adsr_list', [0,0,0,0])
            self.kind = kwargs.get('kind', 1)
        elif 'pluck_hardness' in kwargs: # Chiamata Karplus-Strong (suono_1)
            self.pluck_hardness = kwargs.get('pluck_hardness', 0.5)
            self.damping_factor = kwargs.get('damping_factor', 0.996)
        else:
            # Fallback se kwargs è vuoto (improbabile)
            self.kind = 1 

    def _render_karplus_strong(self, n_samples):
        """
        Implementazione avanzata di Karplus-Strong (Snippet 5).
        """
        # 1. Calcola la lunghezza del buffer
        N = int(self.fs / self.freq)
        if N <= 1:
            return np.zeros(n_samples, dtype=np.float32) # Freq troppo alta
            
        # 2. Eccitazione (Usando il Blocco Helper 1)
        pluck = _generate_harmonic_pluck(N, self.pluck_hardness)
        buf = deque(pluck)
        
        samples = np.zeros(n_samples, dtype=np.float32)
        
        for i in range(n_samples):
            # 3. Lettura del campione
            samples[i] = buf[0]
            
            # 4. Filtro di Loop (KS Classico)
            # Leggiamo i primi due campioni per l'averaging
            avg = self.damping_factor * 0.5 * (buf[0] + buf[1])
            
            # 5. Feedback
            buf.append(avg)
            buf.popleft() # Mantiene la lunghezza N
            
        return samples

    def _render_legacy_osc(self, n_samples):
        """
        Oscillatori semplici (il vecchio _get_wave_vector)
        e inviluppo ADSR (la vecchia logica di render).
        """
        # 1. Genera onda base (Logica dal vecchio _get_wave_vector)
        t = np.linspace(0., n_samples / self.fs, n_samples, endpoint=False)
        phase_vector = 2 * np.pi * self.freq * t
        
        if self.kind == 2: wave = signal.square(phase_vector)
        elif self.kind == 3: wave = signal.sawtooth(phase_vector, 0.5)
        elif self.kind == 4: wave = signal.sawtooth(phase_vector)
        elif self.kind == 5:
            wave = np.zeros(n_samples, dtype=np.float32)
            for i, h_amp in enumerate(HARMONICS):
                wave += np.sin((i + 1) * phase_vector) * h_amp
            max_val = np.max(np.abs(wave))
            if max_val > 0: wave /= max_val
        else: # kind 1 (default)
            wave = np.sin(phase_vector)
        
        wave = wave.astype(np.float32)
        
        # 2. Applica inviluppo ADSR (Logica dal vecchio render())
        a_pct, d_pct, s_level_pct, r_pct = self.adsr_list
        attack_frac = a_pct / 100.0
        decay_frac = d_pct / 100.0
        sustain_level = s_level_pct / 100.0
        release_frac = r_pct / 100.0
        
        attack_samples = int(round(attack_frac * n_samples))
        decay_samples = int(round(decay_frac * n_samples))
        release_samples = int(round(release_frac * n_samples))
        
        sustain_samples = n_samples - (attack_samples + decay_samples + release_samples)
        if sustain_samples < 0:
            release_samples += sustain_samples
            sustain_samples = 0
            release_samples = max(0, release_samples)

        envelope = np.zeros(n_samples, dtype=np.float32)
        current_pos = 0

        if attack_samples > 0:
            attack_samples = min(attack_samples, n_samples - current_pos)
            envelope[current_pos : current_pos + attack_samples] = np.linspace(0., 1., attack_samples, dtype=np.float32)
            current_pos += attack_samples
        
        if decay_samples > 0:
            decay_samples = min(decay_samples, n_samples - current_pos)
            envelope[current_pos : current_pos + decay_samples] = np.linspace(1., sustain_level, decay_samples, dtype=np.float32)
            current_pos += decay_samples
        
        if sustain_samples > 0:
            sustain_samples = min(sustain_samples, n_samples - current_pos)
            envelope[current_pos : current_pos + sustain_samples] = sustain_level
            current_pos += sustain_samples
        
        if release_samples > 0:
            release_samples = min(release_samples, n_samples - current_pos)
            if release_samples > 0:
                envelope[current_pos : current_pos + release_samples] = np.linspace(sustain_level, 0., release_samples, dtype=np.float32)

        wave *= envelope
        return wave

    def render(self):
        """
        Pre-calcola l'intera nota (onda + envelope) e 
        RESTITUISCE l'array stereo.
        """
        empty_array = np.array([], dtype=np.float32)

        if self.freq <= 0.0:
            return empty_array

        total_note_samples = int(round(self.dur * self.fs))
        if total_note_samples == 0:
            return empty_array
            
        # --- ROUTING LOGIC ---
        # Se pluck_hardness è stato impostato, usa KS (suono_1)
        if self.pluck_hardness > 0:
            wave = self._render_karplus_strong(total_note_samples)
            # Nota: KS ha già il suo inviluppo, quindi non applichiamo ADSR
        else:
            # Altrimenti, usa il vecchio metodo (per suono_2)
            wave = self._render_legacy_osc(total_note_samples)
            
        # Applica volume e panning
        wave *= self.vol
        
        stereo_segment = np.zeros((total_note_samples, 2), dtype=np.float32)
        stereo_segment[:, 0] = wave * self.pan_l
        stereo_segment[:, 1] = wave * self.pan_r
        
        return stereo_segment
# --- Fine Motore Audio Live ---

def get_impostazioni_default():
    """Restituisce la struttura dati di default per un nuovo file JSON."""
    return {
        "nomenclatura": "latino",
        "default_bpm": 60,
        "suono_1": {
            "descrizione": "Suono per accordi (Karplus-Strong Pluck)",
            "pluck_hardness": 0.2,    # Range 0.1 (morbido) - 0.9 (brillante)
            "damping_factor": 0.998,  # Range 0.990 (corto) - 0.999 (lungo)
            "dur_accordi": 9.0,   
            "volume": 0.45
        },
        "suono_2": {
            "descrizione": "Suono per scale (simil-flauto)",
            "kind": 1,
            "adsr": [2.0, 1.0, 90.0, 2.0],
            "volume": 0.35
        },
        "chordpedia": {},
    }
def carica_impostazioni():
    """Carica le impostazioni da FILE_IMPOSTAZIONI.
    Se il file non esiste, lo crea con i valori di default.
    Gestisce anche l'aggiornamento di file vecchi.
    """
    global impostazioni, archivio_modificato
    try:
        with open(FILE_IMPOSTAZIONI, 'r', encoding='utf-8') as f:
            impostazioni = json.load(f)
        print(f"File di impostazioni '{FILE_IMPOSTAZIONI}' caricato.")
        
        # --- Controllo di migrazione (FIX per KeyError: 'volume' E 'bpm') ---
        migrazione_necessaria = False
        
        if 'volume' not in impostazioni.get('suono_1', {}):
            print("Aggiornamento 'suono_1': aggiunta chiave 'volume' di default.")
            if 'suono_1' not in impostazioni: 
                impostazioni['suono_1'] = {} # Sicurezza
            impostazioni['suono_1']['volume'] = 0.35
            migrazione_necessaria = True
            
        if 'volume' not in impostazioni.get('suono_2', {}):
            print("Aggiornamento 'suono_2': aggiunta chiave 'volume' di default.")
            if 'suono_2' not in impostazioni: 
                impostazioni['suono_2'] = {} # Sicurezza
            impostazioni['suono_2']['volume'] = 0.35
            migrazione_necessaria = True

        # --- Aggiunta controllo 'default_bpm' ---
        if 'default_bpm' not in impostazioni:
            print("Aggiornamento impostazioni: aggiunta chiave 'default_bpm'.")
            impostazioni['default_bpm'] = 60
            migrazione_necessaria = True
        
        if migrazione_necessaria:
            archivio_modificato = True
            print("Impostazioni aggiornate alla nuova versione.")
        # --- Fine controllo di migrazione ---
        
    except FileNotFoundError:
        print(f"File '{FILE_IMPOSTAZIONI}' non trovato. Ne creo uno nuovo con i valori di default.")
        impostazioni = get_impostazioni_default()
        archivio_modificato = True 
        salva_impostazioni() # Salviamo subito il file creato
    except json.JSONDecodeError:
        print(f"Errore: Il file '{FILE_IMPOSTAZIONI}' è corrotto o malformato.")
        print("Uscita dall'applicazione.")
        sys.exit(1)
    except Exception as e:
        print(f"Errore imprevisto during il caricamento delle impostazioni: {e}")
        sys.exit(1)
def salva_impostazioni():
    """Salva il dizionario 'impostazioni' nel file JSON."""
    global archivio_modificato
    if not archivio_modificato:
        print("\nNessuna modifica alle impostazioni. Salvataggio non necessario.")
        return
        
    try:
        with open(FILE_IMPOSTAZIONI, 'w', encoding='utf-8') as f:
            json.dump(impostazioni, f, indent=4, ensure_ascii=False)
        print(f"\nImpostazioni salvate con successo in '{FILE_IMPOSTAZIONI}'.")
        archivio_modificato = False
    except IOError as e:
        print(f"\nErrore: Impossibile salvare il file di impostazioni: {e}")
    except Exception as e:
        print(f"\nErrore imprevisto durante il salvataggio: {e}")

# --- Funzioni Helper (Fase 1) ---

def get_nota(nota_std_music21):
    """
    Converte una nota standard (es. "C#4", "Eb", "G~5", "A``")
    nella notazione scelta dall'utente (latina o anglosassone),
    preservando i simboli microtonali (~, `` , ~~, ``` ``) alla fine.
    """
    if not isinstance(nota_std_music21, str):
        return str(nota_std_music21) # Restituisci come stringa se non è una stringa

    # Mappa di conversione base
    if impostazioni['nomenclatura'] == 'latino':
        mappa = STD_TO_LATINO
    else:
        mappa = STD_TO_ANGLO

    # Estrai ottava e simboli microtonali (se presenti) alla fine della stringa
    ottava = ""
    micro_suffix = ""
    base_name_std = nota_std_music21

    # Estrai ottava (se presente)
    if base_name_std and base_name_std[-1].isdigit():
        ottava = base_name_std[-1]
        base_name_std = base_name_std[:-1]

    # Estrai simboli microtonali (~, ``, ~~, ``` ``) alla fine
    possible_micros = ["~~", "``", "~", "`"] # Ordina dal più lungo al più corto
    for micro in possible_micros:
        if base_name_std.endswith(micro):
            micro_suffix = micro
            base_name_std = base_name_std[:-len(micro)] # Rimuovi il suffisso
            break # Trovato il suffisso più lungo

    # Ora base_name_std contiene solo la nota e l'alterazione standard (es. "C#", "Eb", "G")
    # Traduci la parte standard
    nome_tradotto = mappa.get(base_name_std, base_name_std) # Usa originale se non in mappa

    # Ricomponi la stringa finale
    return nome_tradotto + micro_suffix + ottava
# --- Funzioni Audio (Fase 3) ---
def Suona(tablatura):
    """
    Permette l'ascolto interattivo di una tablatura.
    Usa il motore 'pre-calcolato' (classe NoteRenderer) e sd.play().
    """
    print("\nAscolta le corde:")
    print("Tasti da 1 a 6, (A) pennata in levare, (Q) pennata in battere")
    print("ESC per uscire.")
    
    #Q rimuovi i parametri non usati
    suono_1 = impostazioni['suono_1']
    hardness = suono_1.get('pluck_hardness', 0.6)
    damping = suono_1.get('damping_factor', 0.997)
    dur = suono_1['dur_accordi']
    vol = suono_1['volume']
    
    renderers = [NoteRenderer(fs=FS) for _ in range(6)]
    note_da_suonare = [] # Lista di booleani (se la corda suona)
    note_freq = [] # Lista delle frequenze
    note_pan = [] # Lista dei pan

    # Pre-configura i parametri
    for i in range(6): # i da 0 a 5 (corda 6 a 1)
        corda = 6 - i
        tasto = tablatura[i]
        pan_val = 0.8 - (i * 0.32) 
        note_pan.append(pan_val)
        
        freq = 0.0
        if tasto.isdigit() and f"{corda}.{tasto}" in CORDE:
            nota_std = CORDE[f"{corda}.{tasto}"]
            freq = note_to_freq(nota_std)
        
        note_freq.append(freq)
        note_da_suonare.append(freq > 0) 
        
        # Imposta i parametri per questo renderer
        renderers[i].set_params(freq, dur, vol, pan_val, 
                                pluck_hardness=hardness, 
                                damping_factor=damping)
    note_prompt_str = get_note_da_tablatura(tablatura)
    while True:
        print(f"Note: {note_prompt_str}): ",end="\r",flush=True)
        scelta = key().lower()
        
        if scelta.isdigit() and scelta in '123456':
            corda_idx_py = 5 - (int(scelta) - 1)
            if note_da_suonare[corda_idx_py]:
                # --- MODIFICA CHIAVE ---
                # Renderizza la nota ORA
                note_audio = renderers[corda_idx_py].render()
                if note_audio.size > 0:
                    sd.play(note_audio, samplerate=FS, blocking=False)
                    
        elif scelta == chr(27): # ESC
            print("Uscita dal menù ascolto.")
            sd.stop() 
            break 
            
        elif scelta == 'a' or scelta == 'q': # Pennata
            sd.stop() 
            strum_delay_sec = 0.07
            strum_delay_samples = int(strum_delay_sec * FS)
            note_duration_samples = int(dur * FS)
            
            total_samples = note_duration_samples + (5 * strum_delay_samples)
            mix_buffer = np.zeros((total_samples, 2), dtype=np.float32)

            note_order = range(6) if scelta == 'q' else range(5, -1, -1)
            
            current_delay_samples = 0
            for i in note_order:
                if note_da_suonare[i]:
                    # Imposta i parametri corretti (necessario se cambiassero)
                    renderers[i].set_params(note_freq[i], dur, vol, note_pan[i], 
                                            pluck_hardness=hardness, 
                                            damping_factor=damping)                    
                    note_data = renderers[i].render() 
                    if len(note_data) > note_duration_samples:
                        note_data = note_data[:note_duration_samples]
                    
                    start_pos = current_delay_samples
                    end_pos = start_pos + len(note_data)
                    
                    if end_pos > total_samples:
                        end_pos = total_samples
                        note_data = note_data[:(end_pos - start_pos)]
                        
                    mix_buffer[start_pos:end_pos] += note_data
                
                current_delay_samples += strum_delay_samples
            
            max_val = np.max(np.abs(mix_buffer))
            if max_val > 1.0:
                mix_buffer /= max_val
            
            sd.play(mix_buffer, samplerate=FS, blocking=False)
            
        else:
            print("Comando non valido. Premi 1-6, A, Q o ESC.")
    return
def SuonaAccordoTeorico(note_pitch_list):
    """
    Player audio per accordi teorici generati da CostruttoreAccordi.
    Gestisce fino a 10 note, ordina per altezza, assegna panning
    (grave=dx, acuto=sx) e mappa i tasti 1-0.
    """
    if not note_pitch_list:
        print("Nessuna nota da suonare.")
        return

    # 1. Ordina le note dalla più grave alla più acuta
    try:
        sorted_pitches = sorted(note_pitch_list, key=lambda p: p.frequency if p and p.frequency is not None else float('inf'))
    except Exception as e:
        print(f"Errore durante l'ordinamento delle note: {e}")
        # Fallback: prova a usare l'ordinamento predefinito se la frequenza fallisce
        try:
            sorted_pitches = sorted(note_pitch_list)
        except:
             print("Impossibile ordinare le note.")
             return


    # 2. Limita a un massimo di 10 note
    if len(sorted_pitches) > 10:
        print(f"Attenzione: L'accordo ha {len(sorted_pitches)} note. Suono solo le 10 più gravi.")
        pitches_to_play = sorted_pitches[:10]
    else:
        pitches_to_play = sorted_pitches
        
    num_notes = len(pitches_to_play)

    # 3. Prepara parametri audio (da suono_1)
    suono_1 = impostazioni['suono_1']
    kind = suono_1['kind']
    adsr_list = suono_1['adsr']
    dur = suono_1['dur_accordi']
    vol = suono_1['volume']
    hardness = suono_1.get('pluck_hardness', 0.6)
    damping = suono_1.get('damping_factor', 0.997)

    # 4. Calcola Panning (Grave=+0.8 -> Acuto=-0.8)
    pan_values = []
    if num_notes == 1:
        pan_values.append(0.0) # Centro se una sola nota
    elif num_notes > 1:
        pan_step = 1.6 / (num_notes - 1) # Range totale 1.6
        for i in range(num_notes):
            pan = -0.8 + (i * pan_step) # Parte da -0.8 (sx) per la nota più grave (i=0)
            pan_values.append(np.clip(pan, -0.8, 0.8))
    # 5. Mappa tasti 1..9, 0 (MODIFICATO: 1=Grave, 0=Acuta)
    # Segue il layout della tastiera: 1, 2, 3...0
    key_map = {str(i+1): i for i in range(min(num_notes, 9))} # Tasti '1' a '9' -> indici 0 a 8
    if num_notes >= 10:
        key_map['0'] = 9 # Tasto '0' -> indice 9 (decima nota)            key_map[tasto_char] = target_index
    # 6. Prepara Renderers e dati note
    renderers = [NoteRenderer(fs=FS) for _ in range(num_notes)]
    note_freqs = []
    note_names_display = []
    
    print("\n--- Player Accordo Teorico ---")
    print(f"Suono {num_notes} note (ordinate dalla più grave alla più acuta):")

    for i, p in enumerate(pitches_to_play):
        freq = p.frequency if p and p.frequency is not None else 0.0
        note_freqs.append(freq)
        
        # Nome nota per display (con ottava)
        nota_display = get_nota(p.nameWithOctave.replace('-', 'b')) if p else "N/A"
        note_names_display.append(nota_display)
        
        # Configura il renderer
        pan_val = pan_values[i]
        renderers[i].set_params(freq, dur, vol, pan_val, 
                                pluck_hardness=hardness, 
                                damping_factor=damping)        
        # Stampa info nota (con tasto associato)
        tasto_associato = "N/A"
        for key_char, index in key_map.items():
            if index == i:
                tasto_associato = key_char
                break
        print(f"  Tasto '{tasto_associato}': {nota_display} (Pan: {pan_val:.2f})")

    # 7. Loop Interattivo
    print("\nPremi tasti 1-0 per note singole.")
    print("Q = Strum Giù (Grave->Acuta / Dx->Sx)")
    print("A = Strum Su (Acuta->Grave / Sx->Dx)")
    print("ESC = Esci")

    note_prompt_str = " ".join(note_names_display)

    while True:
        print(f"\nNote: {note_prompt_str}): ", end="", flush=True)
        scelta = key().lower()

        if scelta in key_map: # Tasto nota singola (1-0)
            note_idx = key_map[scelta]
            if 0 <= note_idx < num_notes:
                if note_freqs[note_idx] > 0:
                    note_audio = renderers[note_idx].render()
                    if note_audio.size > 0:
                        sd.play(note_audio, samplerate=FS, blocking=False)
                else:
                    print("Nota non valida o senza frequenza.")
            else:
                 print("Indice nota non valido?") # Debug

        elif scelta == chr(27): # ESC
            print("\nUscita dal player accordo.")
            sd.stop()
            break

        elif scelta == 'q' or scelta == 'a': # Strum
            sd.stop()
            strum_delay_sec = 0.05 # Più veloce per accordi
            strum_delay_samples = int(strum_delay_sec * FS)
            note_duration_samples = int(dur * FS)

            total_samples = note_duration_samples + ((num_notes - 1) * strum_delay_samples)
            mix_buffer = np.zeros((total_samples, 2), dtype=np.float32)
            note_order = range(num_notes) if scelta == 'q' else range(num_notes - 1, -1, -1)
            current_delay_samples = 0
            for i in note_order:
                if note_freqs[i] > 0:
                    # Riconfigura renderer (per sicurezza, anche se già fatto)
                    renderers[i].set_params(freq, dur, vol, pan_val, 
                                pluck_hardness=hardness, 
                                damping_factor=damping)                    
                    # Renderizza la singola nota
                    note_data = renderers[i].render()
                    
                    if note_data.size == 0: continue

                    # Tronca se necessario
                    actual_note_samples = note_data.shape[0]
                    samples_to_mix = min(actual_note_samples, note_duration_samples)
                    note_data_segment = note_data[:samples_to_mix]
                    
                    # Calcola posizione nel buffer
                    start_pos = current_delay_samples
                    end_pos = start_pos + samples_to_mix
                    
                    # Assicura che non sfori dal buffer
                    if end_pos > total_samples:
                        end_pos = total_samples
                        samples_to_mix = end_pos - start_pos
                        if samples_to_mix <= 0: continue # Non c'è spazio
                        note_data_segment = note_data_segment[:samples_to_mix]

                    # Mixa
                    mix_buffer[start_pos:end_pos] += note_data_segment
                
                # Incrementa il ritardo per la prossima nota
                current_delay_samples += strum_delay_samples

            # Normalizza e suona
            max_val = np.max(np.abs(mix_buffer))
            if max_val > 1.0:
                mix_buffer /= max_val
            
            sd.play(mix_buffer, samplerate=FS, blocking=False)

        else:
            print("Comando non valido.")

    return # Fine funzione SuonaAccordoTeorico

def Barre(t):
    """Riceve la tablatura e restituisce il capotasto del barrè, se lo trova."""
    # (Logica identica all'originale)
    if "0" in t: return 0
    tasti_premuti = [int(fret) for fret in t if fret not in 'X']
    if len(tasti_premuti) < 2:
        return 0
    conteggio_tasti = {}
    for tasto in tasti_premuti:
        if tasto in conteggio_tasti:
            conteggio_tasti[tasto] += 1
        else:
            conteggio_tasti[tasto] = 1
    for k, v in conteggio_tasti.items():
        if v > 0 and k <= min(list(conteggio_tasti.keys())):
            return k
    return 0

def VediTablaturaPerTasto(t):
    """Mostra la tablatura ordinata per tasto."""
    # (Logica identica all'originale)
    print("\nTablatura per tasto:")
    risultato = {}
    bar = Barre(t)
    for tasto in range(0, 22):
        risultato[tasto] = ""
        c = 6
        stopate = []
        for j in t:
            if j != "X" and tasto == int(j):
                risultato[tasto] += str(c) + ", "
            if j == "X": stopate.append(c)
            c -= 1
        if tasto > 0 and tasto == int(bar): risultato[tasto] = risultato[tasto] + "Barrè!"
        if risultato[tasto][-2:] == ", ": risultato[tasto] = risultato[tasto][:-2] + "."
    for k, v in risultato.items():
        if len(v) > 0:
            if len(v) > 2: crd = "corde"
            else: crd = "corda"
            if k == 0 and len(v) >= 1: k1 = f"Corde aperte: {v}"
            elif k == 0 and len(v) <= 2: k1 = f"Corda aperta: {v}"
            else: k1 = f"Tasto {k}, {crd}: {v}"
            print(k1)
    if len(stopate) > 0:
        stp = ''
        for j in stopate:
            stp += f"{j}, "
        stp = stp[:-2] + "."
        if len(stopate) > 1: k2 = f"Corde stoppate: {stp}"
        else: k2 = f"Corda stoppata: {stp}"
        print(k2)
    return

def VediTablaturaPerCorda(t):
    """Mostra la tablatura ordinata per corda."""
    print("\nTablatura per corda:")
    bar = Barre(t)
    if int(bar) > 0: print(f"Barrè al tasto {bar}")
    it = 0
    for corda in range(6, 0, -1):
        j = t[it]
        if j.isdigit() and int(j) >= 1 and int(j) <= 24:
            # --- MODIFICA FASE 5: Usa get_nota() ---
            nota_std = CORDE[f'{corda}.{j}']
            y = get_nota(nota_std[:-1]) # Rimuove l'ottava
            # --- Fine Modifica ---
            print(f"Corda {corda}, tasto {j}, {y}.")
        elif j.isdigit() and int(j) == 0:
            # --- MODIFICA FASE 5: Usa get_nota() ---
            nota_std = CORDE[f'{corda}.0']
            y = get_nota(nota_std[:-1]) # Rimuove l'ottava
            # --- Fine Modifica ---
            print(f"Corda {corda} libera, {y}.")
        elif j == "X":
            print(f"Corda {corda} stoppata.")
        it += 1
    return

# (Riga 355 circa, dopo VediTablaturaPerCorda)

def get_note_da_tablatura(t):
    """
    Data una tablatura (lista), restituisce una stringa
    con i nomi delle note (usando la nomenclatura attuale).
    """
    note = []
    it = 0
    for corda in range(6, 0, -1):
        j = t[it]
        if j.isdigit() and f"{corda}.{j}" in CORDE:
            nota_std = CORDE[f'{corda}.{j}']
            nota_formattata = get_nota(nota_std[:-1]) # Rimuove l'ottava
            note.append(nota_formattata)
        elif j == "X":
            note.append("X")
        it += 1
    
    # Restituisce una stringa formattata (es. MI LA RE SOL SI MI)
    return " ".join(reversed(note)) # Le corde sono 6-1, le note 1-6

def InserisciTablatura(nuova_lista_tablature, nuovo_nome_accordo):
    """Chiede all'utente una nuova tablatura (6 valori)."""
    # (Logica identica all'originale)
    while True:
        tbl = dgt(prompt=f"Tablatura: ({len(nuova_lista_tablature) + 1}) - {nuovo_nome_accordo} (Tab: ", kind="s", smax=19).upper()
        if tbl == "": return ""
        stbl = tbl.split(" ")
        if len(stbl) == 6: break
        print("Non sono stati inseriti sei valori, riprova.")
    return stbl

def DaTablaturaAStringa(t):
    """Trasforma una lista di 6 valori in tablatura (stringa)."""
    # (Logica identica all'originale)
    s = ''
    for j in t:
        if j.isdigit():
            if int(j) >= 0 and int(j) <= 9: s += j
            else: s += " " + j
        else: s += j.upper()
    return s

def RimuoviAccordi():
    """Rimuove un accordo da impostazioni['chordpedia']"""
    global archivio_modificato
    chordpedia = impostazioni['chordpedia'] # Alias per leggibilità
    
    cancello_accordo = dgt(prompt="\nInserisci l'esatto nome dell'accordo da eliminare: >", kind="s", smax=64).upper()
    if len(chordpedia) > 0:
        if cancello_accordo in chordpedia.keys():
            del chordpedia[cancello_accordo]
            archivio_modificato = True
            print(f"{cancello_accordo} eliminato. Ora l'archivio ne contiene {len(chordpedia)}.")
        else:
            print("Nome accordo non presente in Chordpedia")
    else:
        print("Il Database degli accordi è già vuoto.")
    return

def VediAccordi():
    """Permette di visualizzare, gestire e ascoltare gli accordi."""
    global archivio_modificato
    chordpedia = impostazioni['chordpedia'] # Alias per leggibilità
    l = len(chordpedia)
    if l == 0:
        print("\nArchivio vuoto, prima aggiungi qualche accordo.")
        return

    print(f"\nVisualizza uno dei {l} accordi presenti nella chordpedia.")
    print("Usa il menu interattivo per filtrare e scegliere l'accordo.")
    
    # --- OTTIMIZZAZIONE FASE 5: Sostituzione loop 'key()' con 'menu()' ---
    # Creiamo un dizionario {nome: nome} per la funzione menu
    d_accordi = {k: k for k in chordpedia.keys()}
    
    while True: # Loop di consultazione
        trovato_accordo = menu(d=d_accordi, keyslist=True, show=False, pager=20, 
                               show_on_filter=True, ntf="Accordo non trovato", 
                               p="Filtra accordo: ")
        
        if trovato_accordo is None: # Utente ha premuto ESC o Invio a vuoto
            print("Ritorno al menu Chordpedia.")
            return
        
        # --- Fine Ottimizzazione ---

        # Da qui, la logica è identica, ma usa 'trovato_accordo'
        
        # Gestione tablature multiple
        if len(chordpedia[trovato_accordo]) > 1:
            print(f"L'accordo {trovato_accordo} ha {len(chordpedia[trovato_accordo])} tablature. Scegline una:")
            dz_tablature_presenti_in_accordo = {}
            indice_tablature_in_accordo = 1
            for j in chordpedia[trovato_accordo]:
                # Usiamo str(indice) come chiave per menu()
                chiave_menu = str(indice_tablature_in_accordo)
                descrizione = DaTablaturaAStringa(j) # Usiamo j (la tablatura)
                dz_tablature_presenti_in_accordo[chiave_menu] = descrizione
                indice_tablature_in_accordo += 1
            
            # Mostriamo il menu numerato
            tablatura_scelta_key = menu(d=dz_tablature_presenti_in_accordo, show=True, numbered=True, ntf="Scelta non valida")
            if tablatura_scelta_key is None:
                continue # Torna alla scelta accordo
            
            tablatura_scelta_idx = int(tablatura_scelta_key) # L'indice menu (da 1)
        else:
            tablatura_scelta_idx = 1 # C'è solo una tablatura (indice 1)
        
        # L'indice della lista in Python è (scelta - 1)
        tablatura_scelta_py_idx = tablatura_scelta_idx - 1
        tablatura_corrente = chordpedia[trovato_accordo][tablatura_scelta_py_idx]
        print(f"\nAccordo {trovato_accordo}, tablatura {tablatura_scelta_idx} Tab: {DaTablaturaAStringa(chordpedia[trovato_accordo][tablatura_scelta_py_idx])}")
        note_accordo_str = get_note_da_tablatura(tablatura_corrente)
        # Menu gestione singola tablatura
        mn_gestione_tablatura = {
            "c": "Visualizza in ordine di corda",
            "t": "Visualizza in ordine di tasto",
            "a": "Ascolta le note",
            "m": "Modifica tablatura",
            "r": "Rimuovi questa tablatura",
            "p": "Scegli un altro accordo",
            "i": "Torna al menu Chordpedia",
        }
        while True: # Loop sottomenu
            # --- MODIFICA OBIETTIVO 1: Rimossa la riga 'print(f"Note: ...")' da qui ---
            s = menu(d=mn_gestione_tablatura, ntf="Comando non valido", keyslist=True, show=True, show_on_filter=False)
            
            if s == "i": return # Esce da VediAccordi
            elif s == "p" or s is None:
                print("\nProsegui con la consultazione degli accordi")
                break # Esce dal sottomenu e torna al loop scelta accordo
            
            elif s == "c": VediTablaturaPerCorda(chordpedia[trovato_accordo][tablatura_scelta_py_idx])
            elif s == "t": VediTablaturaPerTasto(chordpedia[trovato_accordo][tablatura_scelta_py_idx])
            
            elif s == "a": 
                # --- MODIFICA FASE 5: Chiama la nuova Suona() (Fase 3) ---
                Suona(chordpedia[trovato_accordo][tablatura_scelta_py_idx])
            
            elif s == "r":
                if len(chordpedia[trovato_accordo]) == 1:
                    print("\nNon puoi rimuovere l'ultima tablatura.")
                    print("Rimuovi invece l'intero accordo dal menù precedente.")
                else:
                    del chordpedia[trovato_accordo][tablatura_scelta_py_idx]
                    print(f"Rimozione effettuata. Ora {trovato_accordo} ha {len(chordpedia[trovato_accordo])} tablature.")
                    archivio_modificato = True
                    break # Torna al loop scelta accordo
                    
            elif s == "m":
                print(f"\nTab: ({tablatura_scelta_idx}) = {DaTablaturaAStringa(chordpedia[trovato_accordo][tablatura_scelta_py_idx])}. Nuova tab? ")
                stbl = InserisciTablatura([], trovato_accordo)
                if stbl != "":
                    chordpedia[trovato_accordo][tablatura_scelta_py_idx] = stbl
                    archivio_modificato = True
                    print("Tablatura modificata")
                else:
                    print("Modifica annullata.")
                break # Torna al loop scelta accordo
        # Fine loop sottomenu
    # Fine loop consultazione
    return

def Aggiungiaccordo():
    """Aggiunge un nuovo accordo a impostazioni['chordpedia']"""
    global archivio_modificato
    chordpedia = impostazioni['chordpedia'] # Alias per leggibilità
    
    print("\nAggiungi un nuovo accordo alla collezione")
    while True:
        nuovo_nome_accordo = dgt(prompt="Nome accordo: ", kind="s", smin=1, smax=40).upper()
        if nuovo_nome_accordo == "":
            print("Aggiunta annullata.")
            return
        if nuovo_nome_accordo not in chordpedia.keys(): break
        print("Già presente della collezione. Riprova con un nome diverso.")
    
    nuova_lista_tablature = []
    print("Inserisci la tablatura: 6 valori (Tasto o X) separati da spazi")
    print("Dalla corda 6 (la più spessa) alla corda 1 (la più sottile).")
    print("Es: '0 2 2 1 0 0' (E Maggiore)")
    print("Concludi con un INVIO a vuoto.")
    
    while True:
        stbl = InserisciTablatura(nuova_lista_tablature, nuovo_nome_accordo)
        if stbl == "": break
        nuova_lista_tablature.append(stbl)
    
    if len(nuova_lista_tablature) > 0:
        chordpedia[nuovo_nome_accordo] = nuova_lista_tablature
        archivio_modificato = True
        print(f"Accordo {nuovo_nome_accordo} aggiunto con {len(nuova_lista_tablature)} tablature.")
        print(f"La Chordpedia ora contiene {len(chordpedia)} accordi.")
    else:
        print("Nessuna tablatura inserita. Accordo non aggiunto.")
    return

def Manlimiti(s):
    """
    Riceve stringa "N.N", restituisce 2 int per i limiti del manico.
    (Logica identica all'originale, ma più robusta)
    """
    if "." not in s or " " in s:
        print("Errore: formato non valido. Usare N.N (es. 0.4).")
        return 0, 21
    
    s2 = s.split(".")
    if len(s2) != 2 or not s2[0].isdigit() or not s2[1].isdigit():
        print("Errore: inserire solo valori numerici separati da un punto.")
        return 0, 21
        
    maninf, mansup = int(s2[0]), int(s2[1])
    
    # Assicura che i limiti siano in ordine
    if maninf > mansup:
        print(f"Limiti invertiti. Uso {mansup}.{maninf}.")
        return mansup, maninf
        
    return maninf, mansup

def Spacchetta(k):
    """
    Funzione di servizio di MostraCorde.
    Riceve elenco posizioni e stampa suddividendo le corde.
    """
    # (Logica identica all'originale)
    cc = 0
    for pos in k:
        pc, pt = pos.split(".")[0], pos.split(".")[1]
        if cc != pc: print(f"\nCorda {pc}, tasti: ", end="")
        cc = pc
        if cc == pc:
            print(pt, end=" ")
        else:
            cc = pc
    return

def MostraCorde(nota_std, rp=False, maninf=0, mansup=21):
    """
    Mostra tutte le posizioni della nota cercata sul manico.
    - nota_std: Nota in formato standard (es. "C4" o "C")
    - rp: se True, restituisce la lista invece di stamparla
    - maninf, mansup: limiti del manico per la ricerca
    """
    
    # Se la nota non ha l'ottava (es. "C"), cerca in tutte le ottave
    con_ottava = nota_std[-1].isdigit()
    
    if not rp: 
        print(f"Nota {get_nota(nota_std)} trovata nelle seguenti posizioni (tasti {maninf}-{mansup}):")
        
    posizioni = []
    for k, v in CORDE.items():
        ks = k.split("."); 
        ks1 = int(ks[1]) # Tasto
        
        # Filtra per manico
        if ks1 < maninf or ks1 > mansup:
            continue
            
        if con_ottava and nota_std == v: # Cerca nota con ottava (es. C4)
            posizioni.append(k)
        elif not con_ottava and nota_std == v[:-1]: # Cerca nota senza ottava (es. C)
            posizioni.append(k)

    if not rp:
        Spacchetta(posizioni)
        print()
        return
    else:
        return posizioni
# (Riga 530 circa, dopo 'def MostraCorde(...):')

# --- Logica di Gestione Scale (Fase 6) ---

def render_scale_audio(note_list, suono_params, bpm):
    """
    Usa la classe NoteRenderer per generare un array audio per una scala.
    Accetta una lista di stringhe nota (es. "C4") o frequenze (float).
    """
    print("Rendering audio scala...")

    s_kind = suono_params['kind']
    s_adsr = suono_params['adsr']
    s_vol = suono_params['volume']
    s_dur = 60.0 / bpm # Durata di ogni nota
    s_pan = 0.0 # Pan centrale per le scale

    if s_dur <= 0:
        print("Errore: Durata nota non valida (BPM troppo alti?).")
        return np.array([], dtype=np.float32)
    # --- CORREZIONE: Usa NoteRenderer ---
    renderer = NoteRenderer(fs=FS)
    # ------------------------------------
    segmenti_audio = []
    note_count = 0

    for note_or_freq in note_list:
        freq = 0.0
        if isinstance(note_or_freq, (int, float)):
            if note_or_freq is not None and note_or_freq > 0:
                 freq = float(note_or_freq)
        elif isinstance(note_or_freq, str):
            freq = note_to_freq(note_or_freq)

        # Se freq è 0 o negativa, crea un segmento di silenzio
        if freq <= 0:
             silence_samples = int(round(s_dur * FS))
             if silence_samples > 0:
                  segmenti_audio.append(np.zeros((silence_samples, 2), dtype=np.float32))
             continue # Passa alla prossima nota

        # Imposta i parametri sul renderer
        renderer.set_params(freq, s_dur, s_vol, s_pan, 
                            adsr_list=s_adsr, 
                            kind=s_kind)
        # Chiama render() per ottenere l'array audio
        note_audio = renderer.render() 
        # Aggiungi il segmento audio (o silenzio se render fallisce)
        if note_audio is not None and note_audio.size > 0:
            # Verifica che l'array restituito abbia la forma corretta (samples, 2)
            if note_audio.ndim == 2 and note_audio.shape[1] == 2:
                 segmenti_audio.append(note_audio)
                 note_count += 1
            else:
                 print(f"Attenzione: NoteRenderer.render() ha restituito un array con forma inattesa {note_audio.shape} per freq={freq}. Aggiungo silenzio.")
                 silence_samples = int(round(s_dur * FS))
                 if silence_samples > 0: segmenti_audio.append(np.zeros((silence_samples, 2), dtype=np.float32))
        else:
             # Se il rendering fallisce, aggiungi silenzio
             silence_samples = int(round(s_dur * FS))
             if silence_samples > 0:
                  segmenti_audio.append(np.zeros((silence_samples, 2), dtype=np.float32))

    if not segmenti_audio:
        print("Rendering fallito: nessun segmento audio generato.")
        return np.array([], dtype=np.float32)

    print(f"Rendering completato ({note_count} note suonate).")
    # Concatena tutti i segmenti (note e silenzi)
    try:
        final_audio = np.concatenate(segmenti_audio, axis=0)
    except ValueError as e:
         print(f"Errore durante la concatenazione audio: {e}")
         valid_segments = [seg for seg in segmenti_audio if seg.ndim == 2 and seg.shape[1] == 2 and seg.shape[0] > 0]
         if not valid_segments: return np.array([], dtype=np.float32)
         try:
              final_audio = np.concatenate(valid_segments, axis=0)
              print("   (Recupero concatenazione riuscito escludendo segmenti problematici)")
         except ValueError:
               print("   (Recupero concatenazione fallito)")
               return np.array([], dtype=np.float32)

    return final_audio
def VisualizzaEsercitatiScala():
    """ Versione Finale Ibrida con gestione microtoni completa e indentazione corretta """
    global SCALE_CATALOG, SCALE_TYPES_DICT
    suono_2 = impostazioni['suono_2']

    print("\n--- Visualizza ed Esercitati sulle Scale (music21 - Catalogo) ---")

# --- 1. Scegli Tonica ---
    # Dizionario {Mostra_Utente -> Ritorna_Standard}
    mappa_toniche = {}
    if impostazioni['nomenclatura'] == 'latino':
        # Inverti: {'DO': 'C', 'DO#': 'C#', ...}
        mappa_toniche = {lat: std for std, lat in STD_TO_LATINO.items() if len(std) <= 2 and std in NOTE_STD}
    else:
        # Mantieni: {'C': 'C', 'C#': 'C#', ...}
        mappa_toniche = {anglo: std for std, anglo in STD_TO_ANGLO.items() if len(std) <= 2 and std in NOTE_STD}
    
    # Chiama menu() con keyslist=True.
    # Mostrerà le chiavi ('DO', 'RE'... o 'C', 'D'...)
    tonica_scelta_display = menu(d=mappa_toniche, keyslist=True, show=True, 
                                 pager=12, ntf="Nota non valida", 
                                 p="Scegli la TONICA della scala: ")
    
    if tonica_scelta_display is None: return # Utente ha annullato
        
    # Ottieni la nota standard ('C', 'D'...) dal dizionario
    tonica_std_base = mappa_toniche[tonica_scelta_display]
    tonica_std_con_ottava = tonica_std_base + "4"
    # --- 2. Scegli Tipo di Scala (dal Catalogo via Indice) ---
    selected_key = menu(d=SCALE_TYPES_DICT, keyslist=True, show=False,
                        pager=20, ntf="Tipo non valido",
                        p=f"Filtra TIPO scala per {get_nota(tonica_std_base)} (o '...'): ")
    if selected_key is None: return

    # Inizializza variabili fuori dal try per scope
    usi_string = ""
    nome_scala_display_base = ""
    scala_m21 = None
    note_scala_std_asc = []
    note_scala_formattate_asc = []
    note_scala_formattate_desc = [] # Definita qui
    note_per_audio_asc = []
    note_per_audio_desc = []
    is_microtonal_scale = False

    try:
        # --- Gestione selezione: Menu diretto o Ricerca Fuzzy ---
        if selected_key == "...":
            # Esegui ricerca fuzzy
            selected_key_from_fuzzy = fuzzy_search_and_select(
                SCALE_TYPES_DICT,
                f"Cerca TIPO scala per {get_nota(tonica_std_base)} (testo parziale): ",
                "tipo di scala"
            )
            if selected_key_from_fuzzy is None: return # Annullato
            selected_key = selected_key_from_fuzzy
            if selected_key == "...":
                print("Annullato.")
                return

        # --- Costruzione USI e Nome Display ---
        try:
            paradigm, scale_id = selected_key.split(':', 1)
            nome_scala_display_base = SCALE_TYPES_DICT.get(selected_key, scale_id)
            usi_string = f"{paradigm}:{tonica_std_con_ottava}:{scale_id}"
        except ValueError:
            print(f"Errore: Chiave selezione ('{selected_key}') malformata.")
            key("Premi un tasto...")
            return

        # --- Istanziazione tramite Factory USI ---
        scala_m21 = get_scale_from_usi(usi_string)

        # --- 3. Estrazione delle Note ---

        def process_pitch(p):
            nonlocal is_microtonal_scale
            if not isinstance(p, pitch.Pitch): return None, str(p), None
            frequenza = p.frequency
            nome_m21_base = p.nameWithOctave
            nome_std_base_per_lookup = nome_m21_base.replace('-', 'b')
            nota_visualizzata = get_nota(nome_std_base_per_lookup)
            is_micro = False
            if p.accidental and hasattr(p.accidental, 'alter') and p.accidental.alter not in [0.0, 1.0, -1.0, 2.0, -2.0]:
                is_micro = True; is_microtonal_scale = True
            p_standard = pitch.Pitch(p.step + str(p.octave if p.octave is not None else 4))
            if p.accidental and p.accidental.name in ['sharp', 'flat', 'double-sharp', 'double-flat']: p_standard.accidental = p.accidental
            nota_base_per_manico = p_standard.name.replace('-','b')
            nota_base_per_manico = ''.join(filter(lambda c: not c.isdigit(), nota_base_per_manico))
            if frequenza is None and is_micro: print(f"Attenzione: Impossibile calcolare frequenza per {p.nameWithOctave}")
            return nota_base_per_manico, nota_visualizzata, frequenza

        local_note_std_asc = []
        local_note_formattate_asc = []
        local_note_audio_asc = []
        local_note_audio_desc = []
        local_processed_display_asc = set()
        local_processed_display_desc = set()
        local_desc_notes_display = []

        # Determina estremi ottava (con try/except interno)
        try: #<<<--- TRY INTERNO 1 ---<<<
            p_start = scala_m21.getTonic() if hasattr(scala_m21, 'getTonic') else pitch.Pitch(tonica_std_con_ottava)
            start_octave = p_start.octave if p_start.octave is not None else 4
            end_octave = start_octave + 1
            p_end = pitch.Pitch(p_start.step + str(end_octave))
            p_start_desc = p_end
            p_end_desc = p_start
        except Exception as pitch_err: #<<<--- EXCEPT INTERNO 1 ---<<<
            print(f"Errore nella definizione dell'intervallo di ottava: {pitch_err}")
            p_start = pitch.Pitch(tonica_std_con_ottava)
            p_end = pitch.Pitch(tonica_std_base + "5")
            p_start_desc = p_end
            p_end_desc = p_start

        # Estrai pitches (con try/except interno)
        pitches_asc = [] # Inizializza prima del try
        pitches_desc = []# Inizializza prima del try
        try: #<<<--- TRY INTERNO 2 ---<<<
            
            # --- INIZIO BLOCCO MODIFICATO ---
            # Questa logica sostituisce tutti i tentativi precedenti.
            # È più semplice e robusta.
            
            if isinstance(scala_m21, scale.ScalaScale):
                # .pitches per ScalaScale funziona e dà la lista completa
                pitches_asc = scala_m21.pitches
                pitches_desc = list(reversed(pitches_asc))

            elif isinstance(scala_m21, scale.ConcreteScale):
                # .pitches per ConcreteScale restituisce l'ottava (8 note, C4..C5)
                # Questo evita getPitches() e il bug 'includePitchEnd'
                # E sostituisce il tuo fallback buggato.
                pitches_asc = scala_m21.pitches
                
                # La discesa è semplicemente l'inverso
                pitches_desc = list(reversed(pitches_asc))

            else: 
                print("Attenzione: Tipo di scala non riconosciuto per l'estrazione.")
            # --- FINE BLOCCO MODIFICATO ---

        except Exception as get_pitch_err: #<<<--- EXCEPT INTERNO 2 ---<<<
            print(f"Errore durante l'estrazione delle note dalla scala: {get_pitch_err}")
            # pitches_asc e pitches_desc rimangono liste vuote

        # Processa pitches ascendenti (ora DENTRO il try principale)
        if pitches_asc:
            for p in pitches_asc:
                result = process_pitch(p)
                if result:
                    nota_base_manico, nota_display, freq = result
                    if nota_base_manico and nota_base_manico not in local_note_std_asc: local_note_std_asc.append(nota_base_manico)
                    # De-duplicazione per la stampa
                    if nota_display not in local_processed_display_asc: 
                        local_note_formattate_asc.append(nota_display)
                        local_processed_display_asc.add(nota_display)
                    # L'audio prende tutte le note
                    local_note_audio_asc.append(freq)
        else: 
            print("Attenzione: Nessuna nota ascendente estratta.")
            
        if pitches_desc:
            for p in pitches_desc:
                result = process_pitch(p)
                if result:
                    _, nota_display, freq = result
                    # L'audio prende tutte le note (ora 8 corrette)
                    local_note_audio_desc.append(freq)
                    # De-duplicazione per la stampa
                    if nota_display not in local_processed_display_desc: 
                        local_desc_notes_display.append(nota_display)
                        local_processed_display_desc.add(nota_display)
        
        elif local_note_audio_asc: # Fallback audio
            print("Info: Generazione audio discendente invertendo le frequenze ascendenti.")
            local_note_audio_desc = list(reversed(local_note_audio_asc))
            if local_note_formattate_asc:
                local_desc_notes_display = list(reversed(local_note_formattate_asc))
        else: 
            print("Attenzione: Nessuna nota discendente estratta.")

        # Assegna i risultati alle variabili esterne
        note_scala_std_asc = local_note_std_asc
        note_scala_formattate_asc = local_note_formattate_asc
        note_per_audio_asc = local_note_audio_asc
        note_per_audio_desc = local_note_audio_desc
        note_scala_formattate_desc = local_desc_notes_display

        # --- 4. Stampa Riepilogo (INDENTATO) ---
        nome_scala_display = f"{get_nota(tonica_std_base)} {nome_scala_display_base}"
        note_asc_str = " ".join(note_scala_formattate_asc)
        note_desc_str = " ".join(note_scala_formattate_desc) 

        print(f"\nScala: {nome_scala_display}")
        print(f"Note (Asc): {note_asc_str if note_asc_str else '(Nessuna nota trovata)'}")
        if is_microtonal_scale:
            print("INFO: Scala microtonale rilevata. L'audio userà le frequenze esatte (se calcolabili).")

        # Ora le due stringhe dovrebbero essere l'inversa l'una dell'altra
        if note_asc_str != note_desc_str and note_desc_str:
            print(f"Note (Desc): {note_desc_str}")

        # --- 5. Mostra su Manico (INDENTATO) ---
        if is_microtonal_scale:
            print("\nVisualizzazione sul manico approssimata per scale microtonali.")
        if not note_scala_std_asc: # Se non ci sono note standard
            print("\nImpossibile mostrare sul manico: nessuna nota standard generata.")
        else:
            print("\nPuoi indicare una porzione di manico...")
            scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
            maninf, mansup = 0, 21
            if scelta_manico != "": maninf, mansup = Manlimiti(scelta_manico)
            visualizza_note_su_manico(note_scala_std_asc, maninf, mansup)

        # --- 6. Loop Esercizio (INDENTATO) ---
        if not note_per_audio_asc and not note_per_audio_desc:
            print("\nNessuna nota audio generata per l'esercizio.")
            key("Premi un tasto per tornare al menu...")
        else:
            print("\n--- Menu Esercizio Scala ---\n\tPremi '?' per aiuto.")
            bpm = impostazioni['default_bpm']
            loop_attivo = False
            loop_count = 1
            ultima_direzione = 'a'
            audio_data_asc = None
            audio_data_desc = None
            menu_esercizio = {"a": "Ascolta ascendente", "d": "Ascolta discendente", "l": "Attiva/Disattiva Loop", "b": "Imposta BPM", "i": "Indietro"}
            menu_mostrato_iniziale = False
            loop_messaggio_stampato = False

            while True: # Inizio Loop Esercizio
                audio_to_play = None
                dur_totale = 0.0
                scelta_raw = "" # Inizializza input grezzo
                scelta = None   # Inizializza comando valido
                if loop_attivo: # Modalità Loop
                    if not loop_messaggio_stampato: print("Loop ATTIVO. Premi 'L' per fermare."); loop_messaggio_stampato = True
                    note_scala_loop_str = note_asc_str if ultima_direzione == 'a' else note_desc_str
                    print(f"Numero ripetizione: {loop_count} - Note: {note_scala_loop_str}" + " "*10, end="\r", flush=True)
                    tasto = key(attesa=0.1)
                    if tasto and tasto.lower() == 'l': loop_attivo = False; print("\nLoop disattivato." + " "*30); sd.stop(); loop_messaggio_stampato = False; continue
                    else: scelta = ultima_direzione
                else: # Modalità Menu Interattivo
                    loop_messaggio_stampato = False
                    prompt_scale = f"Note (Asc): {note_asc_str if note_asc_str else '(vuota)'}"
                    if note_asc_str != note_desc_str and note_desc_str: prompt_scale += f" | (Desc): {note_desc_str}"
                    if not menu_mostrato_iniziale:
                        print(f"Note (Asc): {note_asc_str if note_asc_str else '(vuota)'}")
                        if note_asc_str != note_desc_str and note_desc_str: print(f"Note (Desc): {note_desc_str}")
                        scelta = menu(d=menu_esercizio, keyslist=True, ntf="Scelta non valida", show=True, p="> ")
                        menu_mostrato_iniziale = True
                    else:
                        note_da_mostrare = note_asc_str if ultima_direzione == 'a' else note_desc_str
                        direzione_str = "Asc" if ultima_direzione == 'a' else "Desc"
                        print(f"Note ({direzione_str}): {note_da_mostrare if note_da_mostrare else '(vuota)'} (Premi '?' per aiuto)" + " "*20, end="\r", flush=True)
                        scelta_raw = key().lower()
                        scelta = scelta_raw if scelta_raw in menu_esercizio else None
                        if scelta_raw == '?': menu(d=menu_esercizio, show=True, p="> "); continue

                # --- Gestione Scelte Menu Esercizio ---
                exit_pressed = (not loop_attivo and scelta_raw == chr(27))
                if scelta == 'i' or exit_pressed:
                    if loop_attivo: loop_attivo = False; print("\nLoop disattivato." + " "*30); sd.stop()
                    if menu_mostrato_iniziale and not loop_attivo: print(" " * 80, end="\r") # Pulisci riga note
                    break
                elif scelta == 'l': # ... (codice 'l') ...
                    loop_attivo = not loop_attivo
                    if loop_attivo: loop_count = 1; print(" " * 80, end="\r")
                    else: print("\nLoop disattivato." + " "*30); sd.stop()
                    continue
                elif scelta == 'b': # ... (codice 'b') ...
                    global archivio_modificato
                    print(" " * 80, end="\r")
                    nuovo_bpm = dgt(f"Nuovi BPM (attuale: {bpm}): ", kind='i', imin=20, imax=300, default=bpm)
                    if nuovo_bpm != bpm:
                        bpm = nuovo_bpm; impostazioni['default_bpm'] = bpm; archivio_modificato = True
                        print(f"BPM predefiniti aggiornati a {bpm}.")
                        audio_data_asc = None; audio_data_desc = None
                elif scelta == 'a': # ... (codice 'a') ...
                    ultima_direzione = 'a'
                    valid_notes_asc = [f for f in note_per_audio_asc if f is not None]
                    if not valid_notes_asc: print("\nNote ascendenti non disponibili per l'audio."); continue
                    if audio_data_asc is None: audio_data_asc = render_scale_audio(note_per_audio_asc, suono_2, bpm)
                    audio_to_play = audio_data_asc
                    dur_totale = len(note_per_audio_asc) * (60.0 / bpm)
                elif scelta == 'd': # ... (codice 'd') ...
                    ultima_direzione = 'd'
                    valid_notes_desc = [f for f in note_per_audio_desc if f is not None]
                    if not valid_notes_desc: print("\nNote discendenti non disponibili per l'audio."); continue
                    if audio_data_desc is None: audio_data_desc = render_scale_audio(note_per_audio_desc, suono_2, bpm)
                    audio_to_play = audio_data_desc
                    dur_totale = len(note_per_audio_desc) * (60.0 / bpm)
                elif scelta is None and not loop_attivo: # Input non valido
                    print("\nComando non valido. Premi '?' per aiuto.")
                    continue

                # --- Riproduzione Audio (indentato) ---
                if audio_to_play is not None and audio_to_play.size > 0:
                    if not loop_attivo:
                        print(" " * 80, end="\r")
                        print(f"Riproduzione scala {'ascendente' if scelta == 'a' else 'discendente'} a {bpm} BPM...")
                    sd.play(audio_to_play, samplerate=FS, blocking=False)
                    if loop_attivo:
                        step = 0.05; passi_totali = int(dur_totale / step) if dur_totale > 0 else 0
                        tempo_rimanente = dur_totale - (passi_totali * step)
                        for _ in range(passi_totali):
                            tasto = key(attesa=step)
                            if tasto and tasto.lower() == 'l': loop_attivo = False; print("\nLoop fermato." + " "*30); sd.stop(); break
                        if not loop_attivo: continue
                        if tempo_rimanente > 0: aspetta(tempo_rimanente)
                        loop_count += 1
                    else:
                        if dur_totale > 0: aspetta(dur_totale)
                elif not loop_attivo: # Messaggio "Nessun audio"
                    print(" " * 80, end="\r")
                    print("Nessun audio da riprodurre per la selezione.")
                    key("Premi un tasto...")

            # --- Fine Loop Esercizio ---
            print(" " * 80, end="\r")

        print("Fine esercizio.") 

    # --- Blocchi except per il try principale (correttamente allineati) ---
    except (InvalidUSIFormatError, UnknownScaleError, ScaleException) as e:
        print(f"\nErrore nella generazione della scala: {e}")
        key("Premi un tasto...")
    except Exception as e:
        print(f"\nErrore imprevisto durante la generazione della scala: {e}")
        if usi_string: print(f"USI tentato: '{usi_string}'")
        key("Premi un tasto...")
# --- Funzioni Segnaposto (Stub per Fase 2) ---

def GestoreChordpedia():
    """Gestisce il DB degli accordi (Implementazione Fase 5 - Corretta)"""
    global archivio_modificato
    print("\n--- Tablature Accordi ---") 
    print("Gestore del database degli accordi.")
    
    mnaccordi = {
        "v": "Vedi e gestisci accordi",
        "a": "Aggiungi un nuovo accordo",
        "r": "Rimuovi un accordo",
        "i": "Torna al menu principale"
    }
    
    # RIMOSSA: menu(d=mnaccordi, show=True) <-- Era qui
    
    while True:
        s = menu(d=mnaccordi, ntf="Non trovato", keyslist=True, show=True, show_on_filter=False)
        
        if s == "i" or s is None:
            print("Ritorno al menu principale.")
            break
        elif s == "a":
            Aggiungiaccordo()
        elif s == "v":
            VediAccordi()
        elif s == "r":
            RimuoviAccordi()
        
        # RIMOSSO: print("\n--- Menu Chordpedia ---") <-- Era qui
    return
# (Riga 837 circa)

def ModificaSuono(suono_key):
    """
    Funzione helper per modificare i parametri di 'suono_1' o 'suono_2'.
    Gestisce i diversi parametri per ogni tipo di suono.
    """
    global archivio_modificato
    
    suono = impostazioni[suono_key]
    print(f"\n--- Modifica {suono['descrizione']} ---")

    # --- Logica Condizionale ---
    if suono_key == 'suono_1':
        # --- Parametri Karplus-Strong (suono_1) ---
        
        # 1. Modifica pluck_hardness (scalato 1-10)
        current_hardness_float = suono.get('pluck_hardness', 0.6)
        # Mappa inversa: [0.1, 0.9] -> [1, 10]
        current_hardness_int = int(round(1 + (np.clip(current_hardness_float, 0.1, 0.9) - 0.1) * (9.0 / 0.8)))
        
        hardness_prompt = f"Durezza plettro (1=morbido, 10=brillante) (attuale: {current_hardness_int}): "
        new_hardness_int = dgt(hardness_prompt, kind='i', imin=1, imax=10, default=current_hardness_int)
        
        # Mappa [1, 10] -> [0.1, 0.9] e salva il float
        suono['pluck_hardness'] = 0.1 + (new_hardness_int - 1) * (0.8 / 9.0)

        # 2. Modifica damping_factor (scalato 1-10)
        current_damping_float = suono.get('damping_factor', 0.997)
        # Mappa inversa: [0.990, 0.999] -> [1, 10]
        current_damping_int = int(round(1 + (np.clip(current_damping_float, 0.990, 0.999) - 0.990) / 0.001))

        damping_prompt = f"Sustain (1=corto, 10=lungo) (attuale: {current_damping_int}): "
        new_damping_int = dgt(damping_prompt, kind='i', imin=1, imax=10, default=current_damping_int)

        # Mappa [1, 10] -> [0.990, 0.999] e salva il float
        suono['damping_factor'] = 0.990 + (new_damping_int - 1) * 0.001

        # 3. Modifica Durata Massima (come prima)
        dur_prompt = f"Durata max accordi (sec) (attuale: {suono['dur_accordi']}): "
        suono['dur_accordi'] = dgt(dur_prompt, kind='f', fmin=0.1, fmax=10.0, default=suono['dur_accordi'])
    
    elif suono_key == 'suono_2':
        # --- Parametri Legacy (suono_2) ---
        
        # 1. Modifica Tipo di Onda (Kind)
        onda_prompt = f"Onda (1=Sin, 2=Quadra, 3=Tri, 4=Saw, 5=String) (attuale: {suono['kind']}): "
        suono['kind'] = dgt(onda_prompt, kind='i', imin=1, imax=5, default=suono['kind'])

        # 2. Modifica ADSR
        print("Inserisci i valori ADSR (premi Invio per confermare il valore attuale):")
        labels_adsr = ["Attacco % (tempo)", "Decadimento % (tempo)", "Sustain Livello % (vol)", "Rilascio % (tempo)"]
        vecchio_adsr = suono['adsr']
        nuovo_adsr = []
        
        for i in range(4):
            val = dgt(f"{labels_adsr[i]} (attuale: {vecchio_adsr[i]}): ", 
                        kind='f', fmin=0.0, fmax=100.0, default=vecchio_adsr[i])
            nuovo_adsr.append(val)
        
        # Validazione somma ADSR
        somma_adr = nuovo_adsr[0] + nuovo_adsr[1] + nuovo_adsr[3]
        if somma_adr > 100.0:
            print(f"ATTENZIONE: La somma di Attacco, Decadimento e Rilascio ({somma_adr}%) supera 100%.")
            print("ADSR non modificato.")
        else:
            suono['adsr'] = nuovo_adsr

    # --- Parametro Comune (Volume) ---
    vol_prompt = f"Volume (0.0 - 1.0) (attuale: {suono['volume']}): "
    suono['volume'] = dgt(vol_prompt, kind='f', fmin=0.0, fmax=1.0, default=suono['volume'])

    print(f"Impostazioni per {suono['descrizione']} aggiornate.")
    archivio_modificato = True
    key("Premi un tasto per continuare...")
def GestoreImpostazioni():
    """Gestisce la modifica delle impostazioni dell'app."""
    global archivio_modificato
    print("\n--- Gestore Impostazioni ---")
    
    while True:
        # Il menu mostra dinamicamente l'impostazione corrente
        menu_impostazioni = {
            'n': f"Cambia nomenclatura (attuale: {impostazioni['nomenclatura']})",
            '1': f"Modifica {impostazioni['suono_1']['descrizione']}",
            '2': f"Modifica {impostazioni['suono_2']['descrizione']}",
            'i': "Torna al menu principale"
        }
        
        scelta = menu(d=menu_impostazioni, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
        
        if scelta == 'n':
            # Inverti l'impostazione
            if impostazioni['nomenclatura'] == 'latino':
                impostazioni['nomenclatura'] = 'anglosassone'
            else:
                impostazioni['nomenclatura'] = 'latino'
            
            print(f"Nomenclatura impostata su: {impostazioni['nomenclatura']}")
            archivio_modificato = True
            key("Premi un tasto...")
            
        elif scelta == '1':
            ModificaSuono('suono_1')
            
        elif scelta == '2':
            ModificaSuono('suono_2')
            
        elif scelta == 'i' or scelta is None:
            print("Ritorno al menu principale.")
            break
# (Riga 860 circa)

def TrovaNota():
    """
    Trova le posizioni di una nota (senza ottava) sul manico,
    chiedendo i limiti e usando la funzione MostraCorde.
    (Implementazione Fase 7)
    """
    print("\n--- Trova Nota sul Manico ---")
    print(f"Cerca una nota. Nomenclatura attuale: {impostazioni['nomenclatura']}.")
    
    # Determina la lista di note valide e la mappa di conversione
    if impostazioni['nomenclatura'] == 'latino':
        lista_note_valide = NOTE_LATINE
        mappa_inversa = dict(zip(NOTE_LATINE, NOTE_STD))
    else:
        lista_note_valide = NOTE_ANGLO
        mappa_inversa = dict(zip(NOTE_ANGLO, NOTE_STD))
        
    print(f"Note valide (senza ottava): {', '.join(lista_note_valide)}")
    s_nota = dgt("Inserisci il nome della nota: ", smin=1, smax=5).upper()
    
    if s_nota == "":
        print("Operazione annullata.")
        key("Premi un tasto...")
        return
        
    # Validiamo e convertiamo la nota in formato Standard (es. "C#")
    nota_std = None
    if s_nota in mappa_inversa:
        nota_std = mappa_inversa[s_nota]
    else:
        print(f"'{s_nota}' non è un nome di nota valido in questa nomenclatura.")
        key("Premi un tasto...")
        return
        
    # Chiediamo i limiti del manico
    print("\nPuoi indicare una porzione di manico per la ricerca (es. 0.4)")
    scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
    maninf, mansup = 0, 21
    if scelta_manico != "":
        maninf, mansup = Manlimiti(scelta_manico)
        
    # Chiamiamo la funzione helper che stampa i risultati
    # (rp=False per stampare, True per restituire la lista)
    MostraCorde(nota_std, rp=False, maninf=maninf, mansup=mansup)
    
    key("Premi un tasto per tornare al menu...")
def TrovaPosizione():
    """Trova la nota data una posizione C.T e la suona."""
    print("\n--- Trova Posizione (C.T) ---")
    s = dgt("Inserisci Corda.Tasto (es. 6.3): ", smax=5)
    
    if s in CORDE:
        nota_std = CORDE[s]
        print(f"Sulla corda {s.split('.')[0]}, tasto {s.split('.')[1]}, si trova la nota: {get_nota(nota_std)}")
        
        suono_1 = impostazioni['suono_1']
        
        freq = note_to_freq(nota_std)
        corda_idx_zero_based = 6 - int(s.split('.')[0])
        pan = -0.8 + (corda_idx_zero_based * 0.32)
        dur = suono_1['dur_accordi']
        vol = suono_1['volume'] 
        
        # Crea un singolo renderer
        hardness = suono_1.get('pluck_hardness', 0.6)
        damping = suono_1.get('damping_factor', 0.997)        
        renderer = NoteRenderer(fs=FS)
        
        # Imposta i parametri
        renderer.set_params(freq, dur, vol, pan, 
                            pluck_hardness=hardness, 
                            damping_factor=damping)        
        # Renderizza la nota e la ottiene
        note_audio = renderer.render()
        
        # Suona (non bloccante) sul buffer renderizzato
        if note_audio.size > 0:
            sd.play(note_audio, samplerate=FS, blocking=False)
        
    elif s == "":
        print("Operazione annullata.")
    else:
        print(f"Posizione '{s}' non valida. Formato richiesto: C.T (es. 6.3), tasti da 0 a 21.")
    
    key("Premi un tasto per tornare al menu...")
def CostruttoreAccordi():
    """
    Costruisce accordi usando music21.harmony.ChordSymbol secondo
    le best practice definite nel documento tecnico. (Versione Completa)
    """
    global USER_CHORD_DICT # Accedi al dizionario globale corretto

    print("\n--- Costruttore di Accordi Teorico (harmony.ChordSymbol) ---")
    print("Scopri quali note compongono qualsiasi accordo.")

# --- 1. Scegli la Tonica ---
    # Dizionario {Mostra_Utente -> Ritorna_Standard}
    mappa_toniche = {}
    if impostazioni['nomenclatura'] == 'latino':
        # Inverti: {'DO': 'C', 'DO#': 'C#', ...}
        mappa_toniche = {lat: std for std, lat in STD_TO_LATINO.items() if len(std) <= 2 and std in NOTE_STD}
    else:
        # Mantieni: {'C': 'C', 'C#': 'C#', ...}
        mappa_toniche = {anglo: std for std, anglo in STD_TO_ANGLO.items() if len(std) <= 2 and std in NOTE_STD}

    # Chiama menu() con keyslist=True.
    # Mostrerà le chiavi ('DO', 'RE'... o 'C', 'D'...)
    tonica_scelta_display = menu(d=mappa_toniche, keyslist=True, show=True,
                                 pager=12, ntf="Nota non valida", p="Scegli la TONICA: ")
    
    if tonica_scelta_display is None:
        print("Costruzione annullata.")
        return # Utente ha annullato
        
    # Ottieni la nota standard ('C', 'D'...) dal dizionario
    tonica_std = mappa_toniche[tonica_scelta_display]
    # --- 2. Scegli il Tipo di Accordo (dal Dizionario Introspezione) ---
    primary_shorthand = menu(d=USER_CHORD_DICT, keyslist=True, show=False,
                             pager=15, ntf="Tipo non valido",
                             # --- MODIFICA PROMPT ---
                             p=f"Filtra TIPO accordo per {get_nota(tonica_std)} (o '...'): ")

    if primary_shorthand is None:
        print("Costruzione annullata.")
        return

    figure_string = "" # Inizializza per blocco except
    nome_accordo_display_base = "" # Nome per visualizzazione
    accordo_m21 = None # Oggetto music21

    try:
        # --- MODIFICA CHIAVE: Gestione Ricerca Fuzzy ---
        if primary_shorthand == "...":
            # Chiama la funzione di ricerca fuzzy
            selected_shorthand = fuzzy_search_and_select(
                USER_CHORD_DICT, # Cerca nel dizionario degli accordi
                f"Cerca TIPO accordo per {get_nota(tonica_std)} (testo parziale): ",
                "tipo di accordo"
            )
            # Se l'utente annulla la ricerca fuzzy
            if selected_shorthand is None: 
                print("Ricerca annullata.")
                return 
            # Se la ricerca ha successo, usa la chiave trovata
            primary_shorthand = selected_shorthand 
        # --- FINE MODIFICA CHIAVE ---

        # --- Ora primary_shorthand contiene la chiave corretta ---
        
        # Crea la stringa di figura usando la fondamentale e lo shorthand
        figure_string = tonica_std + primary_shorthand
        nome_accordo_display_base = USER_CHORD_DICT.get(primary_shorthand, primary_shorthand) # Prendi il nome leggibile

        # --- Istanziazione tramite harmony.ChordSymbol (Metodo Corretto) ---
        accordo_m21 = harmony.ChordSymbol(figure_string)

        # Verifica robusta
        if accordo_m21 is None or not accordo_m21.pitches:
              # Fallback (come prima, per sicurezza)
              if primary_shorthand == "": figure_string_fallback = tonica_std + " major"; accordo_m21 = harmony.ChordSymbol(figure_string_fallback)
              elif primary_shorthand == "m": figure_string_fallback = tonica_std + " minor"; accordo_m21 = harmony.ChordSymbol(figure_string_fallback)
              elif primary_shorthand == "dim": figure_string_fallback = tonica_std + " diminished"; accordo_m21 = harmony.ChordSymbol(figure_string_fallback)
              elif primary_shorthand == "aug": figure_string_fallback = tonica_std + " augmented"; accordo_m21 = harmony.ChordSymbol(figure_string_fallback)

              if accordo_m21 is None or not accordo_m21.pitches:
                  raise ValueError(f"Music21 non è riuscito a interpretare la figura '{figure_string}'")

        # --- Estrazione delle Note ---
        note_accordo_obj = accordo_m21.pitches # Tupla di oggetti pitch.Pitch

        note_accordo_std = []
        note_accordo_formattate = []
        for p_note in note_accordo_obj:
            nota_base_std = p_note.name.replace('-', 'b')
            # Rimuovi l'ottava per MostraCorde
            nota_base_std_no_oct = ''.join(filter(lambda c: not c.isdigit(), nota_base_std))
            
            # Formattazione per la stampa (con ottava)
            nota_formattata_con_oct = get_nota(p_note.nameWithOctave.replace('-', 'b'))

            # Aggiungi solo se non è un duplicato (per manico e stampa base)
            if nota_base_std_no_oct not in note_accordo_std:
                note_accordo_std.append(nota_base_std_no_oct)
            if nota_formattata_con_oct not in note_accordo_formattate:    
                note_accordo_formattate.append(nota_formattata_con_oct)

    except Exception as e:
        print(f"\nErrore durante la creazione dell'accordo: {e}")
        if figure_string: print(f"Input tentato per music21: '{figure_string}'")
        print(f"Verifica la correttezza della fondamentale e del tipo.")
        key("Premi un tasto...")
        return # Esce dalla funzione

    # --- 4. Mostra i Risultati ---
    nome_accordo_display = f"{get_nota(tonica_std)} {nome_accordo_display_base}"
    note_str = " - ".join(note_accordo_formattate)
    print(f"\n--- Risultato Analisi (harmony.ChordSymbol) ---")
    print(f"Accordo: {nome_accordo_display}")
    print(f"Note componenti: {note_str}")
    print("---------------------------------------------")

# --- 5. Mostra sul Manico (Condizionato al numero di note) ---
    num_note = len(note_accordo_obj) # Usiamo la lista originale con gli oggetti Pitch

    if num_note <= 6:
        print(f"\n({num_note} note <= 6) Ecco dove trovare queste note sul manico:")
        print("Puoi indicare una porzione di manico (es. 0.4)")
        scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
        maninf, mansup = 0, 21
        if scelta_manico != "":
            maninf, mansup = Manlimiti(scelta_manico)

        # Usiamo note_accordo_std (nomi base senza ottava, senza duplicati)
        visualizza_note_su_manico(note_accordo_std, maninf, mansup)
        
        print("\nUsando queste poszioni, puoi trovare una diteggiatura e salvarla nella tua Chordpedia.")

    else:
        print(f"\n({num_note} note > 6) Visualizzazione sul manico non mostrata per accordi complessi.")

    # --- 6. Passa al Player Audio Teorico ---
    # Passiamo la lista originale di oggetti Pitch (note_accordo_obj) che contiene le ottave corrette ed è ordinata come generata da music21.
    if note_accordo_obj: # Assicurati che ci siano note prima di chiamare il player
        SuonaAccordoTeorico(note_accordo_obj)
    else:
        print("\nNessuna nota valida generata per l'ascolto.")
        key("Premi un tasto per tornare al menu...")
def main():
    global SCALE_CATALOG, SCALE_TYPES_DICT, USER_CHORD_DICT , archivio_modificato, impostazioni
    print(f"\nBenvenuto in Chitabry, l'App per familiarizzare con la Chitarra e studiare musica.")
    print(f"\tVersione: {VERSIONE}, di Gabriele Battaglia (IZ4APU)")
    
    carica_impostazioni()

    # --- POPOLA I DIZIONARI DINAMICI ---
    print("Analisi libreria music21 per scale e accordi...")
    SCALE_CATALOG = build_scale_catalog() # Chiama la funzione e popola il catalogo!
    temp_scale_types = {}
    for scale_info in SCALE_CATALOG: # Itera sul catalogo
        prog_id = scale_info['programmatic_id']
        paradigm = scale_info['paradigm']
        friendly_name = scale_info['friendly_name']
        unique_key = f"{paradigm}:{prog_id}" # Usa la chiave univoca
        temp_scale_types[unique_key] = friendly_name # Mappa chiave -> nome

    # Aggiungi l'opzione manuale all'inizio con chiave speciale "..."
    SCALE_TYPES_DICT = {"...": ">> Inserisci USI manualmente..."}
    SCALE_TYPES_DICT.update(temp_scale_types)
    USER_CHORD_DICT = get_user_chord_dictionary() # <-- NUOVA CHIAMATA
    print(f"Riconosciuti {len(SCALE_TYPES_DICT)} tipi di scale e {len(USER_CHORD_DICT)-1} tipi di accordi.") # -1 per 'manuale'

    num_accordi = len(impostazioni.get('chordpedia', {}))
    print(f"Le tue Tablature Accordi contengono {num_accordi} diteggiature.") 
    print("\n--- Menu Principale ---")
    
    while True:
        # Mostriamo il menu e attendiamo la scelta
        scelta = menu(d=MAINMENU, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
        
        print(f"\nHai scelto: {scelta}") # Utile per il debug e conferma
        
        if scelta == "Accordi":
            GestoreChordpedia()
        
        elif scelta == "Costruttore Accordi": # <-- NUOVO BLOCCO
            CostruttoreAccordi()
        elif scelta == "Metronomo":
            print("\nAvvio di Clitronomo...")
            aspetta(0.5)
            clitronomo.main()
            print("\n--- Ritorno al Menu Principale di Chitabry ---")
        elif scelta == "MidiStudy":
            midistudy.MidiStudyMain()
        elif scelta == "Scale":
            VisualizzaEsercitatiScala()
        elif scelta == "Flauto":
            GestoreFlauto()
        elif scelta == "Impostazioni":
            GestoreImpostazioni()
            
        elif scelta == "Nota sul manico":
            TrovaNota()
            
        elif scelta == "Trova Posizione":
            TrovaPosizione()
            
        elif scelta == "Guida":
            manuale("ChitabryMan.txt")
        
        elif scelta == "Esci" or scelta is None:
            break
            
        print("\n--- Ritorno al Menu Principale ---")

    # Uscita dal loop
    salva_impostazioni()
    print(f"Arrivederci da Chitabry versione: {VERSIONE}")
    
    aspetta(0.2) # Diamo tempo di leggere l'arrivederci
    sys.exit()

if __name__ == "__main__":
    main()