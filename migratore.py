import json
import os

FILE_IMPOSTAZIONI = "chitabry-settings.json"
BACKUP_FILE = "chitabry-settings.json.backup"

# Questi sono i nuovi valori di default per il suono 1
DEFAULT_HARDNESS = 0.6
DEFAULT_DAMPING = 0.997

def migra_impostazioni():
    """
    Script "oneshot" per aggiornare chitabry-settings.json
    al nuovo formato Karplus-Strong per suono_1.
    
    Rimuove 'kind' e 'adsr' da 'suono_1'.
    Aggiunge 'pluck_hardness' e 'damping_factor' a 'suono_1'.
    """
    print(f"--- Migratore Impostazioni Chitabry ---")
    
    # --- 1. Controllo Esistenza File ---
    if not os.path.exists(FILE_IMPOSTAZIONI):
        print(f"ERRORE: File '{FILE_IMPOSTAZIONI}' non trovato.")
        print("Assicurati di eseguire questo script nella stessa cartella del file.")
        input("Premi Invio per uscire.")
        return

    # --- 2. Caricamento ---
    try:
        with open(FILE_IMPOSTAZIONI, 'r', encoding='utf-8') as f:
            impostazioni = json.load(f)
        print(f"Caricato file '{FILE_IMPOSTAZIONI}'.")
    except json.JSONDecodeError:
        print(f"ERRORE: Il file '{FILE_IMPOSTAZIONI}' è corrotto o malformato.")
        print("Impossibile eseguire la migrazione.")
        input("Premi Invio per uscire.")
        return
    except Exception as e:
        print(f"Errore imprevisto durante il caricamento: {e}")
        input("Premi Invio per uscire.")
        return

    # --- 3. Controllo Migrazione ---
    suono_1 = impostazioni.get('suono_1')

    if not suono_1:
        print("ERRORE: Blocco 'suono_1' non trovato nel file.")
        input("Premi Invio per uscire.")
        return

    if 'pluck_hardness' in suono_1 or 'damping_factor' in suono_1:
        print("File già aggiornato al formato Karplus-Strong.")
        print("Nessuna modifica necessaria.")
        input("Premi Invio per uscire.")
        return

    if 'kind' not in suono_1 and 'adsr' not in suono_1:
        print("ATTENZIONE: 'suono_1' non contiene i vecchi parametri 'kind' o 'adsr',")
        print("ma non contiene nemmeno i nuovi. Aggiungo i nuovi parametri di default.")
        # La migrazione procede
        pass
    
    print("Vecchia struttura 'suono_1' rilevata. Avvio migrazione...")

    # --- 4. Backup ---
    try:
        with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
            json.dump(impostazioni, f, indent=4, ensure_ascii=False)
        print(f"Backup di sicurezza creato in '{BACKUP_FILE}'.")
    except IOError as e:
        print(f"ERRORE: Impossibile creare il file di backup: {e}")
        print("Migrazione annullata.")
        input("Premi Invio per uscire.")
        return

    # --- 5. Migrazione ---
    try:
        # Rimuovi i vecchi parametri (se esistono)
        if 'kind' in suono_1:
            vecchio_kind = suono_1.pop('kind')
            print(f" - Rimosso 'kind: {vecchio_kind}'")
            
        if 'adsr' in suono_1:
            vecchio_adsr = suono_1.pop('adsr')
            print(f" - Rimosso 'adsr: {vecchio_adsr}'")
            
        # Aggiungi i nuovi parametri
        suono_1['pluck_hardness'] = DEFAULT_HARDNESS
        suono_1['damping_factor'] = DEFAULT_DAMPING
        print(f" + Aggiunto 'pluck_hardness: {DEFAULT_HARDNESS}'")
        print(f" + Aggiunto 'damping_factor: {DEFAULT_DAMPING}'")
        
        # Aggiorna la descrizione
        suono_1['descrizione'] = "Suono per accordi (Karplus-Strong Pluck)"
        print(" * Aggiornata 'descrizione'")
        
    except Exception as e:
        print(f"ERRORE durante l'aggiornamento della struttura dati: {e}")
        input("Premi Invio per uscire.")
        return

    # --- 6. Salvataggio ---
    try:
        with open(FILE_IMPOSTAZIONI, 'w', encoding='utf-8') as f:
            json.dump(impostazioni, f, indent=4, ensure_ascii=False)
        print(f"\nMigrazione completata con successo!")
        print(f"File '{FILE_IMPOSTAZIONI}' aggiornato.")
    except IOError as e:
        print(f"ERRORE: Impossibile salvare il file aggiornato: {e}")
        print("Ripristina il file dal backup.")
    
    input("Premi Invio per chiudere.")

if __name__ == "__main__":
    migra_impostazioni()