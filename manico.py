# Chitabry, manico: dove stanno le note sulle corde, e le funzioni del menu che lo interrogano.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.

from GBUtils import dgt, key

import config
import suoni
from nomenclatura import get_nota, nome_utente_in_std, nomi_note_utente

# Le note bemolli e quelle scritte con il trattino di music21, riportate al
# diesis con cui config.CORDE nomina le posizioni del manico.
_BEMOLLI_IN_DIESIS = {
    'Db': 'C#', 'Eb': 'D#', 'Gb': 'F#', 'Ab': 'G#', 'Bb': 'A#',
    'C-': 'B', 'D-': 'C#', 'E-': 'D#', 'F-': 'E', 'G-': 'F#', 'A-': 'G#', 'B-': 'A#',
}


def Manlimiti(s):
    """Riceve una stringa N-N e restituisce i due limiti del manico come interi.
    Se il formato non e' valido usa tutto il manico e lo dice."""
    if "-" not in s or " " in s:
        print("Errore: formato non valido. Usare N-N (es. 0-4).")
        return 0, config.NUM_TASTI
    s2 = s.split("-")
    if len(s2) != 2 or not s2[0].isdigit() or not s2[1].isdigit():
        print("Errore: inserire solo valori numerici separati da un trattino.")
        return 0, config.NUM_TASTI
    maninf, mansup = int(s2[0]), int(s2[1])
    if maninf > mansup:
        print(f"Limiti invertiti. Uso {mansup}-{maninf}.")
        return mansup, maninf
    return maninf, mansup


def _posizioni_manico(corrisponde, maninf, mansup):
    """Dizionario corda -> tasti crescenti delle posizioni la cui nota, con
    ottava, soddisfa corrisponde, entro i limiti del manico."""
    trovate = {corda: [] for corda in range(config.NUM_CORDE, 0, -1)}
    for posizione, nota in config.CORDE.items():
        corda_str, tasto_str = posizione.split(".")
        tasto = int(tasto_str)
        if maninf <= tasto <= mansup and corrisponde(nota):
            trovate[int(corda_str)].append(tasto)
    return trovate


def _stampa_posizioni(trovate):
    """Una riga per corda, dalla piu' grave alla piu' acuta."""
    qualcosa = False
    for corda in range(config.NUM_CORDE, 0, -1):
        if trovate[corda]:
            qualcosa = True
            print(f"Corda {corda}, tasti: {' '.join(str(t) for t in trovate[corda])}")
    if not qualcosa:
        print("Nessuna nota trovata in quest'area del manico.")


def MostraCorde(nota_std, maninf=0, mansup=None):
    """Mostra tutte le posizioni della nota cercata sul manico.
    nota_std e' in formato standard, con l'ottava (C4) o senza (C): senza,
    si cercano tutte le ottave."""
    if mansup is None:
        mansup = config.NUM_TASTI
    con_ottava = nota_std[-1].isdigit()
    print(f"Nota {get_nota(nota_std)} trovata nelle seguenti posizioni (tasti {maninf}-{mansup}):")
    if con_ottava:
        trovate = _posizioni_manico(lambda nota: nota == nota_std, maninf, mansup)
    else:
        trovate = _posizioni_manico(lambda nota: nota[:-1] == nota_std, maninf, mansup)
    _stampa_posizioni(trovate)


def visualizza_note_su_manico(lista_note, maninf=0, mansup=None):
    """Mostra sul manico un elenco di note standard senza ottava, per esempio
    quelle di una scala o di un accordo, entro i limiti indicati."""
    if mansup is None:
        mansup = config.NUM_TASTI
    note_da_cercare = set()
    for n in lista_note:
        n_clean = n.replace('-', 'b')
        note_da_cercare.add(_BEMOLLI_IN_DIESIS.get(n_clean, n_clean))
    print(f"Posizioni sul manico (tasti {maninf}-{mansup}):")
    trovate = _posizioni_manico(lambda nota: nota[:-1] in note_da_cercare, maninf, mansup)
    _stampa_posizioni(trovate)


def TrovaNota():
    """Trova le posizioni di una nota, senza ottava, sul manico, chiedendo i limiti."""
    print(f"Trova nota sul manico. Nomenclatura attuale: {config.impostazioni['nomenclatura']}.")
    print(f"Note valide (senza ottava): {', '.join(nomi_note_utente())}")
    s_nota = dgt("Inserisci il nome della nota (Invio per annullare): ", smax=5).strip().upper()
    if s_nota == "":
        print("Operazione annullata.")
        key("Premi un tasto...")
        return
    nota_std = nome_utente_in_std(s_nota)
    if nota_std is None:
        print(f"'{s_nota}' non e' un nome di nota valido in questa nomenclatura.")
        key("Premi un tasto...")
        return
    print("Puoi indicare una porzione di manico per la ricerca (es. 0-4).")
    scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
    maninf, mansup = 0, config.NUM_TASTI
    if scelta_manico != "":
        maninf, mansup = Manlimiti(scelta_manico)
    MostraCorde(nota_std, maninf=maninf, mansup=mansup)
    key("Premi un tasto per tornare al menu...")


def TrovaPosizione():
    """Trova la nota data una posizione corda.tasto e la suona con il suono attivo."""
    print("Trova posizione (corda.tasto).")
    s = dgt("Inserisci Corda.Tasto (es. 6.3): ", smax=5).strip()
    if s == "":
        print("Operazione annullata.")
    elif s in config.CORDE:
        nota_std = config.CORDE[s]
        corda, tasto = s.split('.')
        print(f"Sulla corda {corda}, tasto {tasto}, si trova la nota: {get_nota(nota_std)}")
        # Le corde gravi a sinistra e le acute a destra, come sulla tastiera
        indice_corda = config.NUM_CORDE - int(corda)
        suoni.suona_una_nota(nota_std, pan=suoni.pan_per_voce(indice_corda, config.NUM_CORDE))
    else:
        print(f"Posizione '{s}' non valida. Formato richiesto: C.T (es. 6.3), tasti da 0 a {config.NUM_TASTI}.")
    key("Premi un tasto per tornare al menu...")


def VisualizzaManico():
    """Mostra lo schema del manico dello strumento attivo come griglia di
    caratteri con le colonne allineate, pensata per la barra braille."""
    strum_attivo = config.impostazioni.get("strumento_attivo", config.STRUMENTO_PREDEFINITO)
    num_tasti = config.NUM_TASTI
    num_corde = config.NUM_CORDE
    nome_basso = strum_attivo.lower()
    if nome_basso.startswith("chitarra"):
        articolo = "della"
    elif nome_basso.startswith("ukulele"):
        articolo = "dell'"
    elif nome_basso.startswith(("basso", "mandolino", "banjo", "guitalele")):
        articolo = "del"
    else:
        articolo = "dello strumento"
    if articolo.endswith("'"):
        print(f"Il manico {articolo}{nome_basso}.")
    else:
        print(f"Il manico {articolo} {nome_basso}.")
    col0_width = len(str(num_corde))
    # La larghezza delle colonne e' quella della cella piu' lunga
    max_len = len("[T0]")
    for tasto in range(1, num_tasti + 1):
        max_len = max(max_len, len(f" T{tasto}"))
    for corda in range(1, num_corde + 1):
        for tasto in range(num_tasti + 1):
            key_pos = f"{corda}.{tasto}"
            if key_pos in config.CORDE:
                nota_tradotta = get_nota(config.CORDE[key_pos])
                if tasto == 0:
                    max_len = max(max_len, len(f"[{nota_tradotta}]"))
                else:
                    max_len = max(max_len, len(f" {nota_tradotta}"))
    col_width = max_len
    col0_head = f"{'C':<{col0_width}}"
    cells_head = ["[T0]"] + [f" T{t}".ljust(col_width) for t in range(1, num_tasti + 1)]
    print(f"{col0_head}|" + "|".join(cells_head) + "|")
    for corda in range(1, num_corde + 1):
        row_cells = []
        for tasto in range(num_tasti + 1):
            key_pos = f"{corda}.{tasto}"
            nota_tradotta = get_nota(config.CORDE[key_pos]) if key_pos in config.CORDE else ""
            if tasto == 0:
                cell_val = f"[{nota_tradotta}]"
            else:
                cell_val = f" {nota_tradotta}"
            row_cells.append(cell_val.ljust(col_width))
        col0_row = f"{corda:<{col0_width}}"
        print(f"{col0_row}|" + "|".join(row_cells) + "|")
    key("Premi un tasto per tornare al menu...")
