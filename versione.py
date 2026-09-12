# Chitabry, versione: numero, data e autori stanno in un posto solo.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09: prima la versione e la data vivevano
# nella stessa stringa dentro Chitabry.py, e midistudy la importava da li'
# rieseguendo tutto il modulo principale.

VERSIONE = "8.0.1"
RELEASE_DATE = "2026-09-12"
APP_NAME = "Chitabry"
AUTORI = "Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode)"
API_RELEASE = "https://api.github.com/repos/GabrieleBattaglia/Chitabry/releases/latest"

_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
         "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def data_italiana(iso=RELEASE_DATE):
    """Da AAAA-MM-GG a giorno mese anno per esteso, come si dice a voce."""
    anno, mese, giorno = iso.split("-")
    return f"{int(giorno)} {_MESI[int(mese) - 1]} {anno}"
