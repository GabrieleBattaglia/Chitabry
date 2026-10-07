# Chitabry, armonica a schermo: lo schema dei fori, dove si suona una nota, cosa suona un simbolo, gli accordi sui fori vicini.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la 9.0.0, issue 58: con un'armonica attiva, le voci del menu che
# per una chitarra interrogano il manico interrogano i fori.

from GBUtils import dgt, key, menu

import config
import suoni
from nomenclatura import get_nota, nome_con_grafia, nome_da_midi, nome_utente_in_std, nomi_note_utente

# Le righe dello schema, nell'ordine in cui si leggono: prima le note
# naturali, poi i bending aspirati dei fori bassi, quelli soffiati dei fori
# alti, e gli overbend. Il bending soffiato di un tono e mezzo c'e' sul foro
# 10 della Harmonic Minor, dove le ance distano quattro semitoni. Sulla cromatica soffiato e aspirato, con e senza cursore.
RIGHE_DIATONICA = ("+", "-", "-/", "-//", "-///", "+/", "+//", "+///", "+*", "-*")
RIGHE_CROMATICA = ("+", "+<", "-", "-<")
LEGENDA = ("Una riga per tecnica: + soffiato, - aspirato, ogni barra un semitono di bending, "
           "l'asterisco l'overbend, il segno minore il cursore premuto.")


def nome_attivo():
    return config.impostazioni.get("strumento_attivo", "")


def descrivi(modello):
    """L'armonica a parole, con la tonalita' nella nomenclatura dell'utente."""
    return f"{modello.famiglia} in {get_nota(modello.tonalita)}, accordatura {modello.accordatura.nome}, {modello.fori} fori"


def frase(testo):
    """Un messaggio del modello, che comincia minuscolo, fatto frase."""
    testo = str(testo)
    return testo[:1].upper() + testo[1:] + ("" if testo.endswith(".") else ".")


def _sigla(tecnica):
    """Il simbolo senza il numero del foro: e' l'etichetta della riga."""
    return tecnica.verso + "/" * tecnica.bend + ("*" if tecnica.overbend else "") + ("<" if tecnica.cursore else "")


def righe_schema(modello):
    """Lo schema come elenco di righe di testo, colonne allineate: e' una
    griglia pensata per la barra braille, come quella del manico."""
    celle = {}
    for tecnica in modello.tecniche:
        celle.setdefault(_sigla(tecnica), {})[tecnica.foro] = nome_da_midi(tecnica.midi)
    if not modello.cromatica:
        ordine = RIGHE_DIATONICA
    elif modello.valvole:
        ordine = RIGHE_CROMATICA
    else:
        # Senza valvole sono due armoniche a un semitono: prima tutte le
        # righe a cursore aperto, poi le stesse con il cursore premuto
        ordine = RIGHE_DIATONICA + tuple(sigla + "<" for sigla in RIGHE_DIATONICA)
    sigle = [s for s in ordine if s in celle]
    larghezza_etichetta = max(len("Foro"), *(len(s) for s in sigle))
    larghezza = max(len(str(modello.fori)), *(len(n) for riga in celle.values() for n in riga.values()))
    fori = range(1, modello.fori + 1)
    righe = [f"{'Foro':<{larghezza_etichetta}}|" + "|".join(f"{foro:<{larghezza}}" for foro in fori) + "|"]
    for sigla in sigle:
        riga = celle[sigla]
        righe.append(f"{sigla:<{larghezza_etichetta}}|" + "|".join(f"{riga.get(foro, ''):<{larghezza}}" for foro in fori) + "|")
    return righe


def schema():
    """La voce Manico dello strumento, con un'armonica attiva."""
    modello = config.ARMONICA
    print(f"Lo schema dei fori di {nome_attivo()}, {descrivi(modello)}.")
    print(LEGENDA)
    for riga in righe_schema(modello):
        print(riga)
    grave, acuta = modello.estensione()
    print(f"Estensione da {nome_da_midi(grave)} a {nome_da_midi(acuta)}.")
    key("Premi un tasto per tornare al menu...")


def modi_di_suonare(modello, midi):
    """I modi di suonare una nota, ciascuno con il simbolo e la descrizione."""
    return ", ".join(f"{t.simbolo} ({t.descrizione().lower()})" for t in modello.tecniche_per_nota(midi))


def trova_nota():
    """La voce Nota sul manico, con un'armonica attiva: in quali fori, e con
    quale tecnica, si suona una nota, in tutte le ottave o in una sola."""
    modello = config.ARMONICA
    print(f"Dove si suona una nota su {nome_attivo()}, {descrivi(modello)}.")
    print(f"Note valide: {', '.join(nomi_note_utente())}. Con l'ottava, per esempio {get_nota('G')}4, si cerca solo quella.")
    testo = dgt("Inserisci il nome della nota (Invio per annullare): ", smax=6).strip().upper()
    if not testo:
        print("Operazione annullata.")
        key("Premi un tasto...")
        return
    ottava = None
    if testo[-1].isdigit():
        ottava = int(testo[-1])
        testo = testo[:-1]
    nota_std = nome_utente_in_std(testo)
    if nota_std is None:
        print(f"'{testo}' non e' un nome di nota valido in questa nomenclatura.")
        key("Premi un tasto...")
        return
    classe = config.NOTE_STD.index(nota_std)
    trovate = [m for m in sorted(modello.per_midi) if m % 12 == classe and (ottava is None or m // 12 - 1 == ottava)]
    if not trovate:
        grave, acuta = modello.estensione()
        cercata = get_nota(nota_std) + ("" if ottava is None else str(ottava))
        print(f"{cercata} non c'e' su questa armonica, che va da {nome_da_midi(grave)} a {nome_da_midi(acuta)}.")
    for midi in trovate:
        print(f"{nome_da_midi(midi)}: {modi_di_suonare(modello, midi)}.")
    key("Premi un tasto per tornare al menu...")


def trova_posizione():
    """La voce Trova Posizione, con un'armonica attiva: dal simbolo di un
    foro alla nota che suona, che si sente subito. Si continua finche' non
    si preme Invio a vuoto, per provare un simbolo dopo l'altro."""
    modello = config.ARMONICA
    print(f"Trova la nota di un foro su {nome_attivo()}, {descrivi(modello)}.")
    print("Scrivi + per soffiato o - per aspirato, il numero del foro, poi una barra per ogni semitono di bending, "
          "l'asterisco per l'overbend o il segno minore per il cursore. Per esempio -3// o +4*.")
    while True:
        testo = dgt("Simbolo (Invio per tornare al menu): ", smax=8).strip()
        if not testo:
            return
        try:
            tecnica = modello.da_simbolo(testo)
        except ValueError as e:
            print(frase(e))
            continue
        print(f"{tecnica.simbolo}, {tecnica.descrizione().lower()}: suona {nome_da_midi(tecnica.midi)}.")
        altri = [t.simbolo for t in modello.tecniche_per_nota(tecnica.midi) if t != tecnica]
        if altri:
            print(f"La stessa nota anche con {', '.join(altri)}.")
        suoni.suona_note([tecnica.midi], armonica=True)


def _nome_nell_accordo(nomi_classi, midi):
    """Una nota di un gruppo di fori, con la grafia dell'accordo se c'e'."""
    if midi % 12 in nomi_classi:
        return nome_con_grafia(nomi_classi[midi % 12], midi)
    return nome_da_midi(midi)


def accordi(classi, nomi_classi, nome_accordo):
    """Il Costruttore Accordi con un'armonica attiva: i gruppi di fori vicini,
    nello stesso verso, che suonano l'accordo, da ascoltare uno per uno.
    nomi_classi da' per ogni classe di altezza il nome di music21 con la
    grafia dell'accordo, come B- per il SIb: le note dei gruppi e quelle che
    mancano si scrivono cosi', e un SIb resta SIb e non diventa LA#."""
    modello = config.ARMONICA
    finestre = modello.accordi(classi)
    if not finestre:
        print(f"Su {nome_attivo()} non ci sono fori vicini, nello stesso verso, che suonino almeno due note di {nome_accordo} senza note estranee.")
        key("Premi un tasto per tornare al menu...")
        return
    if finestre[0].completo and len(finestre) == 1:
        print(f"{nome_accordo} su {nome_attivo()}: un gruppo di fori vicini, nello stesso verso, lo suona per intero.")
    elif finestre[0].completo:
        print(f"{nome_accordo} su {nome_attivo()}: {len(finestre)} gruppi di fori vicini, nello stesso verso, lo suonano per intero.")
    else:
        print(f"Nessun gruppo di fori vicini suona {nome_accordo} per intero: questi sono i gruppi, senza note estranee, che ne suonano di piu'.")
    voci = {}
    for numero, finestra in enumerate(finestre, start=1):
        testo = f"{finestra.simboli}: {' '.join(_nome_nell_accordo(nomi_classi, n) for n in finestra.note)}"
        if finestra.mancanti:
            testo += f", manca {', '.join(get_nota(nomi_classi[c].replace('-', 'b')) if c in nomi_classi else '?' for c in sorted(finestra.mancanti))}"
        voci[str(numero)] = testo
    if len(finestre) == 1:
        # Con una voce sola menu la restituisce subito senza leggere un tasto:
        # dentro il ciclo l'accordo ripartiva all'infinito
        print(f"{voci['1']}.")
        print(f"Ascolto di {finestre[0].simboli}.")
        suoni.suona_note(finestre[0].note, armonica=True)
        key("Premi un tasto per tornare al menu...")
        return
    print("Scegli il numero del gruppo da ascoltare, Esc per uscire.")
    mostra = True
    while True:
        scelta = menu(d=voci, keyslist=True, show=mostra, ordered=False, ntf="Scelta non valida")
        mostra = False
        if scelta is None:
            break
        finestra = finestre[int(scelta) - 1]
        print(f"Ascolto di {finestra.simboli}.")
        suoni.suona_note(finestra.note, armonica=True)
