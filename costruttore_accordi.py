# Chitabry, costruttore accordi: dalle note di un accordo alle diteggiature sullo strumento attivo.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.

from GBUtils import dgt, key, menu
from music21 import harmony
from music21.exceptions21 import Music21Exception

import config
import scale_catalog
from generatore_accordi import AccordoSolver
from nomenclatura import get_nota, mappa_toniche
from player import Suona
from ricerca import fuzzy_search_and_select
from strumento import InstrumentModel

# Quando la sigla breve non basta a music21, si riprova con il nome esteso
_RIPIEGHI = {"": " major", "m": " minor", "dim": " diminished", "aug": " augmented"}


def _scegli_accordo():
    """Chiede tonica e tipo. Restituisce la coppia (tonica standard, sigla) o None se annullato."""
    toniche = mappa_toniche()
    scelta = menu(d=toniche, keyslist=True, show=True, pager=12, ntf="Nota non valida", p="Scegli la TONICA: ")
    if scelta is None:
        print("Costruzione annullata.")
        return None
    tonica_std = toniche[scelta]
    sigla = menu(d=scale_catalog.USER_CHORD_DICT, keyslist=True, show=False, pager=15, ntf="Tipo non valido",
                 p=f"Filtra TIPO accordo per {get_nota(tonica_std)} (o '...'): ")
    if sigla is None:
        print("Costruzione annullata.")
        return None
    if sigla == "...":
        sigla = fuzzy_search_and_select(scale_catalog.USER_CHORD_DICT,
                                        f"Cerca TIPO accordo per {get_nota(tonica_std)} (testo parziale): ",
                                        "tipo di accordo")
        if sigla is None:
            print("Ricerca annullata.")
            return None
    return tonica_std, sigla


def _costruisci_accordo(tonica_std, sigla):
    """L'accordo di music21 per la figura tonica piu' sigla.
    Solleva ValueError se music21 non la interpreta."""
    figura = tonica_std + sigla
    accordo = harmony.ChordSymbol(figura)
    if not accordo.pitches and sigla in _RIPIEGHI:
        accordo = harmony.ChordSymbol(tonica_std + _RIPIEGHI[sigla])
    if not accordo.pitches:
        raise ValueError(f"music21 non e' riuscito a interpretare la figura '{figura}'")
    return accordo


def _strumento_attivo():
    """Il modello dello strumento attivo per il motore CSP, o None se i dati mancano."""
    strum_attivo = config.impostazioni.get("strumento_attivo", config.STRUMENTO_PREDEFINITO)
    dati_strum = config.impostazioni.get("strumenti", {}).get(strum_attivo, {})
    accordatura = dati_strum.get("accordatura", [])
    if not accordatura:
        print(f"Errore: accordatura dello strumento {strum_attivo} mancante.")
        return None
    return InstrumentModel(accordatura, int(dati_strum.get("tasti", config.TASTI_PREDEFINITI)))


def _diteggiature(model, solver, sols):
    """Prepara le voci di menu e i dettagli delle dieci migliori soluzioni.
    Restituisce la coppia (voci, mappa chiave -> (tablatura acuta-grave, dettagli))."""
    scored_sols = sorted(((solver.score_solution(s), s) for s in sols), key=lambda x: x[0], reverse=True)
    voci = {}
    soluzioni = {}
    for i, (score, s) in enumerate(scored_sols[:10]):
        tab = [s[f"C{j}"] for j in range(model.num_corde)]
        tab_str = ["X" if t == -1 else str(t) for t in tab]
        meta = solver.analizza_difficolta_e_diteggiatura(s, score)
        # Per la chordpedia e per Suona: dalla corda acuta alla grave
        tab_menu_list = ["x" if tab[j] == -1 else str(tab[j]) for j in range(model.num_corde - 1, -1, -1)]
        dettagli = f"Tablatura (dalla corda piu' grave): {' '.join(tab_str)}\n"
        dettagli += f"Difficolta' generale: {meta['difficolta_score_perc']}%. Estensione: {meta['difficolta_stretch_perc']}% ({meta['stretch_tasti']} tasti).\n"
        if meta['diteggiatura']:
            dettagli += "Impostazione mano:\n" + "\n".join(f"  {d}" for d in meta['diteggiatura'])
        else:
            dettagli += "Nessun dito usato (tutte a vuoto o mute)."
        chiave = str(i)
        voci[chiave] = f"{'-'.join(tab_menu_list)} | Diff: {meta['difficolta_score_perc']}% | Stretch: {meta['difficolta_stretch_perc']}%"
        soluzioni[chiave] = (tab_menu_list, dettagli)
    return voci, soluzioni


def CostruttoreAccordi():
    """Costruisce un accordo con harmony.ChordSymbol di music21, ne mostra le
    note e calcola le migliori diteggiature con il motore CSP."""
    print("Costruttore di accordi teorico.")
    print("Scopri quali note compongono qualsiasi accordo.")
    scelta = _scegli_accordo()
    if scelta is None:
        return
    tonica_std, sigla = scelta
    try:
        accordo = _costruisci_accordo(tonica_std, sigla)
    except (Music21Exception, ValueError) as e:
        print(f"Errore durante la creazione dell'accordo: {e}")
        print("Verifica la correttezza della fondamentale e del tipo.")
        key("Premi un tasto...")
        return
    note_formattate = []
    for p_note in accordo.pitches:
        nome = get_nota(p_note.nameWithOctave.replace('-', 'b'))
        if nome not in note_formattate:
            note_formattate.append(nome)
    nome_accordo = f"{get_nota(tonica_std)} {scale_catalog.USER_CHORD_DICT.get(sigla, sigla)}"
    print("Risultato dell'analisi.")
    print(f"Accordo: {nome_accordo}")
    print(f"Note componenti: {' - '.join(note_formattate)}")
    print("Calcolo delle migliori diteggiature in corso...")
    model = _strumento_attivo()
    if model is None:
        key("Premi un tasto...")
        return
    target_pc = {p.pitchClass for p in accordo.pitches}
    solver = AccordoSolver(model, target_pc, accordo.root().pitchClass)
    sols = solver.solve(max_stretch=4)
    if not sols:
        print("Nessuna diteggiatura fisicamente possibile trovata per questo accordo.")
        key("Premi un tasto per tornare al menu...")
        return
    voci, soluzioni = _diteggiature(model, solver, sols)
    if len(voci) == 1:
        tab_selezionata, dettagli = next(iter(soluzioni.values()))
        print("Dettagli dell'unica forma trovata:")
        print(dettagli)
        print("Ascolto dell'accordo (Player Corde)...")
        Suona(list(reversed(tab_selezionata)))
    else:
        while True:
            print(f"Le {len(voci)} migliori diteggiature per {nome_accordo}:")
            scelta_tab = menu(d=voci, keyslist=True, show=True, numbered=False, ntf="Scelta non valida", p="Scegli il numero (es. 0) per ascoltare: ")
            if scelta_tab is None:
                break
            tab_selezionata, dettagli = soluzioni[scelta_tab]
            print(f"Dettagli della forma {scelta_tab}:")
            print(dettagli)
            print("Ascolto dell'accordo (Player Corde)...")
            # tab_selezionata va dalla corda acuta alla grave, Suona vuole il contrario
            Suona(list(reversed(tab_selezionata)))
            azione = dgt("Scegli: [R]iascolta, oppure Invio per tornare alle opzioni: ").strip().lower()
            if azione == 'r':
                Suona(list(reversed(tab_selezionata)))
    print("Uscita dal Costruttore Accordi.")
