# Chitabry dev3 - Studio sulla Chitarra e sulla teoria musicale - di Gabriele Battaglia
# Data concepimento: venerdì 7 febbraio 2020.
# 28 giugno 2024 copiato su Github
# 22 ottobre 2025, versione 4 con importante refactoring

import json, re
from music21 import pitch, chord, scale, interval
import numpy as np
import sounddevice as sd
from scipy import signal
import sys
import random, threading, clitronomo
from time import sleep as aspetta
from GBUtils import dgt, manuale, menu, key

# --- Costanti ---
VERSIONE = "4.4.0 del 27 ottobre 2025."
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
    "Accordi": "Gestisci la tua Chordpedia (Tablature salvate)",
    "Costruttore Accordi": "Analizza/Scopri le note di un accordo", # <-- NUOVA VOCE
    "Metronomo": "Avvia Clitronomo",
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
# --- Funzioni per generare dizionari da music21 (da chiamare una volta all'avvio) ---

def build_scale_dictionary():
    """
    Usa l'introspezione per trovare le classi di scale in music21
    e genera un dizionario {nome_music21: nome_visualizzato}.
    """
    scale_dict = {}
    # Nomi comuni che music21 deriva tramite deriveByTonalityAndMode
    common_scales = [
        "major", "minor", "harmonic minor", "melodic minor",
        "dorian", "phrygian", "lydian", "mixolydian", "aeolian", "ionian", "locrian",
        "pentatonic major", "pentatonic minor", "blues", "chromatic", "whole tone"
    ]
    for name in common_scales:
        # Per questi, il nome music21 e quello visualizzato sono simili
        scale_dict[name] = name.replace(" minor", " Minor").replace(" major", " Major").title()

    # Potremmo aggiungere anche l'introspezione per classi specifiche se servisse,
    # ma deriveByTonalityAndMode copre la maggior parte dei casi utili.
    # Esempio introspezione (più complesso da rendere user-friendly):
    # for name, obj in inspect.getmembers(scale):
    #     if inspect.isclass(obj) and issubclass(obj, scale.AbstractScale) and obj != scale.AbstractScale:
    #         # ... logica per ottenere un nome leggibile dalla classe ...
    #         pass

    # Ordiniamo per nome visualizzato
    return dict(sorted(scale_dict.items(), key=lambda item: item[1]))

def build_chord_type_dictionary():
    """
    Genera un dizionario {nome_music21: nome_visualizzato} per i tipi di accordo,
    combinando qualità base con estensioni/alterazioni comuni.
    """
    # Qualità base riconosciute da music21 (spesso come suffisso o nome completo)
    qualities_m21 = {
        "": "Major",  # Il suffisso vuoto per major
        "m": "Minor",
        "dim": "Diminished",
        "aug": "Augmented",
    }
    # Estensioni/Alterazioni comuni (suffissi)
    extensions_m21 = {
        "7": "7",
        "maj7": "maj7",
        "6": "6",
        "m7": "m7", # Già presente in 'm', ma serve per combinazioni
        "dim7": "dim7", # Già presente in 'dim'
        "m7b5": "m7b5", # Half-diminished
        "sus2": "sus2",
        "sus4": "sus4",
        "9": "9",
        "m9": "m9",
        "maj9": "maj9",
        "11": "11", # Spesso richiede contesto (m11)
        "m11": "m11",
        "13": "13", # Spesso richiede contesto (m13, maj13)
        "m13": "m13",
        "maj13": "maj13",
        "7b5": "7b5",
        "7#5": "7#5",
        "7b9": "7b9",
        "7#9": "7#9",
        "add9": "add9",
        "5": "5", # Power Chord
    }
    # Nomi speciali che non seguono lo schema suffisso
    special_chords = {
         "Neapolitan": "Neapolitan Sixth", # Esempio
    }

    chord_dict = {}

    # Aggiungi le triadi base
    for suffix, display in qualities_m21.items():
        # Saltiamo il major vuoto qui, lo gestiamo dopo
        if suffix: chord_dict[suffix] = display

    # Aggiungi le estensioni/alterazioni comuni (spesso sono tipi completi)
    for suffix, display in extensions_m21.items():
         chord_dict[suffix] = display # music21 spesso li prende come nome completo

    # Aggiungi tipi speciali
    for name, display in special_chords.items():
        chord_dict[name] = display

    # Caso speciale per "Major" (senza suffisso)
    chord_dict[""] = "Major" # Chiave vuota per rappresentare Major Triad

    # Rimuovi eventuali duplicati basati sul valore (nome visualizzato), mantenendo una chiave
    final_dict = {}
    seen_values = set()
    # Ordina per facilitare la ricerca nel menu
    sorted_items = sorted(chord_dict.items(), key=lambda item: (len(item[0]), item[1]))
    for key, value in sorted_items:
        if value not in seen_values:
            final_dict[key] = value
            seen_values.add(value)

    # Aggiungiamo l'opzione manuale alla fine
    final_dict["manuale"] = ">> Inserisci nome manualmente..."

    return final_dict

# --- Variabili Globali per i dizionari generati ---

class Voice:
    """
    Gestisce una singola voce (corda).
    Pre-calcola l'audio ('renderizza') per un callback stabile.
    Usa un lock per la sicurezza tra i thread.
    """
    def __init__(self, fs=FS):
        self.fs = fs
        self.freq = 0.0
        self.vol = 0.0
        self.pan_l, self.pan_r = 0.707, 0.707
        
        self.rendered_stereo_note = np.array([], dtype=np.float32)
        self.read_pos = 0
        self.is_playing = False

        self.adsr_list = [0,0,0,0]
        self.dur = 0
        self.kind = 1
        
        self.lock = threading.Lock() # Lock per la sicurezza

    # --- Oscillatori ---
    def _get_wave_vector(self, freq, n_samples):
        t = np.linspace(0., n_samples / self.fs, n_samples, endpoint=False)
        phase_vector = 2 * np.pi * freq * t
        
        if self.kind == 2: return signal.square(phase_vector)
        elif self.kind == 3: return signal.sawtooth(phase_vector, 0.5)
        elif self.kind == 4: return signal.sawtooth(phase_vector)
        elif self.kind == 5:
            wave = np.zeros(n_samples, dtype=np.float32)
            for i, h_amp in enumerate(HARMONICS):
                wave += np.sin((i + 1) * phase_vector) * h_amp
            max_val = np.max(np.abs(wave))
            if max_val > 0: wave /= max_val
            return wave
        else: # kind 1
            return np.sin(phase_vector)

    # --- Configurazione ---
    def set_params(self, freq, adsr_list, dur, vol, kind, pan):
        """Memorizza i parametri per il rendering."""
        self.freq = freq
        self.vol = vol
        self.adsr_list = adsr_list
        self.dur = dur
        self.kind = kind
        pan_clipped = np.clip(pan, -1.0, 1.0)
        pan_angle = pan_clipped * (np.pi / 4.0)
        self.pan_l = np.cos(pan_angle + np.pi / 4.0)
        self.pan_r = np.sin(pan_angle + np.pi / 4.0)

    def _render_note(self):
        """
        Pre-calcola l'intera nota (onda + envelope).
        """
        if self.freq == 0.0:
            self.rendered_stereo_note = np.array([], dtype=np.float32)
            return

        total_note_samples = int(round(self.dur * self.fs))
        if total_note_samples == 0:
            self.rendered_stereo_note = np.array([], dtype=np.float32)
            return
            
        wave = self._get_wave_vector(self.freq, total_note_samples)
        wave = wave.astype(np.float32)

        a_pct, d_pct, s_level_pct, r_pct = self.adsr_list
        attack_frac = a_pct / 100.0
        decay_frac = d_pct / 100.0
        sustain_level = s_level_pct / 100.0
        release_frac = r_pct / 100.0
        
        attack_samples = int(round(attack_frac * total_note_samples))
        decay_samples = int(round(decay_frac * total_note_samples))
        release_samples = int(round(release_frac * total_note_samples))
        
        # --- (FIX Nota Corta) Calcolo Sustain Corretto ---
        sustain_samples = total_note_samples - (attack_samples + decay_samples + release_samples)
        if sustain_samples < 0:
            # Se A+D+R > 100%, tronca il rilascio
            release_samples += sustain_samples # sustain_samples è negativo
            sustain_samples = 0
            release_samples = max(0, release_samples) # Assicura non sia negativo
        # --- Fine Fix ---

        envelope = np.zeros(total_note_samples, dtype=np.float32)
        current_pos = 0

        if attack_samples > 0:
            attack_samples = min(attack_samples, total_note_samples - current_pos)
            envelope[current_pos : current_pos + attack_samples] = np.linspace(0., 1., attack_samples, dtype=np.float32)
            current_pos += attack_samples
        
        if decay_samples > 0:
            decay_samples = min(decay_samples, total_note_samples - current_pos)
            envelope[current_pos : current_pos + decay_samples] = np.linspace(1., sustain_level, decay_samples, dtype=np.float32)
            current_pos += decay_samples
        
        if sustain_samples > 0:
            sustain_samples = min(sustain_samples, total_note_samples - current_pos)
            envelope[current_pos : current_pos + sustain_samples] = sustain_level
            current_pos += sustain_samples
        
        if release_samples > 0:
            release_samples = min(release_samples, total_note_samples - current_pos)
            if release_samples > 0:
                envelope[current_pos : current_pos + release_samples] = np.linspace(sustain_level, 0., release_samples, dtype=np.float32)
        
        wave *= envelope * self.vol
        
        stereo_segment = np.zeros((total_note_samples, 2), dtype=np.float32)
        stereo_segment[:, 0] = wave * self.pan_l
        stereo_segment[:, 1] = wave * self.pan_r
        
        self.rendered_stereo_note = stereo_segment
    def trigger(self):
        """Attiva la nota (pre-calcola e resetta il playhead)."""
        with self.lock:
            self._render_note() 
            self.read_pos = 0
            self.is_playing = True
        
    def process_additive(self, output_buffer, n_samples):
        """
        Callback audio super-veloce. AGGIUNGE i campioni.
        NON alloca memoria.
        """
        with self.lock:
            if not self.is_playing:
                return 

            samples_left = len(self.rendered_stereo_note) - self.read_pos
            if samples_left <= 0:
                self.is_playing = False
                return

            samples_to_take = min(n_samples, samples_left)
            
            # Aggiunge i campioni (operazione 'in-place')
            output_buffer[0:samples_to_take] += self.rendered_stereo_note[self.read_pos : self.read_pos + samples_to_take]
            
            self.read_pos += samples_to_take

            if samples_to_take < n_samples:
                self.is_playing = False
kind = 1
a_pct = 0.0
d_pct = 0.0
s_level_pct = 0.0
r_pct = 0.0
dur_accordi = 0.0
pan_val = 0.0

# --- Fine Motore Audio Live ---

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
            # --- (FIX Problema 2) Intervalli corretti (Minore Naturale) ---
            "desc": [2, 1, 2, 2, 1, 2, 2], 
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
        "default_bpm": 60,
        "suono_1": {
            "descrizione": "Suono per accordi (simil-chitarra)",
            "kind": 3,
            "adsr": [0.5, 99.0, 0.0, 0.5], 
            "dur_accordi": 3.0, 
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
def Suona(tablatura):
    """
    Permette l'ascolto interattivo di una tablatura.
    Usa il motore 'pre-calcolato' (classe Voice) e sd.play().
    Questo elimina il callback e gli underflow.
    """
    print("\nAscolta le corde:")
    print("Tasti da 1 a 6, (A) pennata in levare, (Q) pennata in battere")
    print("ESC per uscire.")
    
    suono_1 = impostazioni['suono_1']
    kind = suono_1['kind']
    adsr_list = suono_1['adsr']
    dur = suono_1['dur_accordi']
    vol = suono_1['volume']
    
    # Crea 6 voci (ma non le usa in un callback)
    voices = [Voice(fs=FS) for _ in range(6)]
    note_da_suonare = [] # Lista di booleani (se la corda suona)
    note_freq = [] # Lista delle frequenze
    note_pan = [] # Lista dei pan

    # Pre-configura i parametri
    for i in range(6): # i da 0 a 5 (corda 6 a 1)
        corda = 6 - i
        tasto = tablatura[i]
        pan_val = -0.8 + (i * 0.32) 
        note_pan.append(pan_val)
        
        freq = 0.0
        if tasto.isdigit() and f"{corda}.{tasto}" in CORDE:
            nota_std = CORDE[f"{corda}.{tasto}"]
            freq = note_to_freq(nota_std)
        
        note_freq.append(freq)
        note_da_suonare.append(freq > 0) 
        
        # Imposta i parametri per questa voce
        voices[i].set_params(freq, adsr_list, dur, vol, kind, pan_val)

    note_prompt_str = get_note_da_tablatura(tablatura)
    while True:
        # --- MODIFICA OBIETTIVO 1: Aggiunto il prompt alla funzione key() ---
        print(f"Note: {note_prompt_str}): ",end="\r",flush=True)
        scelta = key().lower()
        
        if scelta.isdigit() and scelta in '123456':
            # Tasto 1 = corda 1 = indice 5
            corda_idx_py = 5 - (int(scelta) - 1)
            if note_da_suonare[corda_idx_py]:
                voices[corda_idx_py].trigger() # Renderizza
                if voices[corda_idx_py].rendered_stereo_note.size > 0:
                    sd.play(voices[corda_idx_py].rendered_stereo_note, samplerate=FS, blocking=False)
                
        elif scelta == chr(27): # ESC
            print("Uscita dal menù ascolto.")
            sd.stop() # Ferma qualsiasi suono in riproduzione
            break 
            
        elif scelta == 'a' or scelta == 'q': # Pennata
            sd.stop() # Ferma suoni precedenti
            strum_delay_sec = 0.07
            strum_delay_samples = int(strum_delay_sec * FS)
            note_duration_samples = int(dur * FS)
            
            # Lunghezza totale del buffer = durata nota + 5 delay
            total_samples = note_duration_samples + (5 * strum_delay_samples)
            
            # Crea il buffer di mixaggio finale (silenzio)
            mix_buffer = np.zeros((total_samples, 2), dtype=np.float32)

            note_order = range(6) if scelta == 'q' else range(5, -1, -1)
            
            current_delay_samples = 0
            for i in note_order:
                if note_da_suonare[i]:
                    # Imposta i parametri corretti (trigger li resetta)
                    voices[i].set_params(note_freq[i], adsr_list, dur, vol, kind, note_pan[i])
                    voices[i].trigger() # Renderizza
                    
                    note_data = voices[i].rendered_stereo_note
                    
                    # Assicura che la nota non sia più lunga del buffer
                    if len(note_data) > note_duration_samples:
                        note_data = note_data[:note_duration_samples]
                    
                    # Aggiunge (mixa) la nota al buffer con il ritardo
                    start_pos = current_delay_samples
                    end_pos = start_pos + len(note_data)
                    
                    # Assicura di non scrivere fuori dai limiti
                    if end_pos > total_samples:
                        end_pos = total_samples
                        note_data = note_data[:(end_pos - start_pos)]
                        
                    mix_buffer[start_pos:end_pos] += note_data
                
                current_delay_samples += strum_delay_samples
            
            # Normalizza il buffer se supera 1.0 (per evitare clipping)
            max_val = np.max(np.abs(mix_buffer))
            if max_val > 1.0:
                mix_buffer /= max_val
            
            sd.play(mix_buffer, samplerate=FS, blocking=False)
            
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
    Usa la classe Voice (nuova versione) per generare un
    intero array audio per una scala.
    """
    s_kind = suono_params['kind']
    s_adsr = suono_params['adsr']
    s_vol = suono_params['volume']
    s_dur = 60.0 / bpm
    s_pan = 0.0 # Pan centrale per le scale
    
    voice = Voice(fs=FS)
    segmenti_audio = []

    for nota_str in note_list:
        freq = note_to_freq(nota_str)
        
        # Imposta i parametri e attiva il render
        voice.set_params(freq, s_adsr, s_dur, s_vol, s_kind, s_pan)
        voice.trigger() # Questo ora pre-calcola l'audio
        
        if voice.rendered_stereo_note.size > 0:
            segmenti_audio.append(voice.rendered_stereo_note)
    
    if not segmenti_audio:
        return np.array([], dtype=np.float32)
        
    return np.concatenate(segmenti_audio, axis=0)

def VisualizzaEsercitatiScala():
    """ Versione Ibrida: Menu dinamico + Input manuale """
    global SCALE_TYPES_DICT # Accedi al dizionario globale
    suono_2 = impostazioni['suono_2']

    print("\n--- Visualizza ed Esercitati sulle Scale (music21) ---")

    # --- 1. Scegli Tonica ---
    if impostazioni['nomenclatura'] == 'latino':
        mappa_note = {std: lat for std, lat in STD_TO_LATINO.items() if '#' not in lat and 'b' not in lat and len(std) == 1}
    else:
        mappa_note = {std: anglo for std, anglo in STD_TO_ANGLO.items() if len(std) <= 2}
    tonica_std_base = menu(d=mappa_note, keyslist=True, show=True, pager=12, ntf="Nota non valida", p="Scegli la TONICA della scala: ")
    if tonica_std_base is None:
        print("Operazione annullata.")
        return # Esce dalla funzione
    tonica_std_con_ottava = tonica_std_base + "4" # Aggiunge ottava per music21

    # --- 2. Scegli Tipo di Scala (Menu Dinamico + Manuale) ---
    # Copia il dizionario e aggiungi l'opzione manuale per questo menu
    scale_menu_dict = SCALE_TYPES_DICT.copy()
    scale_menu_dict["manuale"] = ">> Inserisci nome manualmente..."

    tipo_scala_key = menu(d=scale_menu_dict, keyslist=True, show=False,
                           pager=15, ntf="Tipo non valido",
                           p=f"Filtra TIPO scala per {get_nota(tonica_std_base)} (o scegli 'manuale'): ")

    if tipo_scala_key is None:
        print("Operazione annullata.")
        return # Esce dalla funzione

    if tipo_scala_key == "manuale":
        tipo_scala_str_utente = dgt(f"Inserisci TIPO scala per {get_nota(tonica_std_base)} (notazione music21): ", kind="s").strip()
        if not tipo_scala_str_utente:
            print("Operazione annullata.")
            return # Esce dalla funzione
        tipo_scala_music21 = tipo_scala_str_utente # Prova a usarlo direttamente
        nome_scala_display_base = tipo_scala_str_utente
    else:
        tipo_scala_music21 = tipo_scala_key # Chiave già pronta per music21
        nome_scala_display_base = scale_menu_dict[tipo_scala_key] # Nome visualizzato

    # --- 3. Genera la Scala con music21 ---
    scala_m21 = None # Inizializza per il blocco except
    try:
        # Tenta di derivare la scala usando il nome fornito
        scala_m21 = scale.AbstractScale.deriveByTonalityAndMode(pitch.Pitch(tonica_std_con_ottava), tipo_scala_music21)

        # Fallback: Se derive non funziona, prova a cercare una classe Scale con quel nome
        if not scala_m21:
             nome_classe_scala = tipo_scala_music21.replace(" ", "").title().replace("Minor", "Minor").replace("Major", "Major") + "Scale"
             # Correzioni comuni per i nomi delle classi
             if nome_classe_scala == "BluesScale": nome_classe_scala = "MajorBluesScale" # O MinorBluesScale? Da decidere o chiedere
             if nome_classe_scala == "WholeToneScale": nome_classe_scala = "WholeToneScale"
             if nome_classe_scala == "ChromaticScale": nome_classe_scala = "ChromaticScale"

             if hasattr(scale, nome_classe_scala):
                  classe_scala = getattr(scale, nome_classe_scala)
                  scala_m21 = classe_scala(pitch.Pitch(tonica_std_con_ottava)) # Istanzia la classe
             else:
                  # Tentativo finale con ricerca fuzzy (potrebbe essere lento/impreciso)
                  matches = scale.fuzzySearch(tipo_scala_music21)
                  if matches:
                      scala_m21 = matches[0](pitch.Pitch(tonica_std_con_ottava))
                  else:
                      raise ValueError(f"Tipo di scala '{tipo_scala_music21}' non riconosciuto.")

        # Otteniamo le note (oggetti Pitch) per un'ottava ascendente
        # Usiamo pitchList per gestire meglio scale non di 7 note
        pitches_asc = scala_m21.getRealization(pitch.Pitch(tonica_std_con_ottava), pitch.Pitch(tonica_std_base + "5"))


        # Convertiamo le note nel nostro formato standard (SENZA ottava per MostraCorde)
        note_scala_std_asc = []
        note_scala_formattate_asc = []
        for p in pitches_asc:
            nota_str_m21 = p.name.replace('-', 'b')
            nota_base_std = ''.join(filter(lambda c: not c.isdigit(), nota_str_m21))
            # Aggiungiamo solo se non è un duplicato (importante per scale cromatiche/esatonali)
            if nota_base_std not in note_scala_std_asc:
                note_scala_std_asc.append(nota_base_std)
                note_scala_formattate_asc.append(get_nota(nota_base_std))

        # Generiamo le note per l'ascolto (CON ottava) - Ascendente
        # Usiamo .nameWithOctave per avere l'ottava corretta da music21
        note_per_audio_asc = [p.nameWithOctave.replace('-', 'b') for p in pitches_asc]

        # Generiamo la versione discendente per l'ascolto
        # Usiamo pitchList e direction=DESCENDING
        pitches_desc = scala_m21.getRealization(pitch.Pitch(tonica_std_base + "5"), pitch.Pitch(tonica_std_con_ottava), direction=scale.Direction.DESCENDING)
        note_per_audio_desc = [p.nameWithOctave.replace('-', 'b') for p in pitches_desc]


    except Exception as e:
        print(f"\nErrore nella generazione della scala con music21: {e}")
        print(f"Tipo scala tentato: '{tipo_scala_music21}'")
        key("Premi un tasto...")
        return # Esce dalla funzione

    # --- 4. Stampa Riepilogo ---
    # Usa il nome inserito o selezionato dall'utente per coerenza
    nome_scala_display = f"{get_nota(tonica_std_base)} {nome_scala_display_base}"
    note_asc_str = " ".join(note_scala_formattate_asc)
    # Calcola la stringa discendente per il display (senza ottava)
    note_desc_str = " ".join([get_nota(''.join(filter(lambda c: not c.isdigit(), p.name.replace('-','b')))) for p in pitches_desc])

    print(f"\nScala: {nome_scala_display}")
    print(f"Note (Asc): {note_asc_str}")
    # Stampiamo la discendente solo se diversa (per pulizia)
    if note_asc_str != note_desc_str:
         print(f"Note (Desc): {note_desc_str}")


    # --- 5. Mostra su Manico ---
    print("\nPuoi indicare una porzione di manico per la ricerca (es. 0.4)")
    scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
    maninf, mansup = 0, 21
    if scelta_manico != "":
        maninf, mansup = Manlimiti(scelta_manico)

    print(f"\nPosizioni sul manico (Tasti {maninf}-{mansup}):")
    # Usiamo le note senza ottava calcolate prima
    for nota_base in note_scala_std_asc:
        MostraCorde(nota_base, rp=False, maninf=maninf, mansup=mansup)

    # --- 6. Loop Esercizio ---
    print("\n--- Menu Esercizio Scala ---")
    bpm = impostazioni['default_bpm']
    loop_attivo = False
    loop_count = 1
    ultima_direzione = 'a'

    # Cache audio (verrà generata al primo ascolto)
    audio_data_asc = None
    audio_data_desc = None

    menu_esercizio = {
        "a": "Ascolta ascendente",
        "d": "Ascolta discendente",
        "l": "Attiva/Disattiva Loop",
        "b": "Imposta BPM",
        "i": "Indietro"
    }

    menu_mostrato_iniziale = False
    loop_messaggio_stampato = False

    while True:
        audio_to_play = None
        dur_totale = 0.0

        if loop_attivo:
            if not loop_messaggio_stampato:
                print("Loop ATTIVO. Premi 'L' per fermare.")
                loop_messaggio_stampato = True

            note_scala_loop_str = note_asc_str if ultima_direzione == 'a' else note_desc_str
            print(f"Numero ripetizione: {loop_count} - Note: {note_scala_loop_str}", end="\r", flush=True)

            tasto = key(attesa=0.1)
            if tasto and tasto.lower() == 'l':
                loop_attivo = False; print("\nLoop disattivato."); sd.stop(); loop_messaggio_stampato = False; continue
            else:
                scelta = ultima_direzione
        else:
            loop_messaggio_stampato = False
            prompt_scale = f"Note (Asc): {note_asc_str}"
            if note_asc_str != note_desc_str: # Mostra desc solo se diversa
                 prompt_scale += f" | (Desc): {note_desc_str}"

            if not menu_mostrato_iniziale:
                print(f"Note (Asc): {note_asc_str}")
                if note_asc_str != note_desc_str: print(f"Note (Desc): {note_desc_str}")
                scelta = menu(d=menu_esercizio, keyslist=True, ntf="Scelta non valida", show=True, p="> ")
                menu_mostrato_iniziale = True
            else:
                note_da_mostrare = note_asc_str if ultima_direzione == 'a' else note_desc_str
                direzione_str = "Asc" if ultima_direzione == 'a' else "Desc"
                print(f"Note ({direzione_str}): {note_da_mostrare} (Premi '?' per aiuto)      ", end="\r", flush=True)
                scelta = menu(d=menu_esercizio, keyslist=True, ntf="Scelta non valida", show=False, p="")

        # --- Logica di gestione scelte (a, d, l, b, i) ---
        if scelta == 'i' or scelta is None:
            if loop_attivo: loop_attivo = False; print("\nLoop disattivato."); sd.stop()
            if menu_mostrato_iniziale and not loop_attivo: print(" " * 80, end="\r")
            break

        elif scelta == 'l':
            loop_attivo = not loop_attivo
            if loop_attivo: loop_count = 1; print(" " * 80, end="\r")
            else: print("\nLoop disattivato."); sd.stop()
            continue
        elif scelta == 'b':
            global archivio_modificato
            print(" " * 80, end="\r")
            nuovo_bpm = dgt(f"Nuovi BPM (attuale: {bpm}): ", kind='i', imin=20, imax=300, default=bpm)
            if nuovo_bpm != bpm:
                bpm = nuovo_bpm; impostazioni['default_bpm'] = bpm; archivio_modificato = True
                print(f"BPM predefiniti aggiornati a {bpm}.")
                audio_data_asc = None; audio_data_desc = None # Svuota cache

        elif scelta == 'a':
            ultima_direzione = 'a'
            if not note_per_audio_asc: print("Note ascendenti non disponibili."); continue
            if audio_data_asc is None:
                audio_data_asc = render_scale_audio(note_per_audio_asc, suono_2, bpm)
            audio_to_play = audio_data_asc
            dur_totale = len(note_per_audio_asc) * (60.0 / bpm)

        elif scelta == 'd':
            ultima_direzione = 'd'
            if not note_per_audio_desc: print("Note discendenti non disponibili."); continue
            if audio_data_desc is None:
                audio_data_desc = render_scale_audio(note_per_audio_desc, suono_2, bpm)
            audio_to_play = audio_data_desc
            dur_totale = len(note_per_audio_desc) * (60.0 / bpm)

        # --- Logica di riproduzione e attesa (resta identica) ---
        if audio_to_play is not None and audio_to_play.size > 0:
            if not loop_attivo:
                print(" " * 80, end="\r")
                print(f"Riproduzione scala {'ascendente' if scelta == 'a' else 'discendente'} a {bpm} BPM...")

            sd.play(audio_to_play, samplerate=FS, blocking=False)

            if loop_attivo:
                step = 0.05; passi_totali = int(dur_totale / step); tempo_rimanente = dur_totale - (passi_totali * step)
                for _ in range(passi_totali):
                    tasto = key(attesa=step)
                    if tasto and tasto.lower() == 'l':
                        loop_attivo = False; print("\nLoop fermato."); sd.stop(); break
                if not loop_attivo: continue
                aspetta(tempo_rimanente)
                loop_count += 1
            else:
                aspetta(dur_totale)

    print(" " * 80, end="\r")
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

def ModificaSuono(suono_key):
    """
    Funzione helper per modificare i parametri di 'suono_1' o 'suono_2'.
    """
    global archivio_modificato
    
    suono = impostazioni[suono_key]
    print(f"\n--- Modifica {suono['descrizione']} ---")

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
def TrovaPosizione():
    """Trova la nota data una posizione C.T e la suona."""
    print("\n--- Trova Posizione (C.T) ---")
    s = dgt("Inserisci Corda.Tasto (es. 6.3): ", smax=5)
    
    if s in CORDE:
        nota_std = CORDE[s]
        print(f"Sulla corda {s.split('.')[0]}, tasto {s.split('.')[1]}, si trova la nota: {get_nota(nota_std)}")
        
        # Suoniamo la nota usando il motore "one-shot"
        suono_1 = impostazioni['suono_1']
        
        # Calcola parametri
        freq = note_to_freq(nota_std)
        corda_idx_zero_based = 6 - int(s.split('.')[0])
        pan = -0.8 + (corda_idx_zero_based * 0.32)
        dur = suono_1['dur_accordi']
        
        # Crea una singola voce
        voice = Voice(fs=FS)
        
        # Imposta i parametri e attiva il render
        voice.set_params(freq, suono_1['adsr'], dur, suono_1['volume'], suono_1['kind'], pan)
        voice.trigger() # Questo ora pre-calcola l'audio
        
        # Suona (non bloccante) sul buffer renderizzato
        if voice.rendered_stereo_note.size > 0:
            sd.play(voice.rendered_stereo_note, samplerate=FS, blocking=False)
        
    elif s == "":
        print("Operazione annullata.")
    else:
        print(f"Posizione '{s}' non valida. Formato richiesto: C.T (es. 6.3), tasti da 0 a 21.")
    
    key("Premi un tasto per tornare al menu...")

def CostruttoreAccordi():
    """ Versione Ibrida: Menu dinamico + Input manuale """
    global CHORD_TYPES_DICT # Accedi al dizionario globale

    print("\n--- Costruttore di Accordi Teorico (music21) ---")
    print("Scopri quali note compongono qualsiasi accordo.")

    # --- 1. Scegli la Tonica ---
    # Creiamo un dizionario {chiave_standard: valore_visualizzato}
    if impostazioni['nomenclatura'] == 'latino':
        # Mostra DO, RE, MI... ma restituisce C, D, E...
        mappa_note = {std: lat for std, lat in STD_TO_LATINO.items() if '#' not in lat and 'b' not in lat and len(std) == 1} # Solo naturali per ora
        # TODO: Migliorare la visualizzazione/selezione di #/b per Latino
    else:
        # Mostra C, D, E... e restituisce C, D, E...
        mappa_note = {std: anglo for std, anglo in STD_TO_ANGLO.items() if len(std) <= 2} # Includi #/b

    # La chiamata a menu resta uguale, ma ora 'd' è costruito correttamente
    tonica_std = menu(d=mappa_note, keyslist=True, show=True, # Mostra il menu con i valori corretti
                        pager=12, ntf="Nota non valida", p="Scegli la TONICA: ")
    if tonica_std is None:
        print("Costruzione annullata.")
        return

    # --- 2. Scegli il Tipo di Accordo (Menu Dinamico + Manuale) ---
    # Usiamo il dizionario globale CHORD_TYPES_DICT generato all'avvio
    # La chiave 'manuale' avrà come valore ">> Inserisci nome manualmente..."
    tipo_accordo_key = menu(d=CHORD_TYPES_DICT, keyslist=True, show=False,
                             pager=15, ntf="Tipo non valido",
                             p=f"Filtra TIPO accordo per {get_nota(tonica_std)} (o scegli 'manuale'): ")

    if tipo_accordo_key is None:
        print("Costruzione annullata.")
        return # Esce dalla funzione

    if tipo_accordo_key == "manuale":
        # Chiedi input libero
        tipo_accordo_str_utente = dgt(f"Inserisci TIPO accordo per {get_nota(tonica_std)} (notazione music21): ", kind="s").strip()
        if not tipo_accordo_str_utente:
            print("Costruzione annullata.")
            return # Esce dalla funzione
        # Per music21, spesso il nome base (major) è implicito o vuoto
        if tipo_accordo_str_utente.lower() in ["major", "maggiore"]:
            tipo_accordo_music21 = "" # music21 capisce "C" come C major
        else:
            tipo_accordo_music21 = tipo_accordo_str_utente # Prova a usarlo direttamente
        nome_accordo_display_base = tipo_accordo_str_utente # Usiamo quello che ha scritto l'utente per il display

    else:
        # L'utente ha scelto dal menu, usiamo la chiave selezionata (che è già formattata per music21)
        tipo_accordo_music21 = tipo_accordo_key
        nome_accordo_display_base = CHORD_TYPES_DICT[tipo_accordo_key] # Nome visualizzato dal menu

# --- 3. Crea l'Accordo con music21 (Metodo Unificato - Revisione Triadi) ---
    nome_input_per_m21 = "" # Per tracciare cosa passiamo a music21
    accordo_m21 = None      # Inizializza l'oggetto accordo
    try:
        p = pitch.Pitch(tonica_std)

        # --- Logica Specifica per Tipi Base ---
        if tipo_accordo_music21 == "": # Major Triad
            # Tentativo 1: Nome completo "C major" (più esplicito)
            nome_input_per_m21 = p.name + " major"
            accordo_m21 = chord.Chord(nome_input_per_m21)
            # Fallback: Se "C major" non va, prova solo "C" (meno probabile ma per sicurezza)
            if accordo_m21 is None or not accordo_m21.pitches:
                 nome_input_per_m21 = p.name
                 accordo_m21 = chord.Chord(nome_input_per_m21)

        elif tipo_accordo_music21 == "m": # Minor Triad
             # Tentativo 1: Abbreviazione "Cm"
             nome_input_per_m21 = p.name + "m"
             accordo_m21 = chord.Chord(nome_input_per_m21)
             # Fallback: Se "Cm" non va, prova nome completo "C minor"
             if accordo_m21 is None or not accordo_m21.pitches:
                  nome_input_per_m21 = p.name + " minor"
                  accordo_m21 = chord.Chord(nome_input_per_m21)

        elif tipo_accordo_music21 == "dim": # Diminished Triad
             # Tentativo 1: Abbreviazione "Cdim"
             nome_input_per_m21 = p.name + "dim"
             accordo_m21 = chord.Chord(nome_input_per_m21)
             # Fallback: Se "Cdim" non va, prova nome completo "C diminished"
             if accordo_m21 is None or not accordo_m21.pitches:
                  nome_input_per_m21 = p.name + " diminished"
                  accordo_m21 = chord.Chord(nome_input_per_m21)

        elif tipo_accordo_music21 == "aug": # Augmented Triad
             # Tentativo 1: Abbreviazione "Caug"
             nome_input_per_m21 = p.name + "aug"
             accordo_m21 = chord.Chord(nome_input_per_m21)
             # Fallback: Se "Caug" non va, prova nome completo "C augmented"
             if accordo_m21 is None or not accordo_m21.pitches:
                  nome_input_per_m21 = p.name + " augmented"
                  accordo_m21 = chord.Chord(nome_input_per_m21)

        else: # Per tutti gli altri tipi (7, maj7, m7, dim7, 7b9...)
             # Usa la notazione compatta standard Radice+Tipo
             nome_input_per_m21 = p.name + tipo_accordo_music21
             accordo_m21 = chord.Chord(nome_input_per_m21)
             # Fallback specifico per dim7 se la notazione compatta fallisce
             if (accordo_m21 is None or not accordo_m21.pitches) and tipo_accordo_music21 == "dim7":
                  nome_input_per_m21 = p.name + " diminished seventh"
                  accordo_m21 = chord.Chord(nome_input_per_m21)


        # --- Verifica Finale ---
        if accordo_m21 is None or not accordo_m21.pitches:
             # Se NESSUN tentativo ha prodotto un accordo con note, solleva errore
             raise ValueError(f"Music21 non è riuscito a interpretare l'accordo.")

        # --- Se siamo qui, accordo_m21 è valido ---
        note_accordo_obj = accordo_m21.pitches

        # Converti le note nel nostro formato standard (C, C#, Db, etc.)
        note_accordo_std = []
        note_accordo_formattate = []
        for p_note in note_accordo_obj:
            nota_str_m21 = p_note.name # music21 usa # e - per bemolle
            nota_base_std = nota_str_m21.replace('-', 'b')
            nota_base_std = ''.join(filter(lambda c: not c.isdigit(), nota_base_std))
            if nota_base_std not in note_accordo_std:
                 note_accordo_std.append(nota_base_std)
                 note_accordo_formattate.append(get_nota(nota_base_std))

    except Exception as e:
        print(f"\nErrore nella creazione dell'accordo con music21: {e}")
        if nome_input_per_m21: print(f"Ultimo input tentato per music21: '{nome_input_per_m21}'")
        print(f"Verifica la correttezza del tipo inserito o selezionato.")
        key("Premi un tasto...")
        return # Esce dalla funzione
    # --- 4. Mostra i Risultati ---
    nome_accordo_display = f"{get_nota(tonica_std)} {nome_accordo_display_base}"
    note_str = " - ".join(note_accordo_formattate)
    print(f"\n--- Risultato Analisi (music21) ---")
    print(f"Accordo: {nome_accordo_display}")
    print(f"Note componenti: {note_str}")
    print("-----------------------------------")
    # --- 5. Mostra sul Manico ---
    print(f"\nEcco dove trovare queste note sul manico:")
    print("Puoi indicare una porzione di manico (es. 0.4)")
    scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
    maninf, mansup = 0, 21
    if scelta_manico != "":
        maninf, mansup = Manlimiti(scelta_manico)

    for nota_base in note_accordo_std:
        MostraCorde(nota_base, rp=False, maninf=maninf, mansup=mansup)

    print("\nUsando queste posizioni, puoi trovare una diteggiatura e salvarla nella tua Chordpedia.")
    key("Premi un tasto per tornare al menu...")
    return # Fine funzione
def main():
    global SCALE_TYPES_DICT, CHORD_TYPES_DICT, archivio_modificato, impostazioni
    print(f"\nBenvenuto in Chitabry, l'App per familiarizzare con la Chitarra e studiare musica.")
    print(f"\tVersione: {VERSIONE}, di Gabriele Battaglia (IZ4APU)")
    
    carica_impostazioni()
    # --- POPOLA I DIZIONARI DINAMICI ---
    print("Analisi libreria music21 per scale e accordi...")
    SCALE_TYPES_DICT = build_scale_dictionary()
    CHORD_TYPES_DICT = build_chord_type_dictionary()
    print(f"Trovati {len(SCALE_TYPES_DICT)} tipi di scale e {len(CHORD_TYPES_DICT)-1} tipi di accordi comuni.") # -1 per l'opzione manuale

    num_accordi = len(impostazioni.get('chordpedia', {}))
    num_scale = len(impostazioni.get('scale', {}))
    print(f"La tua Chordpedia contiene {num_accordi} accordi e {num_scale} pattern di scale.")
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
        elif scelta == "Scale":
            VisualizzaEsercitatiScala()
            
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