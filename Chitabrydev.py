# Chitabry - Studio sulla Chitarra e sulla teoria musicale - di Gabriele Battaglia
# Data concepimento: venerdì 7 febbraio 2020.
# 28 giugno 2024 copiato su Github
# 22 ottobre 2025, versione 4 con importante refactoring

import json
import sys
import random
from time import sleep as aspetta
from GBUtils import dgt, manuale, menu, key, Acusticator

# --- Costanti ---
VERSIONE = "4.0.0 del 23 ottobre 2025."
ENARMONICI = {
    'C#': 'Db', 'Db': 'C#',
    'D#': 'Eb', 'Eb': 'D#',
    'F#': 'Gb', 'Gb': 'F#',
    'G#': 'Ab', 'Ab': 'G#',
    'A#': 'Bb', 'Bb': 'A#'
}
# Nomi base delle note per la logica "intelligente"
NOTE_DIATONICHE = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
FILE_IMPOSTAZIONI = "chitabry-settings.json"
archivio_modificato = False
impostazioni = {} # Conterrà l'intera configurazione caricata/default

# Nomenclatura standard usata internamente e da Acusticator
NOTE_STD = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTE_LATINE = ['DO', 'DO#', 'RE', 'RE#', 'MI', 'FA', 'FA#', 'SOL', 'SOL#', 'LA', 'LA#', 'SI']
NOTE_ANGLO = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']

# Dizionari per la conversione
STD_TO_LATINO = dict(zip(NOTE_STD, NOTE_LATINE))
STD_TO_ANGLO = dict(zip(NOTE_STD, NOTE_ANGLO))
STD_TO_LATINO.update({
    'Db': 'REb',
    'Eb': 'MIb',
    'Gb': 'SOLb',
    'Ab': 'LAb',
    'Bb': 'SIb'
})
STD_TO_ANGLO.update({
    'Db': 'Db',
    'Eb': 'Eb',
    'Gb': 'Gb',
    'Ab': 'Ab',
    'Bb': 'Bb'
})
# Struttura del manico (basata sulla notazione standard)
SCALACROMATICA_STD = {}
i = 0
for j in range(0, 8):
    for nota in NOTE_STD:
        i += 1
        SCALACROMATICA_STD[i] = nota + str(j)

MANICO = []
for i in range(29, 75):
    MANICO.append(SCALACROMATICA_STD[i])

CAPOTASTI = {}
i = 6
for j in [29, 34, 39, 44, 48, 53]:
    CAPOTASTI[i] = j
    i -= 1

CORDE = {}
for corda in range(6, 0, -1):
    for tasto in range(CAPOTASTI[corda], CAPOTASTI[corda] + 22):
        CORDE[str(corda) + "." + str(tasto - CAPOTASTI[corda])] = SCALACROMATICA_STD[tasto]
MAINMENU = {
    "Accordi": "Gestisci la tua raccolta di accordi (Chordpedia)",
    "Scale": "Visualizza, esercitati e gestisci le scale",
    "Impostazioni": "Configura i suoni e la notazione delle note",
    "Trova Nota": "Trova le posizioni di una nota sul manico",
    "Trova Posizione": "Indica la nota su una corda/tasto (C.T)",
    "Guida": "Mostra la guida di Chitabry",
    "Esci": "Salva ed esci dall'applicazione"
}

# --- Funzioni di Gestione Dati (Fase 1) ---

# (Riga 80 circa)

def get_impostazioni_default():
    """Restituisce la struttura dati di default per un nuovo file JSON."""
    scale_default = {
        "maggiore": {
            "nome": "Maggiore",
            "asc": [2, 2, 1, 2, 2, 2, 1],
            "desc": [2, 2, 1, 2, 2, 2, 1],
            "simmetrica": True
        },
        "minore naturale": {
            "nome": "Minore Naturale",
            "asc": [2, 1, 2, 2, 1, 2, 2],
            "desc": [2, 1, 2, 2, 1, 2, 2],
            "simmetrica": True
        },
        "minore armonica": {
            "nome": "Minore Armonica",
            "asc": [2, 1, 2, 2, 1, 3, 1],
            "desc": [2, 1, 2, 2, 1, 3, 1],
            "simmetrica": True
        },
        "minore melodica": {
            "nome": "Minore Melodica",
            "asc": [2, 1, 2, 2, 2, 2, 1],
            "desc": [2, 2, 1, 2, 2, 1, 2], # Discendente = Minore Naturale
            "simmetrica": False
        },
        "maggiore blues": {
            "nome": "Maggiore Blues",
            "asc": [3, 2, 1, 1, 3, 2],
            "desc": [3, 2, 1, 1, 3, 2],
            "simmetrica": True
        },
        "minore blues": {
            "nome": "Minore Blues",
            "asc": [2, 1, 1, 3, 2, 3], 
            "desc": [2, 1, 1, 3, 2, 3],
            "simmetrica": True
        },
        "cromatica": {
            "nome": "Cromatica",
            "asc": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            "desc": [1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1],
            "simmetrica": True
        },
        "pentatonica": {
            "nome": "Pentatonica Maggiore",
            "asc": [2, 2, 3, 2, 3],
            "desc": [2, 2, 3, 2, 3],
            "simmetrica": True
        }
    }
    
    return {
        "nomenclatura": "latino",
        "default_bpm": 40,
        "suono_1": {
            "descrizione": "Suono per accordi (simil-chitarra)",
            "kind": 3,
            "adsr": [0.5, 99.0, 0.0, 0.5], # A=0.5%, D=99% (decay lungo), S=0, R=0.5%
            "dur_accordi": 3.0, # Aumentato a 3 secondi
            "volume": 0.35
        },
        "suono_2": {
            "descrizione": "Suono per scale (simil-flauto)",
            "kind": 1,
            "adsr": [2.0, 1.0, 90.0, 2.0],
            "volume": 0.35
        },
        "chordpedia": {},
        "scale": scale_default
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

def get_nota(nota_std):
    """
    Converte una nota standard (es. "C#4" o "F#")
    nella notazione scelta dall'utente (latina o anglosassone).
    """
    if impostazioni['nomenclatura'] == 'latino':
        mappa = STD_TO_LATINO
    else:
        mappa = STD_TO_ANGLO

    # Separiamo nota e ottava
    if nota_std[-1].isdigit():
        nome_nota = nota_std[:-1]
        ottava = nota_std[-1]
    else:
        nome_nota = nota_std
        ottava = ""
        
    return mappa.get(nome_nota, nota_std) + ottava
# --- Funzioni Audio (Fase 3) ---

# (Riga 255 circa)

def Suona(tablatura):
    """
    Permette l'ascolto interattivo di una tablatura (lista di 6 corde).
    Usa Acusticator con i parametri di 'suono_1'.
    """
    print("\nAscolta le corde:")
    print("Tasti da 1 a 6, (A) pennata in levare, (Q) pennata in battere")
    print("ESC per uscire.")
    
    suono_1 = impostazioni['suono_1']
    kind = suono_1['kind']
    adsr = suono_1['adsr']
    dur = suono_1['dur_accordi']
    vol = suono_1['volume'] # Aggiunto volume
    
    # Costruiamo la lista di note e pan da suonare
    note_da_suonare = []
    for i in range(6): # i da 0 a 5 (corda 6 a 1)
        corda = 6 - i
        tasto = tablatura[i]
        pan = -0.8 + (i * 0.32)
        
        if tasto.isdigit() and f"{corda}.{tasto}" in CORDE:
            nota_std = CORDE[f"{corda}.{tasto}"]
            note_da_suonare.append( (nota_std, pan) )
        else:
            note_da_suonare.append(None) 
            
    # Loop di ascolto interattivo
    while True:
        scelta = key().lower()
        
        if scelta.isdigit() and scelta in '123456':
            corda_idx = int(scelta) - 1 
            dati_nota = note_da_suonare[5 - corda_idx]
            
            if dati_nota:
                nota, pan = dati_nota
                score = [nota, dur, pan, vol] # Usa vol
                Acusticator(score, kind=kind, adsr=adsr, sync=False)
                
        elif scelta == chr(27): # ESC
            print("Uscita dal menù ascolto.")
            break
            
        elif scelta == 'a': # Pennata in levare
            for i in range(5, -1, -1): 
                dati_nota = note_da_suonare[i]
                if dati_nota:
                    nota, pan = dati_nota
                    score = [nota, dur, pan, vol / 4.0] # Volume ridotto per lo strum
                    Acusticator(score, kind=kind, adsr=adsr, sync=False)
                    aspetta(0.05) 
                    
        elif scelta == 'q': # Pennata in battere
            for i in range(6): 
                dati_nota = note_da_suonare[i]
                if dati_nota:
                    nota, pan = dati_nota
                    score = [nota, dur, pan, vol / 4.0] # Volume ridotto per lo strum
                    Acusticator(score, kind=kind, adsr=adsr, sync=False)
                    aspetta(0.05) 
        else:
            print("Comando non valido. Premi 1-6, A, Q o ESC.")
    
    return
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
            print(f"Note: {note_accordo_str}") # <-- (Req 2) Stampa riepilogo
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

def valida_stringa_intervalli(s_intervalli):
    """
    Convalida una stringa di toni/semitoni (es. "tsttstt").
    Restituisce la lista di intervalli numerici (es. [2, 1, 2, 2, 1, 2, 2])
    o None se la somma non è 12.
    """
    lista_intervalli = []
    somma = 0
    for char in s_intervalli.lower():
        if char == 't':
            val = 2
        elif char == 's':
            val = 1
        else:
            print(f"Carattere non valido '{char}'. Usare solo 't' (tono) e 's' (semitono).")
            return None
        lista_intervalli.append(val)
        somma += val
    
    if somma != 12:
        print(f"Errore: la somma degli intervalli ({somma}) non è 12 (un'ottava).")
        return None
        
    return lista_intervalli

def AggiungiScala():
    """Aggiunge una nuova scala a impostazioni['scale']"""
    global archivio_modificato
    scale = impostazioni['scale']
    
    print("\n--- Aggiungi una nuova scala ---")
    while True:
        nome_scala = dgt("Nome della scala (es. 'Lidia'): ", smin=1, smax=40)
        if nome_scala == "":
            print("Aggiunta annullata.")
            return
        if nome_scala.lower() not in scale:
            break
        print("Nome scala già presente. Scegli un nome diverso.")
    
    # Intervalli ascendenti
    while True:
        s_asc = dgt("Inserisci la sequenza ascendente (es. 'ttsttts'): ")
        intervalli_asc = valida_stringa_intervalli(s_asc)
        if intervalli_asc:
            break
            
    # Simmetrica o discendente
    intervalli_desc = intervalli_asc
    simmetrica = True
    
    scelta_sym = dgt("La scala è simmetrica (uguale discendente)? (s/n): ", smin=1, smax=1).lower()
    if scelta_sym == 'n':
        simmetrica = False
        print("Inserisci la sequenza discendente.")
        while True:
            s_desc = dgt("Sequenza discendente: ")
            intervalli_desc = valida_stringa_intervalli(s_desc)
            if intervalli_desc:
                break
                
    # Salva la nuova scala
    scale[nome_scala.lower()] = {
        "nome": nome_scala.title(), # Salviamo il nome formattato
        "asc": intervalli_asc,
        "desc": intervalli_desc,
        "simmetrica": simmetrica
    }
    archivio_modificato = True
    print(f"Scala '{nome_scala.title()}' aggiunta con successo.")
    key("Premi un tasto...")

def RimuoviScala():
    """Rimuove una scala da impostazioni['scale']"""
    global archivio_modificato
    scale = impostazioni['scale']
    
    print("\n--- Rimuovi una scala ---")
    if not scale:
        print("Non ci sono scale personalizzate da rimuovere.")
        key("Premi un tasto...")
        return
        
    # Crea dizionario {key: nome formattato} per menu()
    d_scale = {k: v['nome'] for k, v in scale.items()}
    
    chiave_scelta = menu(d=d_scale, keyslist=True, show=False, pager=20,
                         ntf="Scala non trovata", p="Filtra scala da rimuovere: ")
                         
    if chiave_scelta is None:
        print("Rimozione annullata.")
        return
        
    nome_formattato = scale[chiave_scelta]['nome']
    
    conferma = dgt(f"Sei sicuro di voler rimuovere la scala '{nome_formattato}'? (s/n): ", smin=1, smax=1).lower()
    if conferma == 's':
        del scale[chiave_scelta]
        archivio_modificato = True
        print(f"Scala '{nome_formattato}' rimossa.")
    else:
        print("Rimozione annullata.")
    key("Premi un tasto...")

def ModificaScala():
    """Modifica una scala (eseguendo Rimuovi + Aggiungi)"""
    global archivio_modificato
    scale = impostazioni['scale']
    
    print("\n--- Modifica una scala ---")
    if not scale:
        print("Nessuna scala da modificare.")
        key("Premi un tasto...")
        return
        
    d_scale = {k: v['nome'] for k, v in scale.items()}
    chiave_scelta = menu(d=d_scale, keyslist=True, show=False, pager=20,
                         ntf="Scala non trovata", p="Filtra scala da MODIFICARE: ")
                         
    if chiave_scelta is None:
        print("Modifica annullata.")
        return
        
    nome_formattato = scale[chiave_scelta]['nome']
    
    conferma = dgt(f"Modificare la scala '{nome_formattato}'? (s/n): ", smin=1, smax=1).lower()
    if conferma == 's':
        # Rimuove la vecchia
        del scale[chiave_scelta]
        print(f"Scala '{nome_formattato}' rimossa. Ora inserisci i nuovi dati.")
        # Aggiunge la nuova (riutilizzando la logica)
        AggiungiScala() 
        # AggiungiScala imposta già 'archivio_modificato'
    else:
        print("Modifica annullata.")
        key("Premi un tasto...")

def genera_note_scala(tonica_std, intervalli):
    """
    Genera la lista di note (stringhe) per una scala,
    applicando la logica "intelligente" diatonica (#/b).
    """
    # Trova l'indice cromatico della tonica
    # (es. 'C4' -> 52)
    try:
        # Crea mappa inversa C4 -> 52
        STD_TO_INDICE = {v: k for k, v in SCALACROMATICA_STD.items()}
        idx_cromatico = STD_TO_INDICE[tonica_std]
        tonica_base = tonica_std[:-1] # Es. 'C'
    except KeyError:
        print(f"Errore: tonica '{tonica_std}' non trovata.")
        return []

    # Trova l'indice diatonico della tonica (es. 'C' -> 0)
    idx_diatonico = NOTE_DIATONICHE.index(tonica_base.replace('#', '').replace('b', ''))
    
    scala_generata = [tonica_std]
    nota_precedente_base = tonica_base
    
    idx_cromatico_corrente = idx_cromatico
    
    for intervallo in intervalli:
        idx_cromatico_corrente += intervallo
        idx_diatonico = (idx_diatonico + 1) % 7
        
        nota_corrente_std = SCALACROMATICA_STD[idx_cromatico_corrente]
        nota_corrente_base = nota_corrente_std[:-1] # Es. 'D#'
        ottava = nota_corrente_std[-1]
        
        nome_diatonico_atteso = NOTE_DIATONICHE[idx_diatonico] # Es. 'D'
        
        # Logica "intelligente":
        # Se la nota generata (es. 'D#') non inizia con il nome
        # diatonico atteso (es. 'D'), cerca l'enarmonico.
        if not nota_corrente_base.startswith(nome_diatonico_atteso):
            enarmonico = ENARMONICI.get(nota_corrente_base)
            if enarmonico and enarmonico.startswith(nome_diatonico_atteso):
                nota_corrente_base = enarmonico
            # Caso speciale (es. Scala di F -> A, A#... deve diventare Bb)
            elif nota_precedente_base.startswith(nome_diatonico_atteso):
                 enarmonico = ENARMONICI.get(nota_corrente_base)
                 if enarmonico:
                     nota_corrente_base = enarmonico

        scala_generata.append(nota_corrente_base + ottava)
        nota_precedente_base = nota_corrente_base
        
    return scala_generata

# (Riga 660 circa)

def VisualizzaEsercitatiScala():
    """Menu per visualizzare, ascoltare ed esercitarsi sulle scale."""
    scale = impostazioni['scale']
    suono_2 = impostazioni['suono_2']
    vol = suono_2['volume'] # Aggiunto volume
    
    print("\n--- Visualizza ed Esercitati sulle Scale ---")
    if not scale:
        print("Nessuna scala definita. Aggiungine una dal menu precedente.")
        key("Premi un tasto...")
        return
        
    # ... (Parte 1: Scegli Scala - non cambia) ...
    d_scale = {k: v['nome'] for k, v in scale.items()}
    chiave_scala = menu(d=d_scale, keyslist=True, show=False, pager=20,
                        ntf="Scala non trovata", p="Filtra scala: ")
    if chiave_scala is None: return
    
    scala_scelta = scale[chiave_scala]
    print(f"Scala selezionata: {scala_scelta['nome']}")
    
    # ... (Parte 2: Scegli Tonica - non cambia) ...
    while True:
        s_tonica = dgt("Inserisci la nota tonica (es. C4, o DO4): ", smin=1, smax=4).upper()
        if s_tonica == "": return
        
        tonica_std = None
        if s_tonica in SCALACROMATICA_STD.values():
            tonica_std = s_tonica
            break
        try:
            idx_latino = NOTE_LATINE.index(s_tonica[:-1])
            ottava = s_tonica[-1]
            if ottava.isdigit():
                tonica_std = NOTE_STD[idx_latino] + ottava
                if tonica_std in SCALACROMATICA_STD.values():
                    break
        except (ValueError, IndexError):
            pass
        print("Tonica non valida. Deve essere una nota con ottava (es. C4, F#3, LA4).")

    print(f"Generazione scala di {scala_scelta['nome']} di {get_nota(tonica_std)}...")
    
    # ... (Parte 3 e 4: Genera e Stampa Scale - non cambia) ...
    note_asc = genera_note_scala(tonica_std, scala_scelta['asc'])
    note_desc = []
    if not scala_scelta['simmetrica']:
        tonica_alta = note_asc[-1] 
        note_desc_temp = genera_note_scala(tonica_alta, scala_scelta['desc'])
        note_desc = list(reversed(note_desc_temp))
    
    print("\n--- Scala Ascendente ---")
    print(" ".join([get_nota(n[:-1]) for n in note_asc])) 
    
    if not scala_scelta['simmetrica']:
        print("\n--- Scala Discendente ---")
        print(" ".join([get_nota(n[:-1]) for n in note_desc])) 

    # ... (Parte 5: Mostra su Manico - non cambia) ...
    print("\nPuoi indicare una porzione di manico per la ricerca (es. 0.4)")
    scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
    maninf, mansup = 0, 21
    if scelta_manico != "":
        maninf, mansup = Manlimiti(scelta_manico)
        
    print(f"\nPosizioni sul manico (Tasti {maninf}-{mansup}):")
    note_base_scala = sorted(list(set([n[:-1] for n in note_asc]))) 
    for nota_base in note_base_scala:
        MostraCorde(nota_base, rp=False, maninf=maninf, mansup=mansup)
    
    # --- (Parte 6: Loop Esercizio - LOGICA CORRETTA) ---
    note_asc_str = " ".join([get_nota(n[:-1]) for n in note_asc])
    print(f"\nScala (Asc): {note_asc_str}")
    if not scala_scelta['simmetrica']:
        note_desc_str = " ".join([get_nota(n[:-1]) for n in note_desc])
        print(f"Scala (Desc): {note_desc_str}")
    print("\n--- Menu Esercizio Scala ---")
    bpm = impostazioni['default_bpm']
    loop_attivo = False
    ultima_direzione = 'a' # 'a' ascendente, 'd' discendente
    
    menu_esercizio = {
        "a": "Ascolta ascendente",
        "d": "Ascolta discendente",
        "l": "Attiva/Disattiva Loop",
        "b": "Imposta BPM",
        "i": "Indietro"
    }
    menu(d=menu_esercizio, show=True)
    
    while True:
        if loop_attivo:
            print(f"Loop ATTIVO (BPM: {bpm}) - Ciclo: {loop_count} - Premi 'L' per fermare. ", end="\r", flush=True)
            tasto = key(attesa=0.1) 
            if tasto and tasto.lower() == 'l':
                loop_attivo = False
                print("Loop disattivato.")
                continue
            else:
                scelta = ultima_direzione # Continua a suonare
        else:
            print(f"Loop SPENTO (BPM: {bpm}).")
            scelta = menu(d=menu_esercizio, keyslist=True, ntf="Scelta non valida")

        if scelta == 'i' or scelta is None:
            if loop_attivo:
                loop_attivo = False
                print("\nLoop disattivato.") 
            break
            
        elif scelta == 'l':
            loop_attivo = not loop_attivo
            if loop_attivo:
                loop_count = 1 # <-- (Req 1) Resetta contatore
                print(f"Loop attivato (direzione: {'ascendente' if ultima_direzione == 'a' else 'discendente'}).")
            else:
                print("\nLoop disattivato.")
            continue
            
        elif scelta == 'b':
            nuovo_bpm = dgt(f"Nuovi BPM (attuale: {bpm}): ", kind='i', imin=20, imax=300, default=bpm)
            if nuovo_bpm != bpm:
                bpm = nuovo_bpm
                impostazioni['default_bpm'] = bpm
                archivio_modificato = True
                print(f"BPM predefiniti aggiornati a {bpm}.")            
        elif scelta == 'a' or scelta == 'd':
            ultima_direzione = scelta 
            dur = 60.0 / bpm 
            
            note_da_suonare = []
            if scelta == 'a':
                note_da_suonare = note_asc
            elif scelta == 'd':
                if scala_scelta['simmetrica']:
                    note_da_suonare = list(reversed(note_asc))
                else:
                    note_da_suonare = note_desc
            
            if not note_da_suonare:
                print("Scala non valida o non definita.")
                continue

            score = []
            for nota in note_da_suonare:
                score.extend([nota, dur, 0.0, vol]) 
            
            if not loop_attivo:
                print(f"Riproduzione scala {'ascendente' if scelta == 'a' else 'discendente'} a {bpm} BPM...")
            Acusticator(score, kind=suono_2['kind'], adsr=suono_2['adsr'], sync=False) 
            
            dur_totale = len(note_da_suonare) * dur
            
            if loop_attivo:
                # Se siamo in loop, attendiamo sondando (polling)
                step = 0.05 # 50ms
                passi_totali = int(dur_totale / step)
                tempo_rimanente = dur_totale - (passi_totali * step)
                
                for _ in range(passi_totali):
                    # Usiamo key() come attesa non bloccante
                    tasto = key(attesa=step) 
                    if tasto and tasto.lower() == 'l':
                        loop_attivo = False
                        print("Loop fermato.")
                        # TODO: stop Acusticator (non possibile da doc)
                        break 
                
                if not loop_attivo:
                    continue # Torna al menu
                
                aspetta(tempo_rimanente) # Attendi il residuo
                loop_count += 1 
            else:
                # Se non siamo in loop, basta aspettare
                aspetta(dur_totale)
    print("Fine esercizio.")
# --- Funzioni Segnaposto (Stub per Fase 2) ---

# (Riga 980 circa)

def GestoreChordpedia():
    """Gestisce il DB degli accordi (Implementazione Fase 5 - Corretta)"""
    global archivio_modificato
    print("\n--- La Chordpedia ---")
    print("Gestore del database degli accordi.")
    
    mnaccordi = {
        "v": "Vedi e gestisci accordi",
        "a": "Aggiungi un nuovo accordo",
        "r": "Rimuovi un accordo",
        "i": "Torna al menu principale"
    }
    
    # RIMOSSA: menu(d=mnaccordi, show=True) <-- Era qui
    
    while True:
        # La chiamata 'menu' è ora solo DENTRO il loop
        # Aggiungo show_on_filter=False per pulizia
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

def MenuScale():
    """Gestisce il menu delle scale (Implementazione Fase 6 - Corretta)"""
    print("\n--- Gestore delle Scale ---")
    
    menu_scale_principale = {
        "v": "Visualizza ed esercitati su una scala",
        "a": "Aggiungi una nuova scala",
        "r": "Rimuovi una scala",
        "m": "Modifica una scala",
        "i": "Torna al menu principale"
    }
    
    # RIMOSSA: menu(d=menu_scale_principale, show=True) <-- Era qui
    
    while True:
        scelta = menu(d=menu_scale_principale, keyslist=True, ntf="Scelta non valida", show=True, show_on_filter=False)
        
        if scelta == 'i' or scelta is None:
            print("Ritorno al menu principale.")
            break
        elif scelta == 'v':
            VisualizzaEsercitatiScala()
        elif scelta == 'a':
            AggiungiScala()
        elif scelta == 'r':
            RimuoviScala()
        elif scelta == 'm':
            ModificaScala()
            
        # RIMOSSO: print("\n--- Menu Gestore Scale ---") <-- Era qui
    return
def ModificaSuono(suono_key):
    """
    Funzione helper per modificare i parametri di 'suono_1' o 'suono_2'.
    """
    global archivio_modificato
    
    suono = impostazioni[suono_key]
    print(f"\n--- Modifica {suono['descrizione']} ---")

    # 1. Modifica Tipo di Onda (Kind)
    onda_prompt = f"Tipo di onda (1=Sin, 2=Quadra, 3=Tri, 4=Dente di sega) (attuale: {suono['kind']}): "
    suono['kind'] = dgt(onda_prompt, kind='i', imin=1, imax=4, default=suono['kind'])

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
        print("Questo potrebbe non essere supportato. ADSR non modificato.")
        suono['adsr'] = vecchio_adsr # Ripristina
    else:
        suono['adsr'] = nuovo_adsr

    # 3. Modifica Durata (solo per suono 1)
    if suono_key == 'suono_1':
        dur_prompt = f"Durata suono accordi (sec) (attuale: {suono['dur_accordi']}): "
        suono['dur_accordi'] = dgt(dur_prompt, kind='f', fmin=0.1, fmax=10.0, default=suono['dur_accordi'])

    # 4. Modifica Volume (Aggiunto)
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
# (Riga 879 circa)

def TrovaPosizione():
    """Trova la nota data una posizione C.T e la suona."""
    print("\n--- Trova Posizione (C.T) ---")
    s = dgt("Inserisci Corda.Tasto (es. 6.3): ", smax=5)
    
    if s in CORDE:
        nota_std = CORDE[s]
        print(f"Sulla corda {s.split('.')[0]}, tasto {s.split('.')[1]}, si trova la nota: {get_nota(nota_std)}")
        
        # Suoniamo la nota
        suono_1 = impostazioni['suono_1']
        dur = suono_1['dur_accordi']
        vol = suono_1['volume'] # Aggiunto volume
        
        corda_idx_zero_based = 6 - int(s.split('.')[0])
        pan = -0.8 + (corda_idx_zero_based * 0.32)
        
        score = [nota_std, dur, pan, vol] # Usa vol
        Acusticator(score, kind=suono_1['kind'], adsr=suono_1['adsr'], sync=False)
        
    elif s == "":
        print("Operazione annullata.")
    else:
        print(f"Posizione '{s}' non valida. Formato richiesto: C.T (es. 6.3), tasti da 0 a 21.")
    
    key("Premi un tasto per tornare al menu...")
def main():
    global archivio_modificato, impostazioni
    
    print(f"\nBenvenuto in Chitabry, l'App per familiarizzare con la Chitarra e studiare musica.")
    print(f"\tVersione: {VERSIONE}, di Gabriele Battaglia (IZ4APU)")
    
    carica_impostazioni()
    
    num_accordi = len(impostazioni.get('chordpedia', {}))
    print(f"La tua Chordpedia contiene {num_accordi} accordi.")
    print("\n--- Menu Principale ---")
    
    while True:
        # Mostriamo il menu e attendiamo la scelta
        scelta = menu(d=MAINMENU, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
        
        print(f"\nHai scelto: {scelta}") # Utile per il debug e conferma
        
        if scelta == "Accordi":
            GestoreChordpedia()
        
        elif scelta == "Scale":
            MenuScale()
            
        elif scelta == "Impostazioni":
            GestoreImpostazioni()
            
        elif scelta == "Trova Nota":
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