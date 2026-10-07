# Chitabry, armonica a schermo: lo schema dei fori, dove si suona una nota, cosa suona un simbolo, gli accordi sui fori vicini.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la 9.0.0, issue 58: con un'armonica attiva, le voci del menu che
# per una chitarra interrogano il manico interrogano i fori.

import math

from GBUtils import dgt, key, menu

import clitronomo
import config
import GBAudio
import player
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
# Il tempo del metronomo quando non ha ancora un preset: quello con cui parte
TEMPO_DI_SERIE = 120


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
    key("\rPremi un tasto per tornare al menu...\r")
    print()


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
        key("\rPremi un tasto...\r")
        print()
        return
    ottava = None
    if testo[-1].isdigit():
        ottava = int(testo[-1])
        testo = testo[:-1]
    nota_std = nome_utente_in_std(testo)
    if nota_std is None:
        print(f"'{testo}' non e' un nome di nota valido in questa nomenclatura.")
        key("\rPremi un tasto...\r")
        print()
        return
    classe = config.NOTE_STD.index(nota_std)
    trovate = [m for m in sorted(modello.per_midi) if m % 12 == classe and (ottava is None or m // 12 - 1 == ottava)]
    if not trovate:
        grave, acuta = modello.estensione()
        cercata = get_nota(nota_std) + ("" if ottava is None else str(ottava))
        print(f"{cercata} non c'e' su questa armonica, che va da {nome_da_midi(grave)} a {nome_da_midi(acuta)}.")
    for midi in trovate:
        print(f"{nome_da_midi(midi)}: {modi_di_suonare(modello, midi)}.")
    key("\rPremi un tasto per tornare al menu...\r")
    print()


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
        suoni.suona_note([tecnica.midi])


def _nome_nell_accordo(nomi_classi, midi):
    """Una nota di un gruppo di fori, con la grafia dell'accordo se c'e'."""
    if midi % 12 in nomi_classi:
        return nome_con_grafia(nomi_classi[midi % 12], midi)
    return nome_da_midi(midi)


def tempo_del_metronomo():
    """I BPM del metronomo attivo, cioe' del suo ultimo preset, o il suo
    tempo di serie se non ne ha. Il metronomo conta i BPM in quarti,
    qualunque sia il tempo della battuta."""
    _, stato = clitronomo.PresetManager(silenzioso=True).get_last_used_preset()
    bpm = (stato or {}).get('bpm', TEMPO_DI_SERIE)
    try:
        bpm = float(bpm)
    except (TypeError, ValueError):
        return TEMPO_DI_SERIE
    if not math.isfinite(bpm) or not 5 <= bpm <= 1000:
        return TEMPO_DI_SERIE
    return bpm


def durata_due_quarti(bpm):
    """Due quarti a quel tempo, in secondi: quanto dura l'accordo che si
    sente da solo, scelto il gruppo di fori. Prima durava quanto il suono,
    fino a nove secondi (collaudo di Gabriele del 7 ottobre 2026)."""
    return 2 * 60.0 / bpm


def ascolta_gruppo(finestra, nomi_classi):
    """L'ascolto di un gruppo di fori, come quello degli accordi della
    chitarra: un tasto per nota, dal foro piu' basso, A o Q per l'accordo
    intero, Spazio per cambiare suono, Esc per uscire. Scelto il gruppo,
    l'accordo si sente da solo per due quarti al tempo del metronomo attivo;
    poi i tasti suonano finche' sono giu', come nella Tastiera (collaudo di
    Gabriele del 7 ottobre 2026). Si suona un fiato alla volta: un tasto
    nuovo chiude con la rampa quello che suonava. Dove la tastiera non sa
    dire quando un tasto si lascia, anche le note dei tasti durano due quarti."""
    note = list(finestra.note)
    tasti_note = min(len(note), 10)
    nomi = [_nome_nell_accordo(nomi_classi, n) for n in note]
    bpm = tempo_del_metronomo()
    durata = durata_due_quarti(bpm)
    ultimo = str(tasti_note) if tasti_note < 10 else "0"
    comandi = f"1-{ultimo}, A, Q, SPAZIO, ESC"
    tasti = player.apri_tastiera()
    poi = ("poi note e accordo suonano finche' tieni il tasto, con il banco fino a otto secondi." if tasti.tiene else
           "e durano due quarti anche note e accordo dei tasti.")
    print(f"Ascolto di {finestra.simboli}: l'accordo si sente per due quarti al tempo del metronomo, {bpm:g} BPM, {poi}")
    print(f"Tasti da 1 a {ultimo} per le note, A o Q per l'accordo, SPAZIO cambia suono, ESC esce.")
    stato = {'suono': suoni.suono_attivo()}
    stato['parametri'] = suoni.parametri_suono(stato['suono'])
    # Due voci per nota, cosi' il fiato nuovo non prende la voce di quello
    # che sta sfumando, e l'ultima per l'accordo a tempo. Con una voce sola
    # per nota, tieni sostituiva il suono che sfumava e la rampa spariva: il
    # passaggio fra accordo e nota faceva uno scatto.
    voci_fiato = 2 * len(note)
    mixer = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=voci_fiato + 1)
    # Il tasto che le ha accese -> le voci, per chiuderle quando risale
    accese = {}

    def zitto():
        """Un fiato alla volta: tutte le voci si chiudono con la rampa. Una
        nota sommata all'accordo, che arriva gia' al pieno, faceva saturare
        il mixer."""
        for voce in range(voci_fiato + 1):
            mixer.lascia(voce, suoni.secondi_di_rilascio(stato['parametri']))
        accese.clear()

    def a_tempo(indici):
        """Note o accordo per due quarti, sulla voce dell'accordo."""
        mono = suoni.mono_delle_note([note[i] for i in indici], stato['parametri'], dur=durata)
        if mono is not None:
            zitto()
            mixer.pluck(voci_fiato, mono)

    def tieni(indici, nome):
        if not tasti.tiene:
            a_tempo(indici)
            return
        zitto()
        # Le voci che tacciono prima, quelle che sfumano solo se mancano
        libere = [v for v in range(voci_fiato) if not mixer.sta_suonando(v)]
        libere += [v for v in range(voci_fiato) if v not in libere]
        coppie = [(libere[k], GBAudio.midi_to_freq(note[i])) for k, i in enumerate(indici)]
        voci = suoni.tieni_note_insieme(mixer, coppie, stato['parametri'])
        if voci:
            accese[nome] = voci

    def riga():
        print(f"\rNote: {' - '.join(nomi)} ({comandi}): \r", end="", flush=True)

    mixer.start()
    try:
        a_tempo(range(len(note)))
        riga()
        while True:
            for nome, azione in tasti.eventi(None):
                if azione == "su":
                    for voce in accese.pop(nome, ()):
                        suoni.lascia_nota(mixer, voce, stato['parametri'])
                    continue
                if nome in player.MODIFICATORI:
                    continue
                scelta = nome.lower()
                if scelta.isdigit():
                    numero = int(scelta) if scelta != '0' else 10
                    if 1 <= numero <= tasti_note:
                        tieni([numero - 1], nome)
                elif scelta in ('a', 'q'):
                    tieni(range(len(note)), nome)
                elif scelta == ' ':
                    zitto()
                    stato['suono'] = suoni.prossimo_suono(stato['suono'])
                    stato['parametri'] = suoni.parametri_suono(stato['suono'])
                    print(f"\nSuono: {suoni.descrizione_suono(stato['suono'])}")
                    riga()
                elif scelta == chr(27):
                    print()
                    return
                else:
                    print(f"\nComando non valido. Premi {comandi}.")
                    riga()
    finally:
        tasti.chiudi()
        mixer.stop()


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
        key("\rPremi un tasto per tornare al menu...\r")
        print()
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
        ascolta_gruppo(finestre[0], nomi_classi)
        return
    print("Scegli il numero del gruppo da ascoltare, Esc per uscire.")
    mostra = True
    while True:
        scelta = menu(d=voci, keyslist=True, show=mostra, ordered=False, ntf="Scelta non valida")
        mostra = False
        if scelta is None:
            break
        ascolta_gruppo(finestre[int(scelta) - 1], nomi_classi)
        print("Scegli un altro gruppo, ? per rileggerli, Esc per uscire.")
