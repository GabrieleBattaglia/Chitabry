# Chitabry, studio della chitarra e della teoria musicale.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Data di concepimento: venerdi' 7 febbraio 2020.

import sys
from time import sleep as aspetta

from GBUtils import gestisci_aggiornamento, manuale, menu

import accordatore
import config
import costruttore_accordi
import esercizio_scale
import flauto
import gestore_impostazioni
import gioca_suono
import manico
import player
import scale_catalog
from versione import API_RELEASE, APP_NAME, AUTORI, VERSIONE, data_italiana

VOCE_MANICO = "Manico dello strumento"
MAINMENU = {
    "Costruttore Accordi": "Analizza/Scopri le note di un accordo",
    "Tastiera": "Suona liberamente con la tastiera del PC",
    "Accordatore": "Avvia l'accordatore acustico per il tuo strumento",
    "Flauto": "Consulta la diteggiatura del flauto traverso",
    "Metronomo": "Avvia il Metronomo",
    "MidiStudy": "Analizza e studia file MIDI",
    "Scale": "Visualizza, esercitati e gestisci le scale",
    "Gioca col suono": "Allena l'orecchio riconoscendo note e frequenze",
    "Impostazioni": "Configura i suoni e la notazione delle note",
    "Nota sul manico": "Trova le posizioni di una nota sul manico",
    "Trova Posizione": "Indica la nota su una corda/tasto (C.T)",
    VOCE_MANICO: "Mostra lo schema del manico dello strumento attivo",
    "Guida": "Mostra la guida di Chitabry",
}


def mostra_guida():
    """La guida si legge dal pacchetto compilato o da accanto ai sorgenti.
    Dalla V2.0.0 manuale solleva invece di stampare da sola: il messaggio lo
    scriviamo qui perche' e' Chitabry a sapere cos'e' quel file e a chi chiederlo."""
    try:
        manuale(config.percorso_risorsa("ChitabryMan.txt"), nome="Guida di Chitabry")
    except (OSError, ValueError):
        print("La guida non e' insieme al programma. Richiedila all'autore.")


def collega_tastiera_midi():
    """Riapre all'avvio la tastiera MIDI scelta nelle impostazioni, se c'e' ancora."""
    import GBAudio
    dispositivo_salvato = config.impostazioni.get("midi_in_dispositivo", "")
    if not dispositivo_salvato:
        return
    dispositivi = GBAudio.get_midi_in_devices()
    if dispositivo_salvato in dispositivi:
        GBAudio.open_global_midi_in(dispositivi.index(dispositivo_salvato))
        print(f"Tastiera MIDI connessa all'avvio: {dispositivo_salvato}")
    else:
        print(f"La tastiera MIDI {dispositivo_salvato} non risulta collegata.")


def costruisci_cataloghi():
    """Interroga music21 una volta sola per i tipi di scale e di accordi."""
    print("Analisi libreria music21 per scale e accordi...")
    scale_catalog.SCALE_CATALOG = scale_catalog.build_scale_catalog()
    tipi = {"...": ">> Inserisci USI manualmente..."}
    for scale_info in scale_catalog.SCALE_CATALOG:
        chiave = f"{scale_info['paradigm']}:{scale_info['programmatic_id']}"
        tipi[chiave] = scale_info['friendly_name']
    scale_catalog.SCALE_TYPES_DICT = tipi
    scale_catalog.USER_CHORD_DICT = scale_catalog.get_user_chord_dictionary()
    print(f"Riconosciuti {len(tipi)} tipi di scale e {len(scale_catalog.USER_CHORD_DICT) - 1} tipi di accordi.")


AZIONI = {
    "Costruttore Accordi": costruttore_accordi.CostruttoreAccordi,
    "Tastiera": player.PlayerGenerico,
    "Accordatore": accordatore.Accordatore,
    "Gioca col suono": gioca_suono.avvia,
    "Scale": esercizio_scale.VisualizzaEsercitatiScala,
    "Flauto": flauto.GestoreFlauto,
    "Impostazioni": gestore_impostazioni.GestoreImpostazioni,
    "Nota sul manico": manico.TrovaNota,
    "Trova Posizione": manico.TrovaPosizione,
    VOCE_MANICO: manico.VisualizzaManico,
    "Guida": mostra_guida,
}


def avvia_metronomo():
    print("Avvio del Metronomo...")
    aspetta(0.5)
    import clitronomo
    clitronomo.main()


def avvia_midistudy():
    import midistudy
    midistudy.MidiStudyMain()


def main():
    if gestisci_aggiornamento(APP_NAME, VERSIONE, API_RELEASE):
        sys.exit(0)
    config.carica_impostazioni()
    config.aggiorna_manico()
    collega_tastiera_midi()
    import midistudy
    midistudy.check_midi_folder_cleanup()
    strum_attivo = config.impostazioni.get("strumento_attivo", config.STRUMENTO_PREDEFINITO)
    print(f"Benvenuto in Chitabry, l'App per familiarizzare con il tuo strumento ({strum_attivo}) e studiare musica.")
    print(f"Versione {VERSIONE} del {data_italiana()}, di {AUTORI}.")
    costruisci_cataloghi()
    print("Premere '?' per visualizzare il menu delle opzioni.")
    while True:
        strum_attivo = config.impostazioni.get("strumento_attivo", config.STRUMENTO_PREDEFINITO)
        MAINMENU[VOCE_MANICO] = f"Mostra lo schema del manico per {strum_attivo}"
        scelta = menu(d=MAINMENU, keyslist=True, show=False, show_on_filter=False, ntf="Scelta non valida")
        if scelta is None:
            break
        print(f"Hai scelto: {scelta}")
        if scelta == "Metronomo":
            avvia_metronomo()
        elif scelta == "MidiStudy":
            avvia_midistudy()
        else:
            AZIONI[scelta]()
        print("Ritorno al menu principale.")
    config.salva_impostazioni()
    print(f"Arrivederci da Chitabry versione {VERSIONE}.")
    aspetta(0.2)
    sys.exit()


if __name__ == "__main__":
    main()
