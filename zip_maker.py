# Chitabry, utilita': prepara l'archivio per la distribuzione.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5, modalita' auto).
# 04/09/2026: primo chiamante, il mestiere sta in crea_archivio_release di GBUtils V103.

"""Comprime la cartella prodotta da PyInstaller in un solo archivio.

Tutto il mestiere sta in GBUtils, cosi' la regola sulle esclusioni e' una
sola per tutti i progetti. Qui restano soltanto i nomi di Chitabry.

Prima non c'era nessuno script e l'archivio si preparava a mano: gli
strumenti di compressione di Windows aggiungono una cartella di livello
superiore, che perform_update non sa attraversare.

Oltre alle cartelle dei dati dell'utente, che la funzione salta da se',
si lasciano fuori le impostazioni, la loro copia di sicurezza, i preset
del metronomo e la cartella midi, dove MidiStudy scrive le anteprime e
le esportazioni: nascono tutti provando l'eseguibile prima di comprimere.
"""

import sys

from GBUtils import crea_archivio_release

FUORI = [
    "midi/",
    "chitabry-settings.json",
    "chitabry-settings.json.backup",
    "clitronomo_presets.json",
]


def main():
    try:
        crea_archivio_release("Chitabry", escludi=FUORI)
    except (FileNotFoundError, OSError) as e:
        print(f"Archivio non creato: {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
