# Chitabry, impostazioni: l'archivio dell'utente, le costanti delle note e il manico attivo.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Revisione 1 del 2026-09-09: i percorsi si ricavano dalla cartella del
# programma e non piu' dalla directory di lavoro; il salvataggio scrive su un
# file temporaneo e conserva la versione precedente come copia .bak; ogni
# modifica si salva subito; il formato dell'archivio porta un numero di
# versione e le chiavi mancanti si completano dai valori predefiniti.

import json
import os
import sys

from GBUtils import cartella_applicazione
from GBUtils import percorso_risorsa as percorso_risorsa_condivisa

import strumento


def cartella_dati():
    """Cartella dei file dell'utente: accanto all'eseguibile se il programma e'
    compilato, accanto ai sorgenti altrimenti. Mai la directory di lavoro:
    avviando Chitabry da un collegamento con una cartella di partenza diversa
    le impostazioni risultavano azzerate.
    La logica sta in GBUtils, come tutte le utilita' condivise: qui resta il
    nome con cui Chitabry la chiama."""
    return cartella_applicazione()


def percorso_risorsa(nome):
    """Dove sta una risorsa in sola lettura, come la guida: da compilato dentro
    il pacchetto, dove PyInstaller mette i dati, altrimenti accanto ai sorgenti."""
    return percorso_risorsa_condivisa(nome)


BASE_DIR = cartella_dati()
FILE_IMPOSTAZIONI = os.path.join(BASE_DIR, "chitabry-settings.json")
CARTELLA_MIDI = os.path.join(BASE_DIR, "midi")
# Numero di versione del formato dell'archivio. Si alza quando una chiave
# cambia nome o significato; l'aggiunta di una chiave nuova non lo richiede,
# perche' le chiavi mancanti si completano da sole dai valori predefiniti.
VERSIONE_FORMATO = 1

NOTE_STD = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
NOTE_LATINE = ['DO', 'DO#', 'RE', 'RE#', 'MI', 'FA', 'FA#', 'SOL', 'SOL#', 'LA', 'LA#', 'SI']
# La nomenclatura anglosassone coincide con quella standard di music21, quindi
# la sua tabella e' un'identita'. Esiste solo perche' il codice che traduce le
# note scelga una mappa in base alla nomenclatura senza fare un caso a parte.
NOTE_ANGLO = NOTE_STD
STD_TO_LATINO = dict(zip(NOTE_STD, NOTE_LATINE, strict=True))
STD_TO_LATINO.update({'Db': 'REb', 'Eb': 'MIb', 'Gb': 'SOLb', 'Ab': 'LAb', 'Bb': 'SIb'})
STD_TO_ANGLO = {nota: nota for nota in NOTE_STD}

STRUMENTO_PREDEFINITO = "Chitarra Standard"
ACCORDATURA_CHITARRA = ["E2", "A2", "D3", "G3", "B3", "E4"]
TASTI_PREDEFINITI = 21

SCALACROMATICA_STD, CAPOTASTI, CORDE = {}, {}, {}
NUM_CORDE, NUM_TASTI = 0, 0
archivio_modificato = False
impostazioni = {}


def get_impostazioni_default():
    """Restituisce la struttura dati di default per un nuovo file JSON."""
    return {
        "versione_formato": VERSIONE_FORMATO,
        "nomenclatura": "latino",
        "default_bpm": 60,
        "tipo_suono": "suono_1",
        "midi_strumento": 0,
        "midi_in_dispositivo": "",
        "strumento_attivo": STRUMENTO_PREDEFINITO,
        "strumenti": {
            STRUMENTO_PREDEFINITO: {
                "accordatura": list(ACCORDATURA_CHITARRA),
                "tasti": TASTI_PREDEFINITI,
            }
        },
        "suono_1": {
            "descrizione": "Suono per accordi (Karplus-Strong Pluck)",
            "pluck_hardness": 0.2,    # da 0.1 (morbido) a 0.9 (aggressivo)
            "damping_factor": 0.998,  # da 0.990 (corto) a 0.999 (lungo)
            "pick_position": 0.15,    # da 0.01 (ponte) a 0.5 (manico)
            "brightness": 0.4,        # da 0.0 (scuro) a 1.0 (brillante)
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


def _migra(dati):
    """Porta un archivio letto da disco al formato corrente.
    Restituisce l'elenco dei cambiamenti fatti, vuoto se non ce n'erano.
    Prima si applicano le trasformazioni legate alla versione del formato,
    poi si completano le chiavi mancanti dai valori predefiniti: cosi' una
    chiave nuova non richiede un controllo in piu' a ogni versione."""
    cambiamenti = []
    formato = dati.get("versione_formato", 0)
    if not isinstance(formato, int):
        formato = 0
    if formato < 1:
        if dati.get("suono_2", {}).get("descrizione") == "Suono per scale (simil-flauto)":
            dati["suono_2"]["descrizione"] = "Suono sintetico (onda semplice)"
            cambiamenti.append("Descrizione del suono 2 aggiornata.")
        if "strumento" in dati:
            # Fino alla 7.3 c'era un solo strumento, sotto la chiave strumento.
            vecchio = dati.pop("strumento")
            nome = vecchio.get("nome", STRUMENTO_PREDEFINITO)
            strumenti = dati.setdefault("strumenti", {})
            strumenti[nome] = {
                "accordatura": vecchio.get("accordatura", list(ACCORDATURA_CHITARRA)),
                "tasti": vecchio.get("tasti", TASTI_PREDEFINITI),
            }
            dati["strumento_attivo"] = nome
            cambiamenti.append(f"Strumento {nome} portato nell'elenco degli strumenti.")
    predefiniti = get_impostazioni_default()
    for chiave, valore in predefiniti.items():
        if chiave == "versione_formato":
            continue
        if chiave not in dati:
            dati[chiave] = valore
            cambiamenti.append(f"Aggiunta l'impostazione {chiave}.")
    for suono in ("suono_1", "suono_2"):
        if not isinstance(dati.get(suono), dict):
            dati[suono] = predefiniti[suono]
            cambiamenti.append(f"Parametri di {suono} ripristinati ai valori predefiniti.")
            continue
        for chiave, valore in predefiniti[suono].items():
            if chiave not in dati[suono]:
                dati[suono][chiave] = valore
                cambiamenti.append(f"Aggiunto il parametro {chiave} a {suono}.")
    if dati.get("versione_formato") != VERSIONE_FORMATO:
        dati["versione_formato"] = VERSIONE_FORMATO
        cambiamenti.append(f"Formato dell'archivio portato alla versione {VERSIONE_FORMATO}.")
    return cambiamenti


def carica_impostazioni():
    """Carica le impostazioni da FILE_IMPOSTAZIONI.
    Se il file non esiste lo crea con i valori di default; se e' illeggibile
    si ferma ed esce, perche' sovrascriverlo cancellerebbe la chordpedia e gli
    strumenti dell'utente: la copia precedente, se c'e', e' nel file .bak."""
    global impostazioni, archivio_modificato
    try:
        with open(FILE_IMPOSTAZIONI, encoding='utf-8') as f:
            dati = json.load(f)
        if not isinstance(dati, dict):
            raise ValueError("il contenuto non e' un dizionario di impostazioni")
    except FileNotFoundError:
        print(f"File {FILE_IMPOSTAZIONI} non trovato. Ne creo uno nuovo con i valori predefiniti.")
        impostazioni = get_impostazioni_default()
        salva_modifiche()
        return
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError, OSError) as e:
        print(f"Il file delle impostazioni {FILE_IMPOSTAZIONI} non si legge: {e}")
        copia = FILE_IMPOSTAZIONI + ".bak"
        if os.path.exists(copia):
            print(f"La versione precedente e' in {copia}: rinominala per ripartire da quella.")
        print("Chitabry si chiude senza toccare il file.")
        sys.exit(1)
    impostazioni = dati
    cambiamenti = _migra(impostazioni)
    if cambiamenti:
        for riga in cambiamenti:
            print(riga)
        print("Impostazioni aggiornate alla versione corrente.")
        salva_modifiche()


def aggiorna_manico():
    """Ricostruisce le tabelle del manico per lo strumento attivo.
    Se lo strumento attivo non esiste piu' nell'elenco, ripiega sul primo
    disponibile o sulla chitarra standard, e lo scrive nell'archivio."""
    global SCALACROMATICA_STD, CAPOTASTI, CORDE, NUM_CORDE, NUM_TASTI
    strumenti = impostazioni.setdefault('strumenti', {})
    strum_attivo = impostazioni.get('strumento_attivo')
    if not strum_attivo or strum_attivo not in strumenti:
        if not strumenti:
            strumenti[STRUMENTO_PREDEFINITO] = {
                "accordatura": list(ACCORDATURA_CHITARRA),
                "tasti": TASTI_PREDEFINITI,
            }
        strum_attivo = next(iter(strumenti))
        impostazioni['strumento_attivo'] = strum_attivo
        salva_modifiche()
    strum_conf = strumenti[strum_attivo]
    accordatura = strum_conf.get('accordatura', ACCORDATURA_CHITARRA)
    num_tasti = strum_conf.get('tasti', TASTI_PREDEFINITI)
    NUM_CORDE = len(accordatura)
    NUM_TASTI = num_tasti
    SCALACROMATICA_STD, CAPOTASTI, CORDE = strumento.build_fretboard_data(NOTE_STD, accordatura, num_tasti)


def salva_impostazioni():
    """Scrive l'archivio su disco se e' stato modificato.
    Scrive su un file temporaneo nella stessa cartella e lo sostituisce al
    precedente con os.replace, conservando la versione prima come copia .bak:
    un'interruzione durante la scrittura non lascia mai un file troncato.
    Restituisce True se non c'era niente da scrivere o se ha scritto."""
    global archivio_modificato
    if not archivio_modificato:
        return True
    temporaneo = FILE_IMPOSTAZIONI + ".tmp"
    try:
        with open(temporaneo, 'w', encoding='utf-8') as f:
            json.dump(impostazioni, f, indent=4, ensure_ascii=False)
        if os.path.exists(FILE_IMPOSTAZIONI):
            os.replace(FILE_IMPOSTAZIONI, FILE_IMPOSTAZIONI + ".bak")
        os.replace(temporaneo, FILE_IMPOSTAZIONI)
    except OSError as e:
        print(f"Impossibile salvare le impostazioni in {FILE_IMPOSTAZIONI}: {e}")
        return False
    archivio_modificato = False
    return True


def salva_modifiche():
    """Segna l'archivio come modificato e lo scrive subito.
    E' la via da usare dopo ogni cambiamento: fino alla 7.8 si scriveva solo
    all'uscita ordinata dal menu, e un Ctrl+C o una finestra chiusa perdevano
    tutto il lavoro di configurazione della sessione."""
    global archivio_modificato
    archivio_modificato = True
    return salva_impostazioni()
