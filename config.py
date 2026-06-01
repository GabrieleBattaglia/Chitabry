import json
import sys
import strumento

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

NOTE_STD, NOTE_LATINE, NOTE_ANGLO, STD_TO_LATINO, STD_TO_ANGLO = setup_note_constants()
SCALACROMATICA_STD, CAPOTASTI, CORDE = {}, {}, {}
NUM_CORDE, NUM_TASTI = 0, 0
FILE_IMPOSTAZIONI = "chitabry-settings.json"
archivio_modificato = False
impostazioni = {}

def aggiorna_manico():
    global SCALACROMATICA_STD, CAPOTASTI, CORDE, NUM_CORDE, NUM_TASTI, archivio_modificato
    strum_attivo = impostazioni.get('strumento_attivo')
    strumenti = impostazioni.get('strumenti', {})
    
    if not strum_attivo or strum_attivo not in strumenti:
        if 'strumento' in impostazioni:
            # Migrazione
            strum = impostazioni['strumento']
            nome = strum.get('nome', 'Chitarra Standard')
            strumenti[nome] = {
                "accordatura": strum.get('accordatura', ["E2", "A2", "D3", "G3", "B3", "E4"]),
                "tasti": strum.get('tasti', 21)
            }
            impostazioni['strumenti'] = strumenti
            impostazioni['strumento_attivo'] = nome
            strum_attivo = nome
            del impostazioni['strumento']
            archivio_modificato = True
        else:
            strum_attivo = "Chitarra Standard"
            strumenti[strum_attivo] = {
                "accordatura": ["E2", "A2", "D3", "G3", "B3", "E4"],
                "tasti": 21
            }
            impostazioni['strumenti'] = strumenti
            impostazioni['strumento_attivo'] = strum_attivo
            archivio_modificato = True

    strum_conf = strumenti[strum_attivo]
    accordatura = strum_conf.get('accordatura', ["E2", "A2", "D3", "G3", "B3", "E4"])
    num_tasti = strum_conf.get('tasti', 21)
    
    NUM_CORDE = len(accordatura)
    NUM_TASTI = num_tasti
    
    SCALACROMATICA_STD, CAPOTASTI, CORDE = strumento.build_fretboard_data(NOTE_STD, accordatura, num_tasti)


def get_impostazioni_default():
    """Restituisce la struttura dati di default per un nuovo file JSON."""
    return {
        "nomenclatura": "latino",
        "default_bpm": 60,
        "tipo_suono": "suono_1",
        "midi_strumento": 0,
        "midi_in_dispositivo": "",
        "suono_1": {
            "descrizione": "Suono per accordi (Karplus-Strong Pluck)",
            "pluck_hardness": 0.2,    # Range 0.1 (morbido) - 0.9 (aggressivo)
            "damping_factor": 0.998,  # Range 0.990 (corto) - 0.999 (lungo)
            "pick_position": 0.15,    # Range 0.01 (ponte) - 0.5 (manico)
            "brightness": 0.4,        # Range 0.0 (scuro) - 1.0 (brillante)
            "dur_accordi": 9.0,   
            "volume": 0.45
        },
        "suono_2": {
            "descrizione": "Suono sintetico (onda semplice)",
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
        
        # --- Controllo di migrazione (FIX per KeyError: 'volume' E 'bpm') ---
        migrazione_necessaria = False
        
        if 'volume' not in impostazioni.get('suono_1', {}):
            print("Aggiornamento 'suono_1': aggiunta chiave 'volume' di default.")
            if 'suono_1' not in impostazioni:
                impostazioni['suono_1'] = {} # Sicurezza
            impostazioni['suono_1']['volume'] = 0.45
            migrazione_necessaria = True

        if 'pick_position' not in impostazioni.get('suono_1', {}):
            print("Aggiornamento 'suono_1': aggiunta parametri acustici Karplus-Strong.")
            if 'suono_1' not in impostazioni:
                impostazioni['suono_1'] = {}
            impostazioni['suono_1']['pick_position'] = 0.15
            impostazioni['suono_1']['brightness'] = 0.4
            migrazione_necessaria = True            
            
        if 'volume' not in impostazioni.get('suono_2', {}):
            print("Aggiornamento 'suono_2': aggiunta chiave 'volume' di default.")
            if 'suono_2' not in impostazioni: 
                impostazioni['suono_2'] = {} # Sicurezza
            impostazioni['suono_2']['volume'] = 0.35
            migrazione_necessaria = True
            
        if impostazioni.get('suono_2', {}).get('descrizione') == "Suono per scale (simil-flauto)":
            impostazioni['suono_2']['descrizione'] = "Suono sintetico (onda semplice)"
            migrazione_necessaria = True

        # --- Aggiunta controllo 'default_bpm' ---
        if 'default_bpm' not in impostazioni:
            print("Aggiornamento impostazioni: aggiunta chiave 'default_bpm'.")
            impostazioni['default_bpm'] = 60
            migrazione_necessaria = True

        if 'tipo_suono' not in impostazioni:
            print("Aggiornamento impostazioni: aggiunta chiave 'tipo_suono'.")
            impostazioni['tipo_suono'] = 'suono_1'
            migrazione_necessaria = True

        if 'midi_strumento' not in impostazioni:
            print("Aggiornamento impostazioni: aggiunta chiave 'midi_strumento'.")
            impostazioni['midi_strumento'] = 0
            migrazione_necessaria = True
        
        if 'midi_in_dispositivo' not in impostazioni:
            print("Aggiornamento impostazioni: aggiunta chiave 'midi_in_dispositivo'.")
            impostazioni['midi_in_dispositivo'] = ""
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

