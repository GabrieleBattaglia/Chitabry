from time import sleep as aspetta
from music21 import pitch, scale, harmony
from GBUtils import dgt, menu, key
from typing import Dict
import numpy as np
import sounddevice as sd
import GBAudio
from GBAudio import FS, NoteRenderer, note_to_freq
import config
import scale_catalog


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
    
    print(_FLAUTO_INTRO)
    
    # Scegli la mappa di conversione corretta
    if config.impostazioni['nomenclatura'] == 'latino':
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
def visualizza_note_su_manico(lista_note: list[str], maninf: int = 0, mansup: int = None):
    if mansup is None: mansup = config.NUM_TASTI
    """
    Funzione helper unificata per visualizzare un elenco di note sul manico.
    Riceve un elenco di note STANDARD (es. ['C', 'E', 'G']) 
    e i limiti del manico, quindi stampa il diagramma.
    """
    
    # 1. Costruisce una struttura dati {corda: [tasti...]}
    #    Questo dizionario conterrà solo le note che ci interessano.
    manico_filtrato = {c: [] for c in range(config.NUM_CORDE, 0, -1)}
    
    # Nota: lista_note contiene nomi base (es. 'C#', 'Bb', 'A')
    # Normalizziamo le note bemolli nei rispettivi diesis per compatibilità con config.CORDE
    note_da_cercare = set()
    mappa_bemolli = {
        'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#',
        'C-': 'B', 'D-': 'C#', 'E-': 'D#', 'F-': 'E', 'G-': 'F#', 'A-': 'G#', 'B-': 'A#'
    }
    for n in lista_note:
        n_clean = n.replace('-', 'b')
        note_da_cercare.add(mappa_bemolli.get(n_clean, n_clean))

    # 2. Itera su config.CORDE (l'intero manico) UNA SOLA VOLTA
    for posizione, nota_std_con_ottava in config.CORDE.items():
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
    for corda in range(config.NUM_CORDE, 0, -1):
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
        for i, (k_elem, display_name) in enumerate(match_list):
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


def get_nota(nota_std_music21):
    """
    Converte una nota standard (es. "C#4", "Eb", "G~5", "A``")
    nella notazione scelta dall'utente (latina o anglosassone),
    preservando i simboli microtonali (~, `` , ~~, ``` ``) alla fine.
    """
    if not isinstance(nota_std_music21, str):
        return str(nota_std_music21) # Restituisci come stringa se non è una stringa

    # Mappa di conversione base
    if config.impostazioni['nomenclatura'] == 'latino':
        mappa = config.STD_TO_LATINO
    else:
        mappa = config.STD_TO_ANGLO

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
    Usa il PolyphonicPlayer per uno stream continuo e mixaggio indipendente per corda.
    """
    print("\nAscolta le corde:")
    max_keys = min(config.NUM_CORDE, 10)
    keys_str = "1 a " + (str(max_keys) if max_keys < 10 else "0")
    print(f"Tasti da {keys_str}, (A) pennata in levare, (Q) pennata in battere")
    print("ESC per uscire.")
    
    suono_attivo_key = 'suono_1'
    suono = config.impostazioni[suono_attivo_key]
    hardness = suono.get('pluck_hardness', 0.6)
    damping = suono.get('damping_factor', 0.997)
    pick_pos = suono.get('pick_position', 0.15)
    bright = suono.get('brightness', 0.4)
    dur = suono.get('dur_accordi', 9.0)
    vol = suono.get('volume', 0.35)
    s_kind = suono.get('kind', 1)
    s_adsr = suono.get('adsr', [0,0,0,0])
    
    # Crea il player polifonico e i renderer
    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=config.NUM_CORDE)
    renderers = [GBAudio.NoteRenderer(fs=GBAudio.FS) for _ in range(config.NUM_CORDE)]
    
    note_da_suonare = []
    note_freq = []
    note_pan = []
    note_names_display = []

    # Pre-configura i parametri
    for i in range(config.NUM_CORDE):
        corda = 6 - i
        tasto = tablatura[i]
        pan_val = -0.8 + (i * 0.32)
        note_pan.append(pan_val)
        poly_player.set_pan(i, pan_val)
        
        freq = 0.0
        if tasto.isdigit() and f"{corda}.{tasto}" in config.CORDE:
            nota_std = config.CORDE[f"{corda}.{tasto}"]
            freq = note_to_freq(nota_std)
        
        note_freq.append(freq)
        note_da_suonare.append(freq > 0) 
        
        if 'pluck_hardness' in suono:
            renderers[i].set_params(freq, dur, vol, pan_val, 
                                    pluck_hardness=hardness, damping_factor=damping,
                                    pick_position=pick_pos, brightness=bright)
        else:
            renderers[i].set_params(freq, dur, vol, pan_val, kind=s_kind, adsr_list=s_adsr)
        
        if tasto.isdigit() and f"{corda}.{tasto}" in config.CORDE:
            note_names_display.append(get_nota(config.CORDE[f"{corda}.{tasto}"]))
        else:
            note_names_display.append("X")
            
    note_prompt_str = " - ".join(note_names_display)
    poly_player.start()
    
    try:
        while True:
            print(f"Note: {note_prompt_str} (Premi 1-{min(config.NUM_CORDE, 10)}, A, Q, SPAZIO, ESC): " + " "*10, end="\r", flush=True)
            scelta = key().lower()
            
            if scelta.isdigit():
                key_int = int(scelta) if scelta != '0' else 10
                if 1 <= key_int <= min(config.NUM_CORDE, 10):
                    corda_idx_py = key_int - 1
                    if note_da_suonare[corda_idx_py]:
                        # Ottieni l'audio mono renderizzato
                        note_audio_stereo = renderers[corda_idx_py].render()
                        if note_audio_stereo.size > 0:
                            # Prende solo il canale L o divide per il mix
                            # NoteRenderer outputta stereo. Selezioniamo il canale sinistro senza panning, perché il panning lo fa il PolyphonicPlayer.
                            # Dobbiamo estrarre l'audio mono prima del panning di NoteRenderer
                            # Oppure modifichiamo provvisoriamente NoteRenderer per outputtare mono o resettiamo il pan_l a 1.0.
                            # Ma in PolyphonicPlayer, pluck si aspetta audio_mono.
                            # NoteRenderer resitituisce: wave * envelope, poi lo panna. 
                            # Se mettiamo pan_val a 0 in renderers e prendiamo canale 0 (mono=stereo/0.707):
                            mono_audio = note_audio_stereo[:, 0] / renderers[corda_idx_py].pan_l if renderers[corda_idx_py].pan_l != 0 else note_audio_stereo[:, 0]
                            poly_player.pluck(string_idx=corda_idx_py, audio_mono=mono_audio)
                            
            elif scelta == ' ':
                suono_attivo_key = 'suono_2' if suono_attivo_key == 'suono_1' else 'suono_1'
                suono = config.impostazioni[suono_attivo_key]
                hardness = suono.get('pluck_hardness', 0.6)
                damping = suono.get('damping_factor', 0.997)
                pick_pos = suono.get('pick_position', 0.15)
                bright = suono.get('brightness', 0.4)
                dur = suono.get('dur_accordi', 9.0)
                vol = suono.get('volume', 0.35)
                s_kind = suono.get('kind', 1)
                s_adsr = suono.get('adsr', [0,0,0,0])
                
                for i in range(config.NUM_CORDE):
                    if note_da_suonare[i]:
                        if 'pluck_hardness' in suono:
                            renderers[i].set_params(note_freq[i], dur, vol, note_pan[i], 
                                                    pluck_hardness=hardness, damping_factor=damping,
                                                    pick_position=pick_pos, brightness=bright)
                        else:
                            renderers[i].set_params(note_freq[i], dur, vol, note_pan[i], kind=s_kind, adsr_list=s_adsr)
                print(f"\n[Suono: {suono['descrizione']}]" + " "*20)
                        
            elif scelta == chr(27): # ESC
                print("\nUscita dal menù ascolto.")
                break 
                
            elif scelta == 'a' or scelta == 'q': # Pennata
                strum_delay_sec = 0.07
                note_order = range(config.NUM_CORDE) if scelta == 'q' else range(config.NUM_CORDE - 1, -1, -1)
                
                for i in note_order:
                    if note_da_suonare[i]:
                        note_audio_stereo = renderers[i].render()
                        if note_audio_stereo.size > 0:
                            mono_audio = note_audio_stereo[:, 0] / renderers[i].pan_l if renderers[i].pan_l != 0 else note_audio_stereo[:, 0]
                            poly_player.pluck(string_idx=i, audio_mono=mono_audio)
                        aspetta(strum_delay_sec)
                        
            else:
                print("Comando non valido. Premi 1-6, A, Q, SPAZIO o ESC.")
    finally:
        poly_player.stop()
    return

def SuonaAccordoTeorico(note_pitch_list):
    """
    Player audio per accordi teorici generati da CostruttoreAccordi.
    Gestisce fino a 10 note, ordina per altezza, assegna panning
    (grave=dx, acuto=sx) e mappa i tasti 1-0. Usa PolyphonicPlayer per polifonia reale.
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
        except TypeError:
             print("Impossibile ordinare le note.")
             return


    # 2. Limita a un massimo di 10 note
    if len(sorted_pitches) > 10:
        print(f"Attenzione: L'accordo ha {len(sorted_pitches)} note. Suono solo le 10 più gravi.")
        pitches_to_play = sorted_pitches[:10]
    else:
        pitches_to_play = sorted_pitches
        
    num_notes = len(pitches_to_play)

    # 3. Prepara parametri audio
    suono_attivo_key = 'suono_1'
    suono = config.impostazioni[suono_attivo_key]
    dur = suono.get('dur_accordi', 9.0)
    vol = suono.get('volume', 0.35)
    hardness = suono.get('pluck_hardness', 0.6)
    damping = suono.get('damping_factor', 0.997)
    pick_pos = suono.get('pick_position', 0.15)
    bright = suono.get('brightness', 0.4)
    s_kind = suono.get('kind', 1)
    s_adsr = suono.get('adsr', [0,0,0,0])

    # 4. Calcola Panning (Grave=-0.8 sinistra -> Acuto=+0.8 destra)
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
        key_map['0'] = 9 # Tasto '0' -> indice 9 (decima nota)            
        
    # 6. Prepara Renderers, Player e dati note
    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=num_notes)
    renderers = [GBAudio.NoteRenderer(fs=GBAudio.FS) for _ in range(num_notes)]
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
        poly_player.set_pan(i, pan_val)
        
        if 'pluck_hardness' in suono:
            renderers[i].set_params(freq, dur, vol, pan_val, 
                                    pluck_hardness=hardness, damping_factor=damping,
                                    pick_position=pick_pos, brightness=bright)        
        else:
            renderers[i].set_params(freq, dur, vol, pan_val, kind=s_kind, adsr_list=s_adsr)
            
        # Stampa info nota (con tasto associato)
        tasto_associato = "N/A"
        for key_char, index in key_map.items():
            if index == i:
                tasto_associato = key_char
                break
        print(f"  Tasto '{tasto_associato}': {nota_display} (Pan: {pan_val:.2f})")

    poly_player.start()
    
    try:
        # 7. Loop Interattivo
        print("\nPremi tasti 1-0 per note singole.")
        print("Q = Strum Giù (Grave->Acuta / Dx->Sx)")
        print("A = Strum Su (Acuta->Grave / Sx->Dx)")
        print("SPAZIO = Cambia Suono")
        print("ESC = Esci")

        note_prompt_str = " ".join(reversed(note_names_display))

        while True:
            print(f"\nNote: {note_prompt_str}): ", end="", flush=True)
            scelta = key().lower()

            if scelta in key_map: # Tasto nota singola (1-0)
                note_idx = key_map[scelta]
                if 0 <= note_idx < num_notes:
                    if note_freqs[note_idx] > 0:
                        note_audio_stereo = renderers[note_idx].render()
                        if note_audio_stereo.size > 0:
                            mono_audio = note_audio_stereo[:, 0] / renderers[note_idx].pan_l if renderers[note_idx].pan_l != 0 else note_audio_stereo[:, 0]
                            poly_player.pluck(string_idx=note_idx, audio_mono=mono_audio)
                    else:
                        print("Nota non valida o senza frequenza.")
                else:
                     print("Indice nota non valido?") # Debug
                     
            elif scelta == ' ':
                suono_attivo_key = 'suono_2' if suono_attivo_key == 'suono_1' else 'suono_1'
                suono = config.impostazioni[suono_attivo_key]
                dur = suono.get('dur_accordi', 9.0)
                vol = suono.get('volume', 0.35)
                hardness = suono.get('pluck_hardness', 0.6)
                damping = suono.get('damping_factor', 0.997)
                pick_pos = suono.get('pick_position', 0.15)
                bright = suono.get('brightness', 0.4)
                s_kind = suono.get('kind', 1)
                s_adsr = suono.get('adsr', [0,0,0,0])
                
                for i in range(num_notes):
                    if 'pluck_hardness' in suono:
                        renderers[i].set_params(note_freqs[i], dur, vol, pan_values[i], 
                                                pluck_hardness=hardness, damping_factor=damping,
                                                pick_position=pick_pos, brightness=bright)
                    else:
                        renderers[i].set_params(note_freqs[i], dur, vol, pan_values[i], kind=s_kind, adsr_list=s_adsr)
                print(f"\n[Suono impostato su: {suono['descrizione']}]")

            elif scelta == chr(27): # ESC
                print("\nUscita dal player accordo.")
                break

            elif scelta == 'q' or scelta == 'a': # Strum
                strum_delay_sec = 0.05 # Più veloce per accordi
                note_order = range(num_notes) if scelta == 'q' else range(num_notes - 1, -1, -1)
                
                for i in note_order:
                    if note_freqs[i] > 0:
                        note_audio_stereo = renderers[i].render()
                        if note_audio_stereo.size > 0:
                            mono_audio = note_audio_stereo[:, 0] / renderers[i].pan_l if renderers[i].pan_l != 0 else note_audio_stereo[:, 0]
                            poly_player.pluck(string_idx=i, audio_mono=mono_audio)
                        aspetta(strum_delay_sec)

            else:
                print("Comando non valido.")
    finally:
        poly_player.stop()

    return # Fine funzione SuonaAccordoTeorico


def Manlimiti(s):
    """
    Riceve stringa "N-N", restituisce 2 int per i limiti del manico.
    (Logica identica all'originale, ma più robusta)
    """
    if "-" not in s or " " in s:
        print("Errore: formato non valido. Usare N-N (es. 0-4).")
        return 0, config.NUM_TASTI
    
    s2 = s.split("-")
    if len(s2) != 2 or not s2[0].isdigit() or not s2[1].isdigit():
        print("Errore: inserire solo valori numerici separati da un trattino.")
        return 0, config.NUM_TASTI
        
    maninf, mansup = int(s2[0]), int(s2[1])
    
    # Assicura che i limiti siano in ordine
    if maninf > mansup:
        print(f"Limiti invertiti. Uso {mansup}-{maninf}.")
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


def MostraCorde(nota_std, rp=False, maninf=0, mansup=None):
    if mansup is None: mansup = config.NUM_TASTI
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
    for k, v in config.CORDE.items():
        ks = k.split(".") 
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


def VisualizzaEsercitatiScala():
    """ Versione Finale Ibrida con gestione microtoni completa e indentazione corretta """
    suono_attivo_key = 'suono_2'

    print("\n--- Visualizza ed Esercitati sulle Scale (music21 - Catalogo) ---")

# --- 1. Scegli Tonica ---
    # Dizionario {Mostra_Utente -> Ritorna_Standard}
    mappa_toniche = {}
    if config.impostazioni['nomenclatura'] == 'latino':
        # Inverti: {'DO': 'C', 'DO#': 'C#', ...}
        mappa_toniche = {lat: std for std, lat in config.STD_TO_LATINO.items() if len(std) <= 2 and std in config.NOTE_STD}
    else:
        # Mantieni: {'C': 'C', 'C#': 'C#', ...}
        mappa_toniche = {anglo: std for std, anglo in config.STD_TO_ANGLO.items() if len(std) <= 2 and std in config.NOTE_STD}
    
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
    selected_key = menu(d=scale_catalog.SCALE_TYPES_DICT, keyslist=True, show=False,
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
    poly_player = None

    try:
        # --- Gestione selezione: Menu diretto o Ricerca Fuzzy ---
        if selected_key == "...":
            # Esegui ricerca fuzzy
            selected_key_from_fuzzy = fuzzy_search_and_select(
                scale_catalog.SCALE_TYPES_DICT,
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
            nome_scala_display_base = scale_catalog.SCALE_TYPES_DICT.get(selected_key, scale_id)
            usi_string = f"{paradigm}:{tonica_std_con_ottava}:{scale_id}"
        except ValueError:
            print(f"Errore: Chiave selezione ('{selected_key}') malformata.")
            key("Premi un tasto...")
            return

        # --- Istanziazione tramite Factory USI ---
        scala_m21 = scale_catalog.get_scale_from_usi(usi_string)

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
            pitch.Pitch(p_start.step + str(end_octave))
        except Exception as pitch_err: #<<<--- EXCEPT INTERNO 1 ---<<<
            print(f"Errore nella definizione dell'intervallo di ottava: {pitch_err}")
            p_start = pitch.Pitch(tonica_std_con_ottava)
            pitch.Pitch(tonica_std_base + "5")

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

        # --- 5. Mostra su Manico / Diteggiature (INDENTATO) ---
        if is_microtonal_scale:
            print("\nVisualizzazione sul manico approssimata per scale microtonali.")
        if not note_scala_std_asc: # Se non ci sono note standard
            print("\nImpossibile mostrare sul manico: nessuna nota standard generata.")
        else:
            print("\nPuoi indicare una porzione di manico per cercare le diteggiature (es. 5-8).")
            scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
            maninf, mansup = 0, config.NUM_TASTI
            if scelta_manico != "": 
                maninf, mansup = Manlimiti(scelta_manico)
                
                # Se l'utente specifica un box e non è microtonale, usiamo il pathfinding
                if mansup - maninf <= 14 and not is_microtonal_scale:
                    print(f"\nCalcolo delle migliori diteggiature nel box {maninf}-{mansup} in corso...")
                    
                    try:
                        strum_attivo = config.impostazioni.get("strumento_attivo", "Chitarra")
                        dati_strum = config.impostazioni.get("strumenti", {}).get(strum_attivo, {})
                        accordatura_lista = dati_strum.get("accordatura", ["E2", "A2", "D3", "G3", "B3", "E4"])
                        num_tasti_strum = int(dati_strum.get("tasti", 22))
                        
                        tuning_midi = [pitch.Pitch(n).midi for n in accordatura_lista]
                        
                        from strumento import InstrumentModel
                        from generatore_scale import ScalePathfinder
                        model_strum = InstrumentModel(tuning_midi=tuning_midi, num_frets=num_tasti_strum)
                        
                        target_pc_list = []
                        if isinstance(scala_m21, scale.ScalaScale) or isinstance(scala_m21, scale.ConcreteScale):
                             for p in scala_m21.pitches:
                                if isinstance(p, pitch.Pitch):
                                    target_pc_list.append(p.pitchClass)
                        else:
                             # Fallback extraction
                             for p_name in note_scala_std_asc:
                                 target_pc_list.append(pitch.Pitch(p_name).pitchClass)
                                 
                        root_pc = pitch.Pitch(tonica_std_con_ottava).pitchClass
                        
                        solver = ScalePathfinder(model_strum, target_pc_list, root_pc)
                        
                        from GBUtils import enter_escape
                        priorita_caged = enter_escape("Desideri dare priorità alla forma CAGED? (INVIO per Sì, ESC per forme a 3 note per corda): ")
                        
                        sols = solver.find_paths(maninf, mansup, priorita_caged=priorita_caged)
                        
                        if not sols:
                            print("\nNessuna diteggiatura fisicamente possibile trovata per questa scala nel box specificato.")
                        else:
                            top_n = min(5, len(sols))
                            print(f"\n--- Le {top_n} migliori diteggiature per {nome_scala_display} ---")
                            
                            menu_diteggiature = {}
                            soluzioni_map = {}
                            
                            for i in range(top_n):
                                s_dict = sols[i]
                                meta = s_dict['meta']
                                path = s_dict['path']
                                
                                diff_gen = meta['difficolta_score_perc']
                                diff_stretch = meta['difficolta_stretch_perc']
                                nps = meta['nps']
                                nps_list = [nps[str_idx] for str_idx in range(model_strum.num_strings)]
                                
                                chiave_menu = str(i+1)
                                menu_diteggiature[chiave_menu] = f"Difficoltà: {diff_gen}% | Stretch: {diff_stretch}% | Note per corda: {nps_list}"
                                
                                dettagli = f"Difficoltà Generale: {diff_gen}% | Estensione: {diff_stretch}% ({meta['stretch_tasti']} tasti)\n"
                                
                                note_per_corda = {s: {'f': [], 'd': [], 'n': []} for s in range(model_strum.num_strings)}
                                for idx_path, p_dict in enumerate(path):
                                    s_idx = p_dict['string']
                                    f_val = p_dict['fret']
                                    dito_val = meta['fingering'][idx_path] if meta['fingering'] else 0
                                    
                                    nota_obj = pitch.Pitch(midi=p_dict['midi'])
                                    nota_nome = get_nota(nota_obj.nameWithOctave.replace('-', 'b'))
                                    
                                    note_per_corda[s_idx]['f'].append(str(f_val))
                                    note_per_corda[s_idx]['d'].append(str(dito_val))
                                    note_per_corda[s_idx]['n'].append(nota_nome)
                                
                                dettagli += "Posizioni (dalla corda più grave):\n"
                                for string_idx in range(model_strum.num_strings):
                                    corda_num = model_strum.num_strings - string_idx
                                    if note_per_corda[string_idx]['f']:
                                        f_str = ", ".join(note_per_corda[string_idx]['f'])
                                        d_str = ", ".join(note_per_corda[string_idx]['d'])
                                        n_str = ", ".join(note_per_corda[string_idx]['n'])
                                        dettagli += f"Corda {corda_num}: tasti ({f_str}), dita ({d_str}), note ({n_str});\n"
                                
                                soluzioni_map[chiave_menu] = dettagli
                            
                            if top_n == 1:
                                chiave = list(soluzioni_map.keys())[0]
                                print("\n--- Dettagli dell'unica Forma Trovata ---")
                                print(soluzioni_map[chiave].rstrip('\n'))
                                key("Premi un tasto per proseguire all'esercizio audio...")
                            else:
                                menu_diteggiature["p"] = ">> Prosegui all'esercizio audio"
                                while True:
                                    menu_ordinato = dict(sorted(menu_diteggiature.items(), key=lambda item: (0 if item[0] == 'p' else 1, int(item[0]) if item[0].isdigit() else 999)))
                                    scelta_tab = menu(d=menu_ordinato, keyslist=True, show=True, numbered=False, ntf="Scelta non valida", p="Scegli il numero per i dettagli (o 'p' per proseguire): ")
                                    
                                    if scelta_tab is None or scelta_tab == 'p':
                                        break
                                        
                                    print(f"\n--- Dettagli Forma {scelta_tab} ---")
                                    print(soluzioni_map[scelta_tab].rstrip('\n'))
                                    key("Premi un tasto per tornare alle opzioni...")
                                
                    except Exception as e:
                        print(f"\nErrore durante il calcolo delle diteggiature: {e}")
                        visualizza_note_su_manico(note_scala_std_asc, maninf, mansup)
                else:
                    visualizza_note_su_manico(note_scala_std_asc, maninf, mansup)
            else:
                visualizza_note_su_manico(note_scala_std_asc, maninf, mansup)

        # --- 6. Loop Esercizio (INDENTATO) ---
        if not note_per_audio_asc and not note_per_audio_desc:
            print("\nNessuna nota audio generata per l'esercizio.")
            key("Premi un tasto per tornare al menu...")
        else:
            print("\n--- Menu Esercizio Scala ---\n\tPremi '?' per aiuto.")
            bpm = config.impostazioni['default_bpm']
            loop_attivo = False
            loop_count = 1
            ultima_direzione = 'a'
            menu_esercizio = {"1-8": "Suona nota singola", "a": "Ascolta ascendente", "d": "Ascolta discendente", "l": "Attiva/Disattiva Loop", "b": "Imposta BPM", "m": "Attiva/Disattiva Metronomo", "i": "Indietro"}
            loop_messaggio_stampato = False

            num_notes = len(note_per_audio_asc)
            poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=num_notes + 1)
            poly_player.set_pan(num_notes, 0.0) # Metronomo centrato
            renderers = [GBAudio.NoteRenderer(fs=GBAudio.FS) for _ in range(num_notes)]

            # Caricamento del preset di metronomo attivo
            metronomo_attivo = False
            import clitronomo
            import sys
            import io
            
            old_stdout = sys.stdout
            sys.stdout = io.StringIO()
            try:
                preset_mgr = clitronomo.PresetManager()
                _, last_state = preset_mgr.get_last_used_preset()
            except Exception:
                last_state = None
            finally:
                sys.stdout = old_stdout

            if last_state:
                config_accento = last_state.get('config_accento')
                config_tick = last_state.get('config_tick')
            else:
                config_accento = {
                    "beep_duration_ms": 70, "volume_perc": 50, "attack_ms": 5,
                    "decay_ms": 8, "frequency_hz": 915.0
                }
                config_tick = {
                    "beep_duration_ms": 40, "volume_perc": 35, "attack_ms": 5,
                    "decay_ms": 12, "frequency_hz": 550.0
                }

            accent_beep = clitronomo.genera_suono_mono_int16(config_accento).astype(np.float32) / 32767.0
            tick_beep = clitronomo.genera_suono_mono_int16(config_tick).astype(np.float32) / 32767.0

            def aggiorna_renderers(suono_key):
                suono = config.impostazioni[suono_key]
                hardness = suono.get('pluck_hardness', 0.6)
                damping = suono.get('damping_factor', 0.997)
                pick_pos = suono.get('pick_position', 0.15)
                bright = suono.get('brightness', 0.4)
                dur = suono.get('dur_accordi', 9.0)
                vol = suono.get('volume', 0.35)
                s_kind = suono.get('kind', 1)
                s_adsr = suono.get('adsr', [0,0,0,0])
                
                for i in range(num_notes):
                    freq = note_per_audio_asc[i]
                    if freq is None:
                        freq = 0.0
                    pan_val = -0.8
                    if num_notes > 1:
                        pan_val = -0.8 + i * (1.6 / (num_notes - 1))
                    poly_player.set_pan(i, pan_val)
                    
                    if 'pluck_hardness' in suono:
                        renderers[i].set_params(freq, dur, vol, pan_val, 
                                                pluck_hardness=hardness, damping_factor=damping,
                                                pick_position=pick_pos, brightness=bright)
                    else:
                        renderers[i].set_params(freq, dur, vol, pan_val, kind=s_kind, adsr_list=s_adsr)

            poly_player.start()
            aggiorna_renderers(suono_attivo_key)

            key_map_scala = {str(i+1): i for i in range(min(num_notes, 9))}
            if num_notes >= 10:
                key_map_scala['0'] = 9

            nota_precedente_loop = None

            while True: # Inizio Loop Esercizio
                scelta_raw = ""
                
                if loop_attivo: # Modalità Loop
                    if not loop_messaggio_stampato:
                        print(f"\rLoop ATTIVO. Premi 'L' per fermare.{' '*20}\r", end="", flush=True)
                        loop_messaggio_stampato = True
                    
                    note_scala_loop_str = note_asc_str if ultima_direzione == 'a' else note_desc_str
                    suono_abbrev = "S2" if suono_attivo_key == 'suono_2' else "S1"
                    dir_abbrev = "asc" if ultima_direzione == 'a' else "dis"
                    print(f"\r{note_scala_loop_str} | L:{loop_count} {dir_abbrev} {suono_abbrev}{' '*15}\r", end="", flush=True)
                    
                    seq = list(range(num_notes)) if ultima_direzione == 'a' else list(range(num_notes - 1, -1, -1))
                    
                    if metronomo_attivo:
                        extra_beats = (4 - (num_notes % 4)) % 4
                    else:
                        extra_beats = 0
                        
                    dur_step = 60.0 / bpm
                    
                    interrotto = False
                    beat_in_measure = 0
                    for idx_step in range(num_notes + extra_beats):
                        if nota_precedente_loop is not None:
                            poly_player.mute(nota_precedente_loop)
                            
                        if idx_step < num_notes:
                            idx = seq[idx_step]
                            freq = note_per_audio_asc[idx]
                            if freq is not None and freq > 0:
                                note_audio_stereo = renderers[idx].render()
                                if note_audio_stereo.size > 0:
                                    mono_audio = note_audio_stereo[:, 0] / renderers[idx].pan_l if renderers[idx].pan_l != 0 else note_audio_stereo[:, 0]
                                    poly_player.pluck(string_idx=idx, audio_mono=mono_audio)
                                    nota_precedente_loop = idx
                        else:
                            nota_precedente_loop = None
                                
                        if metronomo_attivo:
                            is_accent = (beat_in_measure % 4 == 0)
                            click_audio = accent_beep if is_accent else tick_beep
                            if click_audio.size > 0:
                                poly_player.pluck(string_idx=num_notes, audio_mono=click_audio)
                            beat_in_measure += 1

                        passi = int(dur_step / 0.02)
                        for _ in range(passi):
                            tasto = key(attesa=0.02)
                            if tasto:
                                tasto_lower = tasto.lower()
                                if tasto_lower == 'l':
                                    loop_attivo = False
                                    poly_player.mute()
                                    nota_precedente_loop = None
                                    print(f"\rLoop disattivato.{' '*40}\r", end="", flush=True)
                                    loop_messaggio_stampato = False
                                    interrotto = True
                                    break
                                elif tasto_lower == ' ':
                                    suono_attivo_key = 'suono_2' if suono_attivo_key == 'suono_1' else 'suono_1'
                                    aggiorna_renderers(suono_attivo_key)
                                    suono_abbrev = "S2" if suono_attivo_key == 'suono_2' else "S1"
                                    dir_abbrev = "asc" if ultima_direzione == 'a' else "dis"
                                    print(f"\r{note_scala_loop_str} | L:{loop_count} {dir_abbrev} {suono_abbrev}{' '*15}\r", end="", flush=True)
                                elif tasto == chr(27):
                                    loop_attivo = False
                                    poly_player.mute()
                                    nota_precedente_loop = None
                                    interrotto = True
                                    break
                        if interrotto:
                            break
                        
                        rimanente = dur_step - (passi * 0.02)
                        if rimanente > 0:
                            aspetta(rimanente)
                            
                    if interrotto:
                        if not loop_attivo and tasto == chr(27):
                            break
                        continue
                    
                    loop_count += 1
                    
                else: # Modalità Menu Interattivo
                    loop_messaggio_stampato = False
                    note_da_mostrare = note_asc_str if ultima_direzione == 'a' else note_desc_str
                    suono_abbrev = "S2" if suono_attivo_key == 'suono_2' else "S1"
                    dir_abbrev = "asc" if ultima_direzione == 'a' else "dis"
                    print(f"\r{note_da_mostrare if note_da_mostrare else '(vuota)'} | {dir_abbrev} {suono_abbrev}{' (M)' if metronomo_attivo else ''} (1-8, A, D, L, B, M, SPAZIO, ?, ESC):\r", end="", flush=True)
                    
                    scelta_raw = key()
                    if not scelta_raw:
                        continue
                    scelta_lower = scelta_raw.lower()
                    
                    if scelta_lower == chr(27):
                        break
                    elif scelta_lower == '?':
                        print("\n--- Aiuto Esercizio Scala ---")
                        for k, v in menu_esercizio.items():
                            print(f"  Tasto '{k}': {v}")
                        print("  Tasto 'SPAZIO': Cambia Suono")
                        print("  Tasto 'ESC': Torna al menu principale")
                        print("-----------------------------\n")
                        continue
                    elif scelta_lower == 'm':
                        metronomo_attivo = not metronomo_attivo
                        stato_metro = "ATTIVO" if metronomo_attivo else "DISATTIVATO"
                        print(f"\rMetronomo {stato_metro} per l'esercizio.{' '*20}")
                        continue
                    elif scelta_lower == ' ':
                        suono_attivo_key = 'suono_2' if suono_attivo_key == 'suono_1' else 'suono_1'
                        aggiorna_renderers(suono_attivo_key)
                        continue
                    elif scelta_lower in key_map_scala:
                        idx = key_map_scala[scelta_lower]
                        freq = note_per_audio_asc[idx]
                        if freq is not None and freq > 0:
                            note_audio_stereo = renderers[idx].render()
                            if note_audio_stereo.size > 0:
                                mono_audio = note_audio_stereo[:, 0] / renderers[idx].pan_l if renderers[idx].pan_l != 0 else note_audio_stereo[:, 0]
                                poly_player.pluck(string_idx=idx, audio_mono=mono_audio)
                        continue
                    elif scelta_lower == 'l':
                        loop_attivo = True
                        loop_count = 1
                        nota_precedente_loop = None
                        continue
                    elif scelta_lower == 'b':
                        nuovo_bpm = dgt(f"\rNuovi BPM (attuale: {bpm}): ", kind='i', imin=20, imax=300, default=bpm)
                        if nuovo_bpm != bpm:
                            bpm = nuovo_bpm
                            config.impostazioni['default_bpm'] = bpm
                            config.archivio_modificato = True
                            print(f"\rBPM predefiniti aggiornati a {bpm}.{' '*20}")
                            aggiorna_renderers(suono_attivo_key)
                        continue
                    elif scelta_lower == 'a' or scelta_lower == 'd':
                        ultima_direzione = scelta_lower
                        seq = list(range(num_notes)) if scelta_lower == 'a' else list(range(num_notes - 1, -1, -1))
                        
                        if metronomo_attivo:
                            extra_beats = (4 - (num_notes % 4)) % 4
                        else:
                            extra_beats = 0
                            
                        dur_step = 60.0 / bpm
                        
                        nota_precedente_singolo = None
                        interrotto = False
                        beat_in_measure = 0
                        
                        for idx_step in range(num_notes + extra_beats):
                            if nota_precedente_singolo is not None:
                                poly_player.mute(nota_precedente_singolo)
                            
                            if idx_step < num_notes:
                                idx = seq[idx_step]
                                freq = note_per_audio_asc[idx]
                                if freq is not None and freq > 0:
                                    note_audio_stereo = renderers[idx].render()
                                    if note_audio_stereo.size > 0:
                                        mono_audio = note_audio_stereo[:, 0] / renderers[idx].pan_l if renderers[idx].pan_l != 0 else note_audio_stereo[:, 0]
                                        poly_player.pluck(string_idx=idx, audio_mono=mono_audio)
                                        nota_precedente_singolo = idx
                            else:
                                nota_precedente_singolo = None
                                    
                            if metronomo_attivo:
                                is_accent = (beat_in_measure % 4 == 0)
                                click_audio = accent_beep if is_accent else tick_beep
                                if click_audio.size > 0:
                                    poly_player.pluck(string_idx=num_notes, audio_mono=click_audio)
                                beat_in_measure += 1

                            passi = int(dur_step / 0.02)
                            for _ in range(passi):
                                tasto = key(attesa=0.02)
                                if tasto:
                                    tasto_lower = tasto.lower()
                                    if tasto_lower == ' ':
                                        suono_attivo_key = 'suono_2' if suono_attivo_key == 'suono_1' else 'suono_1'
                                        aggiorna_renderers(suono_attivo_key)
                                        suono_abbrev = "S2" if suono_attivo_key == 'suono_2' else "S1"
                                        dir_abbrev = "asc" if ultima_direzione == 'a' else "dis"
                                        print(f"\r{note_da_mostrare if note_da_mostrare else '(vuota)'} | {dir_abbrev} {suono_abbrev}{' '*15}\r", end="", flush=True)
                                    elif tasto == chr(27):
                                        poly_player.mute()
                                        interrotto = True
                                        break
                            if interrotto:
                                break
                            
                            rimanente = dur_step - (passi * 0.02)
                            if rimanente > 0:
                                aspetta(rimanente)
                        continue

        print("Fine esercizio.") 

    # --- Blocchi except per il try principale (correttamente allineati) ---
    except (scale_catalog.InvalidUSIFormatError, scale_catalog.UnknownScaleError, scale_catalog.ScaleException) as e:
        print(f"\nErrore nella generazione della scala: {e}")
        key("Premi un tasto...")
    except Exception as e:
        print(f"\nErrore imprevisto durante la generazione della scala: {e}")
        if usi_string: print(f"USI tentato: '{usi_string}'")
        key("Premi un tasto...")
    finally:
        if poly_player is not None:
            poly_player.stop()
# --- Funzioni Segnaposto (Stub per Fase 2) ---


def ModificaSuono(suono_key):
    """
    Funzione helper per modificare i parametri di 'suono_1' o 'suono_2'.
    Gestisce i diversi parametri per ogni tipo di suono.
    """
    
    suono = config.impostazioni[suono_key]
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

        # 3. Modifica pick_position (scalato 1-10)
        current_pick_float = suono.get('pick_position', 0.15)
        # Mappa inversa: [0.01, 0.5] -> [1, 10]
        current_pick_int = int(round(1 + (np.clip(current_pick_float, 0.01, 0.5) - 0.01) * (9.0 / 0.49)))
        
        pick_prompt = f"Posizione Plettro (1=Ponte/Twang, 10=Manico/Caldo) (attuale: {current_pick_int}): "
        new_pick_int = dgt(pick_prompt, kind='i', imin=1, imax=10, default=current_pick_int)
        
        # Mappa [1, 10] -> [0.01, 0.5]
        suono['pick_position'] = 0.01 + (new_pick_int - 1) * (0.49 / 9.0)

        # 4. Modifica brightness (scalato 1-10)
        current_bright_float = suono.get('brightness', 0.4)
        # Mappa inversa: [0.0, 1.0] -> [1, 10]
        current_bright_int = int(round(1 + np.clip(current_bright_float, 0.0, 1.0) * 9.0))
        
        bright_prompt = f"Brillantezza (1=Scuro, 10=Tagliente) (attuale: {current_bright_int}): "
        new_bright_int = dgt(bright_prompt, kind='i', imin=1, imax=10, default=current_bright_int)
        
        # Mappa [1, 10] -> [0.0, 1.0]
        suono['brightness'] = (new_bright_int - 1) * (1.0 / 9.0)

        # 5. Modifica Durata Massima (come prima)
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
    config.archivio_modificato = True
    key("Premi un tasto per continuare...")

def GestoreStrumenti():
    """Gestisce la scelta, aggiunta e rimozione degli strumenti."""
    print("\n--- Gestore Strumenti ---")
    
    while True:
        strumenti = config.impostazioni.get('strumenti', {})
        strum_attivo = config.impostazioni.get('strumento_attivo')
        
        # Menu
        menu_strum = {
            's': f"Seleziona strumento attivo (Attuale: {strum_attivo})",
            'a': "Aggiungi nuovo strumento",
            'e': "Elimina strumento"
        }
        
        scelta = menu(d=menu_strum, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
        
        if scelta == 's':
            print("\nSeleziona lo strumento attivo:")
            d_strum = {k: f"{k} ({v.get('tasti')} tasti, {len(v.get('accordatura'))} corde)" for k, v in strumenti.items()}
            scelto = menu(d=d_strum, keyslist=True, show=True, numbered=True, ntf="Strumento non trovato")
            if scelto is not None and scelto != strum_attivo:
                config.impostazioni['strumento_attivo'] = scelto
                config.archivio_modificato = True
                config.aggiorna_manico()
                print(f"\nStrumento attivo impostato su: {scelto}.")
        
        elif scelta == 'a':
            print("\n--- Aggiungi Nuovo Strumento ---")
            nome = dgt("Nome strumento: ", kind="s", smin=1).strip()
            if not nome:
                continue
            if nome in strumenti:
                print("Esiste già uno strumento con questo nome.")
                continue
            
            num_corde = dgt("Numero di corde (es. 4 per Ukulele): ", kind="i", imin=1, imax=12)
            if num_corde is None:
                continue
            accordatura = []
            
            print("Inserisci la nota vuota per ogni corda (es. E2).")
            print("La corda 1 è la più sottile (quella in basso nella tablatura).")
            
            # Map per standardizzare input
            mappa_note_std = dict(zip(config.NOTE_LATINE, config.NOTE_STD))
            mappa_note_std.update(dict(zip(config.NOTE_ANGLO, config.NOTE_STD)))
            
            abort = False
            for i in range(num_corde, 0, -1):
                if abort: break
                while True:
                    nota = dgt(f"Nota per la corda {i} (es. corda più grave E2): ", kind="s")
                    if nota is None:
                        abort = True
                        break
                    nota = nota.strip().upper()
                    # valida formato (deve finire con un numero)
                    if len(nota) >= 2 and nota[-1].isdigit():
                        nota_base = nota[:-1]
                        if nota_base in config.NOTE_STD or nota_base in config.NOTE_LATINE or nota_base in config.NOTE_ANGLO:
                            nota_std_fin = mappa_note_std.get(nota_base, nota_base)
                            if nota_std_fin in config.NOTE_STD:
                                accordatura.append(f"{nota_std_fin}{nota[-1]}")
                                break
                    print("Formato non valido. Es: E2, SOL3.")
            if abort:
                continue
            
            tasti = dgt("Numero di tasti: ", kind="i", imin=1, imax=50)
            if tasti is None:
                continue
            
            strumenti[nome] = {
                "accordatura": accordatura,
                "tasti": tasti
            }
            config.impostazioni['strumenti'] = strumenti
            config.archivio_modificato = True
            
            ans = dgt(f"Vuoi impostare {nome} come strumento attivo? (S/N): ", kind="s")
            if ans and ans.strip().lower() == 's':
                config.impostazioni['strumento_attivo'] = nome
                config.aggiorna_manico()
            print(f"Strumento {nome} aggiunto con successo!")
            
        elif scelta == 'e':
            print("\nSeleziona lo strumento da eliminare:")
            eliminabili = {k: v for k, v in strumenti.items() if k != strum_attivo}
            if not eliminabili:
                print("Non ci sono altri strumenti da eliminare.")
                continue
                
            d_strum_el = {k: f"{k} ({v.get('tasti')} tasti, {len(v.get('accordatura'))} corde)" for k, v in eliminabili.items()}
            scelto = menu(d=d_strum_el, keyslist=True, show=True, numbered=True, ntf="Strumento non trovato")
            if scelto is not None:
                conferma = dgt(f"Sei sicuro di voler eliminare {scelto}? (S/N): ", kind="s")
                if conferma and conferma.strip().lower() == 's':
                    del strumenti[scelto]
                    config.impostazioni['strumenti'] = strumenti
                    config.archivio_modificato = True
                    print(f"Strumento {scelto} eliminato.")
                    
        elif scelta is None:
            break


def GestoreImpostazioni():
    """Gestisce la modifica delle config.impostazioni dell'app."""
    print("\n--- Gestore Impostazioni ---")
    
    while True:
        # Il menu mostra dinamicamente l'impostazione corrente
        menu_impostazioni = {
            's': f"Gestisci Strumenti (Attivo: {config.impostazioni.get('strumento_attivo')})",
            'n': f"Cambia nomenclatura (attuale: {config.impostazioni['nomenclatura']})",
            '1': f"Modifica {config.impostazioni['suono_1']['descrizione']}",
            '2': f"Modifica {config.impostazioni['suono_2']['descrizione']}"
        }
        
        scelta = menu(d=menu_impostazioni, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
        
        if scelta == 's':
            GestoreStrumenti()
        
        elif scelta == 'n':
            # Inverti l'impostazione
            if config.impostazioni['nomenclatura'] == 'latino':
                config.impostazioni['nomenclatura'] = 'anglosassone'
            else:
                config.impostazioni['nomenclatura'] = 'latino'
            
            print(f"Nomenclatura impostata su: {config.impostazioni['nomenclatura']}")
            config.archivio_modificato = True
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
    print(f"Cerca una nota. Nomenclatura attuale: {config.impostazioni['nomenclatura']}.")
    
    # Determina la lista di note valide e la mappa di conversione
    if config.impostazioni['nomenclatura'] == 'latino':
        lista_note_valide = config.NOTE_LATINE
        mappa_inversa = dict(zip(config.NOTE_LATINE, config.NOTE_STD))
    else:
        lista_note_valide = config.NOTE_ANGLO
        mappa_inversa = dict(zip(config.NOTE_ANGLO, config.NOTE_STD))
        
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
    print("\nPuoi indicare una porzione di manico per la ricerca (es. 0-4)")
    scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
    maninf, mansup = 0, config.NUM_TASTI
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
    
    if s in config.CORDE:
        nota_std = config.CORDE[s]
        print(f"Sulla corda {s.split('.')[0]}, tasto {s.split('.')[1]}, si trova la nota: {get_nota(nota_std)}")
        
        suono_1 = config.impostazioni['suono_1']
        
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
            sd.play(note_audio, samplerate=GBAudio.FS, blocking=False)
        
    elif s == "":
        print("Operazione annullata.")
    else:
        print(f"Posizione '{s}' non valida. Formato richiesto: C.T (es. 6.3), tasti da 0 a {config.NUM_TASTI}.")
    
    key("Premi un tasto per tornare al menu...")

def CostruttoreAccordi():
    """
    Costruisce accordi usando music21.harmony.ChordSymbol secondo
    le best practice definite nel documento tecnico. (Versione Completa)
    """

    print("\n--- Costruttore di Accordi Teorico (harmony.ChordSymbol) ---")
    print("Scopri quali note compongono qualsiasi accordo.")

# --- 1. Scegli la Tonica ---
    # Dizionario {Mostra_Utente -> Ritorna_Standard}
    mappa_toniche = {}
    if config.impostazioni['nomenclatura'] == 'latino':
        # Inverti: {'DO': 'C', 'DO#': 'C#', ...}
        mappa_toniche = {lat: std for std, lat in config.STD_TO_LATINO.items() if len(std) <= 2 and std in config.NOTE_STD}
    else:
        # Mantieni: {'C': 'C', 'C#': 'C#', ...}
        mappa_toniche = {anglo: std for std, anglo in config.STD_TO_ANGLO.items() if len(std) <= 2 and std in config.NOTE_STD}

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
    primary_shorthand = menu(d=scale_catalog.USER_CHORD_DICT, keyslist=True, show=False,
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
                scale_catalog.USER_CHORD_DICT, # Cerca nel dizionario degli accordi
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
        nome_accordo_display_base = scale_catalog.USER_CHORD_DICT.get(primary_shorthand, primary_shorthand) # Prendi il nome leggibile

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
        print("Verifica la correttezza della fondamentale e del tipo.")
        key("Premi un tasto...")
        return # Esce dalla funzione

    # --- 4. Mostra i Risultati ---
    nome_accordo_display = f"{get_nota(tonica_std)} {nome_accordo_display_base}"
    note_str = " - ".join(note_accordo_formattate)
    print("\n--- Risultato Analisi (harmony.ChordSymbol) ---")
    print(f"Accordo: {nome_accordo_display}")
    print(f"Note componenti: {note_str}")
    print("---------------------------------------------")

# --- 5. Calcolo e Scelta delle Diteggiature (Motore CSP) ---
    print("\nCalcolo delle migliori diteggiature in corso...")
    
    target_pc = {p.pitchClass for p in note_accordo_obj}
    root_pc = accordo_m21.root().pitchClass

    strum_attivo = config.impostazioni.get("strumento_attivo", "Chitarra")
    dati_strum = config.impostazioni.get("strumenti", {}).get(strum_attivo, {})
    if not dati_strum:
        print(f"Errore: Dati per lo strumento {strum_attivo} non trovati.")
        key("Premi un tasto...")
        return
        
    num_corde = int(dati_strum.get("corde", len(dati_strum.get("accordatura", []))))
    num_tasti = int(dati_strum.get("tasti", 22))
    
    # Prendi direttamente la lista dell'accordatura dal JSON
    accordatura_lista = dati_strum.get("accordatura", [])
    if not accordatura_lista or len(accordatura_lista) != num_corde:
        print("Errore: Accordatura dello strumento mancante o incompleta.")
        key("Premi un tasto...")
        return

    from strumento import InstrumentModel
    from generatore_accordi import AccordoSolver
    model = InstrumentModel(accordatura_lista, num_tasti)
    solver = AccordoSolver(model, target_pc, root_pc)
    
    # Eseguiamo il solver e valutiamo le opzioni
    sols = solver.solve(max_stretch=4)
    scored_sols = []
    for s in sols:
        score = solver.score_solution(s)
        scored_sols.append((score, s))
        
    scored_sols.sort(key=lambda x: x[0], reverse=True)
    
    if not scored_sols:
        print("\nNessuna diteggiatura fisicamente possibile trovata per questo accordo.")
        key("Premi un tasto per tornare al menu...")
        return
        
    top_n = min(10, len(scored_sols))
    menu_diteggiature = {}
    soluzioni_map = {}
    
    for i in range(top_n):
        score, s = scored_sols[i]
        tab = [s[f"C{j}"] for j in range(model.num_corde)]
        tab_str = ["X" if t == -1 else str(t) for t in tab]
        meta = solver.analizza_difficolta_e_diteggiatura(s, score)
        
        # Mappa per la chordpedia (dalla corda acuta alla grave, come nel file json)
        tab_menu_list = []
        for j in range(model.num_corde-1, -1, -1):
            tab_menu_list.append("x" if tab[j] == -1 else str(tab[j]))
        
        tab_titolo = "-".join(tab_menu_list)
        chiave_menu = str(i)
        
        dettagli = f"Tablatura (dalla corda più grave): {' '.join(tab_str)}\n"
        dettagli += f"Difficoltà Generale: {meta['difficolta_score_perc']}% | Estensione: {meta['difficolta_stretch_perc']}% ({meta['stretch_tasti']} tasti)\n"
        if meta['diteggiatura']:
            dettagli += "Impostazione mano:\n"
            dettagli += "\n".join([f"  - {d}" for d in meta['diteggiatura']])
        else:
            dettagli += "Nessun dito usato (tutte a vuoto o mute)."
        
        # Nel menu usiamo la tablatura compatta e le % di difficoltà
        menu_diteggiature[chiave_menu] = f"{tab_titolo} | Diff: {meta['difficolta_score_perc']}% | Stretch: {meta['difficolta_stretch_perc']}%"
        soluzioni_map[chiave_menu] = (tab_menu_list, dettagli)

    # --- 6. Interazione con le Soluzioni Trovate ---
    if top_n == 1:
        scelta_tab = list(soluzioni_map.keys())[0]
        tab_selezionata, dettagli_full = soluzioni_map[scelta_tab]
        
        print("\n--- Dettagli dell'unica Forma Trovata ---")
        print(f"{dettagli_full}")
        print("-------------------------------")
        
        print("Ascolto dell'accordo (Player Corde)...")
        Suona(list(reversed(tab_selezionata)))
    else:
        while True:
            print(f"\n--- Le {top_n} migliori diteggiature per {nome_accordo_display} ---")
            menu_ordinato = dict(sorted(menu_diteggiature.items(), key=lambda item: int(item[0])))
            scelta_tab = menu(d=menu_ordinato, keyslist=True, show=True, numbered=False, ntf="Scelta non valida", p="Scegli il numero (es. 0) per ascoltare: ")
            
            if scelta_tab is None:
                break
                
            tab_selezionata, dettagli_full = soluzioni_map[scelta_tab]
            
            print(f"\n--- Dettagli {scelta_tab} ---")
            print(f"{dettagli_full}")
            print("-------------------------------")
            
            print("Ascolto dell'accordo (Player Corde)...")
            # tab_selezionata è [corda1, corda2... corda6]. Suona() si aspetta [corda6, corda5... corda1]
            Suona(list(reversed(tab_selezionata)))
            
            azione = dgt("\nScegli: [R]iascolta | [Invio] per tornare alle opzioni: ").strip().lower()
            if azione == 'r':
                Suona(list(reversed(tab_selezionata)))
                
    print("\nUscita dal Costruttore Accordi.")


def PlayerGenerico():
    print("\n--- Tastiera Virtuale (Player Generico) ---")
    print("Suona usando la tastiera del tuo PC (layout Italiano).")
    print("  Ottava Base (ZXC...): Z=Do, S=Do#, X=Re, D=Re#...")
    print("  Ottava Superiore (QWE...): Q=Do, 2=Do#, W=Re...")
    print("  Maiuscole (Shift): Suonano un'ottava sotto/sopra rispetto ai minuscoli.")
    print("  Freccia SU / GIÙ (o Tasti < / >): Alza/Abbassa l'ottava base")
    print("  SPAZIO: Cambia Suono")
    print("  ESC: Esci")

    base_octave = 3
    suono_attivo_key = 'suono_1'

    # Mappa tastiera italiana per il player virtuale
    # (semitoni rispetto a Do, offset_ottava)
    KB_MAP = {
        # --- OTTAVA BASE (offset 0) ---
        'z': (0, 0),  'x': (2, 0),  'c': (4, 0),  'v': (5, 0),  'b': (7, 0),  'n': (9, 0),  'm': (11, 0), 
        ',': (12, 0), '.': (14, 0), '-': (16, 0),
        's': (1, 0),  'd': (3, 0),  'g': (6, 0),  'h': (8, 0),  'j': (10, 0), 'l': (13, 0), 'ò': (15, 0),

        # --- OTTAVA BASE - 1 (offset -1, SHIFT) ---
        'Z': (0, -1), 'X': (2, -1), 'C': (4, -1), 'V': (5, -1), 'B': (7, -1), 'N': (9, -1), 'M': (11, -1),
        ';': (12, -1), ':': (14, -1), '_': (16, -1),
        'S': (1, -1), 'D': (3, -1), 'G': (6, -1), 'H': (8, -1), 'J': (10, -1), 'L': (13, -1), 'ç': (15, -1),

        # --- OTTAVA BASE + 1 (offset +1, riga superiore) ---
        'q': (0, 1),  'w': (2, 1),  'e': (4, 1),  'r': (5, 1),  't': (7, 1),  'y': (9, 1),  'u': (11, 1),
        'i': (12, 1), 'o': (14, 1), 'p': (16, 1), 'è': (17, 1), '+': (19, 1),
        '2': (1, 1),  '3': (3, 1),  '5': (6, 1),  '6': (8, 1),  '7': (10, 1), '9': (13, 1), '0': (15, 1), 'ì': (18, 1),

        # --- OTTAVA BASE + 2 (offset +2, SHIFT riga superiore) ---
        'Q': (0, 2),  'W': (2, 2),  'E': (4, 2),  'R': (5, 2),  'T': (7, 2),  'Y': (9, 2),  'U': (11, 2),
        'I': (12, 2), 'O': (14, 2), 'P': (16, 2), 'é': (17, 2), '*': (19, 2),
        '"': (1, 2),  '£': (3, 2),  '%': (6, 2),  '&': (8, 2),  '/': (10, 2), ')': (13, 2), '=': (15, 2), '^': (18, 2),
    }

    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=16) 
    num_voices = 16
    renderers = [GBAudio.NoteRenderer(fs=GBAudio.FS) for _ in range(num_voices)]
    voice_idx = 0

    poly_player.start()
    
    def get_synth_params(s_key):
        s = config.impostazioni[s_key]
        return {
            'dur': s.get('dur_accordi', 9.0),
            'vol': s.get('volume', 0.35),
            'hardness': s.get('pluck_hardness', 0.6),
            'damping': s.get('damping_factor', 0.997),
            'pick_pos': s.get('pick_position', 0.15),
            'bright': s.get('brightness', 0.4),
            'kind': s.get('kind', 1),
            'adsr': s.get('adsr', [0,0,0,0])
        }
    
    p = get_synth_params(suono_attivo_key)
    print(f"\n[Suono: {config.impostazioni[suono_attivo_key]['descrizione']}] Ottava Base: {base_octave}")

    try:
        print(f"\r[Suono: {config.impostazioni[suono_attivo_key]['descrizione']}] Ottava Base: {base_octave}{' '*20}\r", end="", flush=True)
        while True:
            ch = key()
            if not ch: continue

            if ch == chr(27): # ESC
                break
            elif ch == ' ':
                suono_attivo_key = 'suono_2' if suono_attivo_key == 'suono_1' else 'suono_1'
                p = get_synth_params(suono_attivo_key)
                print(f"\r[Suono: {config.impostazioni[suono_attivo_key]['descrizione']}] Ottava Base: {base_octave}{' '*20}\r", end="", flush=True)
            elif ch in ('f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8'):
                if ch == 'f1': base_octave = 2
                elif ch == 'f2': base_octave = 3
                elif ch == 'f3': base_octave = 4
                elif ch == 'f4': base_octave = 5
                elif ch == 'f5': base_octave = 6
                elif ch == 'f6': base_octave = 7
                elif ch == 'f7': base_octave = 8
                elif ch == 'f8': base_octave = 9
                print(f"\r[Suono: {config.impostazioni[suono_attivo_key]['descrizione']}] Ottava Base impostata a: {base_octave}{' '*20}\r", end="", flush=True)
            elif ch in KB_MAP:
                semitones, oct_offset = KB_MAP[ch]
                actual_octave = base_octave + oct_offset
                
                # Previene frequenze estreme inaudibili/scomode
                if actual_octave < 1: actual_octave = 1
                if actual_octave > 9: actual_octave = 9
                
                midi_num = 12 + semitones + 12 * actual_octave
                freq = 440.0 * (2.0 ** ((midi_num - 69) / 12.0))
                
                v = voice_idx % num_voices
                voice_idx += 1
                
                suono = config.impostazioni[suono_attivo_key]
                if 'pluck_hardness' in suono:
                    renderers[v].set_params(freq, p['dur'], p['vol'], 0.0, 
                                            pluck_hardness=p['hardness'], damping_factor=p['damping'],
                                            pick_position=p['pick_pos'], brightness=p['bright'])
                else:
                    renderers[v].set_params(freq, p['dur'], p['vol'], 0.0, kind=p['kind'], adsr_list=p['adsr'])
                
                note_audio = renderers[v].render()
                if note_audio.size > 0:
                    mono_audio = note_audio[:, 0] / renderers[v].pan_l if renderers[v].pan_l != 0 else note_audio[:, 0]
                    poly_player.pluck(string_idx=v, audio_mono=mono_audio)
                
                # Calcola il nome della nota per il display
                nota_obj = pitch.Pitch(midi=midi_num)
                nota_nome = get_nota(nota_obj.nameWithOctave.replace('-', 'b'))
                print(f"\rUltima nota: {nota_nome} ({freq:.1f} Hz) [Ottava base: {base_octave}]{' '*15}\r", end="", flush=True)

    finally:
        poly_player.stop()
        print("\nUscita dal Player Generico.")


def GiocaColSuono():
    import gioca_suono
    
    def cb_salva(nuove_impostazioni):
        config.impostazioni = nuove_impostazioni
        config.archivio_modificato = True
        config.salva_impostazioni()
        
    gioca_suono.avvia_gioco(config.impostazioni, get_nota, config.NOTE_LATINE, config.NOTE_STD, config.NOTE_ANGLO, cb_salva)

def Accordatore():
    """Accordatore cromatico: rileva la nota fondamentale dal microfono usando sounddevice e numpy FFT."""
    import math
    import threading

    # Selezione dispositivo di input
    devices = sd.query_devices()
    input_devices = {}
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0:
            try:
                api_name = sd.query_hostapis(dev['hostapi'])['name']
            except Exception:
                api_name = "Sconosciuto"
            input_devices[str(idx)] = f"{dev['name']} [{api_name}]"
    if not input_devices:
        print("\nErrore: Nessun dispositivo di input audio (microfono) trovato.")
        key("Premi un tasto per continuare...")
        return
    print("\n--- Dispositivi di Input Disponibili ---")
    scelta_device = menu(d=input_devices, p="Seleziona il dispositivo di input: ", show=True, numbered=True)
    if scelta_device is None:
        return
    device_idx = int(scelta_device)
    dev_info = sd.query_devices(device_idx, 'input')
    device_sr = int(dev_info['default_samplerate'])
    BLOCK_SIZE = 4096
    RMS_THRESHOLD = 0.002
    pitch_readings = []
    current_rms = [0.0]
    pitch_lock = threading.Lock()
    stop_event = threading.Event()
    def _parabolic_interp(mag, peak_idx):
        if peak_idx <= 0 or peak_idx >= len(mag) - 1:
            return float(peak_idx)
        alpha = mag[peak_idx - 1]
        beta = mag[peak_idx]
        gamma = mag[peak_idx + 1]
        denom = alpha - 2.0 * beta + gamma
        if abs(denom) < 1e-12:
            return float(peak_idx)
        p = 0.5 * (alpha - gamma) / denom
        return peak_idx + p
    def _audio_callback(indata, frames, time_info, status):
        if stop_event.is_set():
            raise sd.CallbackAbort
        mono = indata[:, 0]
        rms = float(np.sqrt(np.mean(mono ** 2)))
        current_rms[0] = rms
        if rms < RMS_THRESHOLD:
            return
        windowed = mono * np.hanning(len(mono))
        fft_data = np.fft.rfft(windowed)
        magnitudes = np.abs(fft_data)
        freq_per_bin = device_sr / len(mono)
        min_bin = max(1, int(50 / freq_per_bin))
        max_bin = min(
            len(magnitudes) - 1,
            int(2000 / freq_per_bin)
        )
        if min_bin >= max_bin:
            return
        search_region = magnitudes[min_bin:max_bin]
        peak_bin = int(np.argmax(search_region)) + min_bin
        refined_bin = _parabolic_interp(
            magnitudes, peak_bin
        )
        detected_freq = refined_bin * freq_per_bin
        with pitch_lock:
            pitch_readings.append(detected_freq)
    print("Accordatore cromatico.")
    print("ESC per uscire.")
    try:
        stream = sd.InputStream(
            device=device_idx,
            samplerate=device_sr,
            channels=1,
            blocksize=BLOCK_SIZE,
            dtype='float32',
            callback=_audio_callback
        )
        stream.start()
    except Exception as e:
        print(f"Errore apertura audio: {e}")
        key("Premi un tasto...")
        return
    import time
    last_print_time = 0
    last_nota = "---"
    last_cents = 0.0
    last_freq = 0.0
    all_midi = []
    all_freqs = []
    all_dbs = []
    try:
        while True:
            ch = key(attesa=0.05)
            if ch == '\x1b':
                break
            current_time = time.time()
            if current_time - last_print_time >= 1.0:
                with pitch_lock:
                    readings = pitch_readings.copy()
                    pitch_readings.clear()
                rms = current_rms[0]
                db_val = 20 * math.log10(rms / 1e-5) if rms > 1e-5 else 0.0
                above_threshold = (rms >= RMS_THRESHOLD)
                if rms > 1e-6:
                    all_dbs.append(db_val)
                if readings and above_threshold:
                    avg_freq = float(np.median(readings))
                    if 30.0 <= avg_freq <= 2000.0:
                        midi_num = 69 + 12 * math.log2(
                            avg_freq / 440.0
                        )
                        target_midi = round(midi_num)
                        cents = (midi_num - target_midi) * 100
                        nota_nome = get_nota(
                            pitch.Pitch(midi=target_midi).nameWithOctave.replace('-', 'b')
                        )
                        last_nota = nota_nome
                        last_cents = cents
                        last_freq = avg_freq
                        all_midi.append(target_midi)
                        all_freqs.append(avg_freq)
                if last_nota == "---":
                    cents_str = "0%"
                    hz_str = "---"
                else:
                    s = "+" if last_cents >= 0 else ""
                    cents_str = f"{s}{last_cents:.0f}%"
                    hz_str = f"{last_freq:.1f}"
                db_str = f"dB:{db_val:.0f}"
                db_formatted = f"[{db_str}]" if above_threshold else f"<{db_str}>"
                line = (
                    f"N:{last_nota} "
                    f"({cents_str}) "
                    f"Hz:{hz_str} "
                    f"{db_formatted}"
                )
                print(
                    f"\r{line:<40}\r",
                    end="", flush=True
                )
                last_print_time = current_time
    finally:
        stop_event.set()
        stream.stop()
        stream.close()
        print("\nAccordatore chiuso.")
        if all_midi and all_freqs and all_dbs:
            if len(all_midi) >= 3:
                trimmed_midi = sorted(all_midi)[1:-1]
                trimmed_freqs = sorted(all_freqs)[1:-1]
                trimmed_dbs = sorted(all_dbs)[1:-1]
            else:
                trimmed_midi = all_midi
                trimmed_freqs = all_freqs
                trimmed_dbs = all_dbs

            min_midi = min(trimmed_midi)
            max_midi = max(trimmed_midi)
            med_midi = int(round(np.median(trimmed_midi)))
            nota_min = get_nota(pitch.Pitch(midi=min_midi).nameWithOctave.replace('-', 'b'))
            nota_max = get_nota(pitch.Pitch(midi=max_midi).nameWithOctave.replace('-', 'b'))
            nota_med = get_nota(pitch.Pitch(midi=med_midi).nameWithOctave.replace('-', 'b'))
            
            min_f = min(trimmed_freqs)
            max_f = max(trimmed_freqs)
            med_f = np.median(trimmed_freqs)
            
            min_db = min(trimmed_dbs)
            max_db = max(trimmed_dbs)
            med_db = np.median(trimmed_dbs)
            
            print(f"\nNote ascoltate: {nota_min} ({nota_med}) {nota_max}")
            print(f"Frequenze (Hz): {min_f:.1f} ({med_f:.1f}) {max_f:.1f}")
            print(f"Volumi (dB): {min_db:.0f} ({med_db:.0f}) {max_db:.0f}")
