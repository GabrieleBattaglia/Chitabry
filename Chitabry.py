# Chitabry - Studio sulla Chitarra e sulla teoria musicale - di Gabriele Battaglia e Gemini 3.5 Flash
# Data concepimento: venerdì 7 febbraio 2020.

from time import sleep as aspetta
import sys
from GBUtils import menu
import config
import scale_catalog
import views

# --- Costanti ---
VERSIONE = "7.7.0 del 31 maggio 2026."

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
    "Guida": "Mostra la guida di Chitabry"
}

def main():
    from GBUtils import update_checker, perform_update, enter_escape

    # Auto-Updater
    if getattr(sys, 'frozen', False):
        api_url = "https://api.github.com/repos/GabrieleBattaglia/Chitabry/releases/latest"
        print("Ricerca aggiornamenti in corso...")
        has_update, new_ver, dl_url, changelog = update_checker(VERSIONE, api_url)
        if has_update:
            if dl_url:
                print("\n*** AGGIORNAMENTO DISPONIBILE ***")
                print(f"E' disponibile la nuova versione {new_ver}! (Attuale: {VERSIONE})")
                if enter_escape("Desideri scaricare e installare l'aggiornamento ora? (INVIO per si', ESC per ignorare): "):
                    print("Download dell'aggiornamento in corso. Attendere prego...")
                    if perform_update(dl_url, "Chitabry"):
                        print("Aggiornamento pronto. Chitabry si chiudera' per l'installazione...")
                        sys.exit(0)
                    else:
                        print("Si e' verificato un errore durante la preparazione dell'aggiornamento.")
            else:
                print("\n*** AGGIORNAMENTO DISPONIBILE ***")
                print(f"E' disponibile la nuova versione {new_ver}, ma i file di installazione non sono ancora pronti per il download.")
                print("Riprova piu' tardi.")
        else:
            print(f"Hai gia' l'ultima versione disponibile ({VERSIONE})!")

    config.carica_impostazioni()
    config.aggiorna_manico()

    import midistudy
    midistudy.check_midi_folder_cleanup()

    strum_attivo = config.impostazioni.get("strumento_attivo", "Chitarra Standard")
    print(f"\nBenvenuto in Chitabry, l'App per familiarizzare con il tuo strumento ({strum_attivo}) e studiare musica.")
    print(f"\tVersione: {VERSIONE}, di Gabriele Battaglia (IZ4APU)")
    
    # --- POPOLA I DIZIONARI DINAMICI ---
    print("Analisi libreria music21 per scale e accordi...")
    scale_catalog.SCALE_CATALOG = scale_catalog.build_scale_catalog()
    temp_scale_types = {}
    for scale_info in scale_catalog.SCALE_CATALOG:
        prog_id = scale_info['programmatic_id']
        paradigm = scale_info['paradigm']
        friendly_name = scale_info['friendly_name']
        unique_key = f"{paradigm}:{prog_id}"
        temp_scale_types[unique_key] = friendly_name

    # Aggiungi l'opzione manuale all'inizio con chiave speciale "..."
    scale_catalog.SCALE_TYPES_DICT = {"...": ">> Inserisci USI manualmente..."}
    scale_catalog.SCALE_TYPES_DICT.update(temp_scale_types)
    scale_catalog.USER_CHORD_DICT = scale_catalog.get_user_chord_dictionary()
    print(f"Riconosciuti {len(scale_catalog.SCALE_TYPES_DICT)} tipi di scale e {len(scale_catalog.USER_CHORD_DICT)-1} tipi di accordi.")

    print("\nPremere '?' per visualizzare il menu delle opzioni.")
    
    while True:
        # Pulisci eventuali voci del manico precedenti per evitare accumuli
        for k in list(MAINMENU.keys()):
            if k.startswith("Manico dello strumento"):
                del MAINMENU[k]

        strum_attivo = config.impostazioni.get("strumento_attivo", "Chitarra Standard")
        MAINMENU[f"Manico dello strumento {strum_attivo}"] = f"Mostra lo schema del manico per {strum_attivo}"

        scelta = menu(d=MAINMENU, keyslist=True, show=False, show_on_filter=False, ntf="Scelta non valida")
        
        if scelta is None:
            break
            
        print(f"\nHai scelto: {scelta}")
        
        if scelta == "Costruttore Accordi":
            views.CostruttoreAccordi()
        elif scelta == "Tastiera":
            views.PlayerGenerico()
        elif scelta == "Accordatore":
            views.Accordatore()
        elif scelta == "Gioca col suono":
            views.GiocaColSuono()
        elif scelta == "Metronomo":
            print("\nAvvio del Metronomo...")
            aspetta(0.5)
            import clitronomo
            clitronomo.main()
            print("\n--- Ritorno al Menu Principale di Chitabry ---")
        elif scelta == "MidiStudy":
            midistudy.MidiStudyMain()
        elif scelta == "Scale":
            views.VisualizzaEsercitatiScala()
        elif scelta == "Flauto":
            views.GestoreFlauto()
        elif scelta == "Impostazioni":
            views.GestoreImpostazioni()
        elif scelta == "Nota sul manico":
            views.TrovaNota()
        elif scelta == "Trova Posizione":
            views.TrovaPosizione()
        elif scelta.startswith("Manico dello strumento"):
            views.VisualizzaManico()
        elif scelta == "Guida":
            from GBUtils import manuale
            manuale("ChitabryMan.txt")
        elif scelta == "Esci" or scelta is None:
            break
            
        print("\n--- Ritorno al Menu Principale ---")

    config.salva_impostazioni()
    print(f"Arrivederci da Chitabry versione: {VERSIONE}")
    aspetta(0.2)
    sys.exit()

if __name__ == "__main__":
    main()
