# Chitabry, player: l'ascolto di una diteggiatura corda per corda e la tastiera del PC.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.
# Le corde si contano con NUM_CORDE: fino alla 7.8.3 il numero sei era
# scritto nel codice, e su un ukulele nessuna corda suonava.
# Dalla 10.0.0 la tastiera a eventi sta anche nell'ascolto delle corde, dove
# la corda suona finche' il tasto e' giu', e ignora le ripetizioni che
# arrivano come rilascio e pressione; il MIDI di Windows non c'e' piu'.

import ctypes
import os
import time
from time import sleep as aspetta

from GBUtils import Tastiera, key
from music21 import pitch

import config
import GBAudio
import suoni
from nomenclatura import get_nota

# Tastiera italiana: per ogni tasto i semitoni da Do e lo scostamento di ottava.
KB_MAP = {
    # Ottava base (scostamento 0)
    'z': (0, 0), 'x': (2, 0), 'c': (4, 0), 'v': (5, 0), 'b': (7, 0), 'n': (9, 0), 'm': (11, 0),
    ',': (12, 0), '.': (14, 0), '-': (16, 0),
    's': (1, 0), 'd': (3, 0), 'g': (6, 0), 'h': (8, 0), 'j': (10, 0), 'l': (13, 0), 'ò': (15, 0),
    # Ottava base meno uno (Shift)
    'Z': (0, -1), 'X': (2, -1), 'C': (4, -1), 'V': (5, -1), 'B': (7, -1), 'N': (9, -1), 'M': (11, -1),
    ';': (12, -1), ':': (14, -1), '_': (16, -1),
    'S': (1, -1), 'D': (3, -1), 'G': (6, -1), 'H': (8, -1), 'J': (10, -1), 'L': (13, -1), 'ç': (15, -1),
    # Ottava base piu' uno (riga superiore)
    'q': (0, 1), 'w': (2, 1), 'e': (4, 1), 'r': (5, 1), 't': (7, 1), 'y': (9, 1), 'u': (11, 1),
    'i': (12, 1), 'o': (14, 1), 'p': (16, 1), 'è': (17, 1), '+': (19, 1),
    '2': (1, 1), '3': (3, 1), '5': (6, 1), '6': (8, 1), '7': (10, 1), '9': (13, 1), '0': (15, 1), 'ì': (18, 1),
    # Ottava base piu' due (Shift sulla riga superiore)
    'Q': (0, 2), 'W': (2, 2), 'E': (4, 2), 'R': (5, 2), 'T': (7, 2), 'Y': (9, 2), 'U': (11, 2),
    'I': (12, 2), 'O': (14, 2), 'P': (16, 2), 'é': (17, 2), '*': (19, 2),
    '"': (1, 2), '£': (3, 2), '%': (6, 2), '&': (8, 2), '/': (10, 2), ')': (13, 2), '=': (15, 2), '^': (18, 2),
}
# I tasti funzione impostano l'ottava base
OTTAVE_FUNZIONE = {'f1': 2, 'f2': 3, 'f3': 4, 'f4': 5, 'f5': 6, 'f6': 7, 'f7': 8, 'f8': 9}
NUM_VOCI = 16
# Quanto si aspetta, dopo un rilascio, prima di riferirlo: se nel frattempo
# lo stesso tasto torna giu', era una ripetizione e la nota continua. Con lo
# Shift tenuto le ripetizioni di Windows arrivavano a Chitabry come coppie di
# rilascio e pressione, non da GBUtils, che con le ripetizioni vere tiene la
# nota, ma da chi sta fra la tastiera e la console, e ogni coppia faceva
# ripartire la nota (collaudo di Gabriele del 7 ottobre 2026). Il minimo,
# sessanta millesimi, copre la ripetizione piu' veloce di Windows, una ogni
# trentatre; con una ripetizione piu' lenta si aspetta un po' di piu'.
# I modificatori premuti da soli, che la tastiera a eventi riferisce e key
# no: negli ascolti si ignorano, invece di dire Comando non valido ogni volta
# che con il Ctrl si zittisce NVDA o con lo Shift si fa una maiuscola.
MODIFICATORI = frozenset({'shift', 'ctrl', 'alt', 'win', 'menu', 'capslock', 'numlock', 'scrolllock'})
GRAZIA_MINIMA = 0.06
_SPI_GETKEYBOARDSPEED = 0x000A
_TOLLERANZA = 1e-6


def grazia_del_rilascio():
    """L'attesa prima di riferire un rilascio, in secondi: una volta e mezza
    l'intervallo di ripetizione della tastiera scelto in Windows, almeno
    GRAZIA_MINIMA."""
    if os.name != 'nt':
        return GRAZIA_MINIMA
    velocita = ctypes.c_uint(31)
    try:
        ctypes.windll.user32.SystemParametersInfoW(_SPI_GETKEYBOARDSPEED, 0, ctypes.byref(velocita), 0)
    except (AttributeError, OSError):
        return GRAZIA_MINIMA
    # Da 0, circa 2,5 ripetizioni al secondo, a 31, circa 30
    ripetizioni = 2.5 + min(31, velocita.value) * 27.5 / 31
    return max(GRAZIA_MINIMA, 1.5 / ripetizioni)


class TastieraTenuta:
    """La tastiera a eventi di GBUtils, con il rilascio riferito solo se lo
    stesso tasto non torna giu' entro la grazia: un tasto tenuto resta tenuto
    anche se le sue ripetizioni arrivano come rilascio e pressione. Il prezzo
    e' che una nota lasciata si chiude qualche centesimo di secondo dopo."""

    tiene = True

    def __init__(self, tastiera, grazia=None):
        self._tastiera = tastiera
        self._grazia = grazia_del_rilascio() if grazia is None else grazia
        self._sospesi = {}   # nome del tasto -> quando riferirne il rilascio

    @property
    def premuti(self):
        return self._tastiera.premuti

    def chiudi(self):
        self._sospesi.clear()
        self._tastiera.chiudi()

    def eventi(self, attesa=None):
        """Come eventi di Tastiera: le coppie (nome, 'giu') e (nome, 'su'),
        con attesa None che aspetta senza limite, e i rilasci in ritardo."""
        limite = None if attesa is None else time.monotonic() + attesa
        while True:
            ora = time.monotonic()
            # Un microsecondo di tolleranza: il tempo che resta, sommato a
            # quello passato, puo' fermarsi un soffio sotto la scadenza
            scaduti = [nome for nome, quando in self._sospesi.items() if quando <= ora + _TOLLERANZA]
            for nome in scaduti:
                del self._sospesi[nome]
            if scaduti:
                return [(nome, "su") for nome in scaduti]
            scadenze = list(self._sospesi.values()) + ([] if limite is None else [limite])
            resta = max(0.0, min(scadenze) - ora) if scadenze else None
            raccolti = []
            for nome, azione in self._tastiera.eventi(resta):
                if azione == "su":
                    self._sospesi[nome] = time.monotonic() + self._grazia
                elif nome in self._sospesi:
                    # Torna giu' dentro la grazia: era una ripetizione
                    del self._sospesi[nome]
                else:
                    raccolti.append((nome, azione))
            if raccolti:
                return raccolti
            ora = time.monotonic()
            if limite is not None and ora >= limite - _TOLLERANZA and all(
                    quando > ora + _TOLLERANZA for quando in self._sospesi.values()):
                return []


class _TastiSenzaRilascio:
    """Il ripiego per dove la tastiera a eventi non c'e', cioe' fuori da
    Windows e in un processo senza console.
    Un terminale consegna caratteri e non sa dire quando un tasto viene
    lasciato, quindi qui ogni tasto e' solo una pressione e le note restano
    quelle che decadono da sole, come prima della issue 55. Il ciclo che le
    suona e' lo stesso: cambia soltanto chi gli passa gli eventi, e tiene dice
    a chi suona se le note si possano tenere o no."""

    tiene = False
    premuti = frozenset()

    def eventi(self, attesa=None):
        nome = key(attesa=attesa)
        return [(nome, "giu")] if nome else []

    def chiudi(self):
        pass


def apri_tastiera():
    """La tastiera a eventi, o il ripiego dove non si puo' avere.
    Non e' un guasto da riferire: e' una differenza di sistema, e chi suona se
    ne accorge perche' le note non si tengono."""
    try:
        tastiera = Tastiera()
    except (NotImplementedError, EOFError, RuntimeError):
        return _TastiSenzaRilascio()
    return TastieraTenuta(tastiera)


def Suona(tablatura):
    """Ascolto interattivo di una tablatura, un tasto per corda e le pennate.
    tablatura e' l'elenco dei tasti dalla corda piu' grave alla piu' acuta,
    con x per la corda muta. Usa il mixer polifonico, una voce per corda.
    Dalla 10.0.0 corde e pennate suonano finche' il tasto e' giu', come
    nella Tastiera (collaudo di Gabriele del 7 ottobre 2026): una corda
    pizzicata decade comunque, ma lasciare il tasto la smorza, e con un banco
    d'organo o d'archi la nota resta."""
    num_corde = config.NUM_CORDE
    max_keys = min(num_corde, 10)
    keys_str = "1 a " + (str(max_keys) if max_keys < 10 else "0")
    print("Ascolta le corde.")
    print(f"Tasti da {keys_str}, A pennata in levare, Q pennata in battere, SPAZIO cambia suono, ESC esce.")
    stato = {'suono': suoni.suono_attivo()}
    stato['parametri'] = suoni.parametri_suono(stato['suono'])
    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=num_corde)
    note_freq, nomi = [], []
    for i in range(num_corde):
        corda = num_corde - i
        tasto = tablatura[i]
        poly_player.set_pan(i, suoni.pan_per_voce(i, num_corde))
        posizione = f"{corda}.{tasto}"
        if tasto.isdigit() and posizione in config.CORDE:
            nota_std = config.CORDE[posizione]
            note_freq.append(GBAudio.note_to_freq(nota_std))
            nomi.append(get_nota(nota_std))
        else:
            note_freq.append(0.0)
            nomi.append("X")
    tasti = apri_tastiera()
    if tasti.tiene:
        print("Le corde suonano finche' tieni il tasto.")
    # Il tasto che le ha accese -> le voci, per spegnerle quando risale
    accese = {}

    def suona_corda(i):
        if note_freq[i] <= 0:
            return False
        return suoni.tieni_nota(poly_player, i, note_freq[i], stato['parametri'], tiene=tasti.tiene)

    def lascia(nome):
        for voce in accese.pop(nome, ()):
            if tasti.tiene:
                suoni.lascia_nota(poly_player, voce, stato['parametri'])

    def riga():
        print(f"\rNote: {' - '.join(nomi)} (1-{max_keys}, A, Q, SPAZIO, ESC): {' ' * 10}\r", end="", flush=True)

    poly_player.start()
    riga()
    try:
        while True:
            for nome, azione in tasti.eventi(None):
                if azione == "su":
                    lascia(nome)
                    continue
                if nome in MODIFICATORI:
                    continue
                scelta = nome.lower()
                if scelta.isdigit():
                    key_int = int(scelta) if scelta != '0' else 10
                    if 1 <= key_int <= max_keys and suona_corda(key_int - 1):
                        accese[nome] = [key_int - 1]
                elif scelta == ' ':
                    for gia in list(accese):
                        lascia(gia)
                    stato['suono'] = suoni.prossimo_suono(stato['suono'])
                    stato['parametri'] = suoni.parametri_suono(stato['suono'])
                    print(f"\nSuono: {suoni.descrizione_suono(stato['suono'])}")
                    riga()
                elif scelta == chr(27):
                    print("\nUscita dal menu ascolto.")
                    return
                elif scelta in ('a', 'q'):
                    # In battere dalla corda grave, in levare dalla acuta
                    ordine = range(num_corde) if scelta == 'q' else range(num_corde - 1, -1, -1)
                    voci = []
                    for i in ordine:
                        if suona_corda(i):
                            voci.append(i)
                            aspetta(0.07)
                    accese[nome] = voci
                else:
                    print(f"\nComando non valido. Premi 1-{max_keys}, A, Q, SPAZIO o ESC.")
                    riga()
    finally:
        tasti.chiudi()
        poly_player.stop()


def PlayerGenerico():
    """La tastiera del PC come strumento, con la tastiera MIDI se collegata.

    Dalla issue 55 la nota e' legata alla coppia pressione e rilascio invece
    che alla sola pressione: dura finche' il dito resta sul tasto, e lasciarlo
    la chiude con una rampa. Ne viene anche che l'auto-ripetizione di Windows
    non si sente piu': un tasto gia' giu' non riaccende niente, dove prima
    ripizzicava la nota trentadue volte al secondo dopo mezzo secondo di
    tenuta. Quanto la nota tenuta duri davvero dipende dal suono scelto: un
    inviluppo con il mantenimento a zero, come una corda pizzicata, decade
    comunque, e tenere il tasto non lo allunga.
    """
    print("Tastiera virtuale (Player Generico).")
    print("Suona usando la tastiera del tuo PC (layout italiano).")
    print("  Ottava base (Z, X, C e seguenti): Z=Do, S=Do#, X=Re, D=Re# e cosi' via.")
    print("  Ottava superiore (Q, W, E e seguenti): Q=Do, 2=Do#, W=Re e cosi' via.")
    print("  Maiuscole (Shift): suonano un'ottava sotto o sopra rispetto alle minuscole.")
    print("  Da F1 a F8: impostano l'ottava base, da 2 a 9.")
    print("  SPAZIO: cambia suono.")
    print("  ESC: esci.")
    stato = {'suono': suoni.suono_attivo(), 'ottava': 3, 'voce': 0}
    stato['parametri'] = suoni.parametri_suono(stato['suono'])
    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=NUM_VOCI)
    tastiera = apri_tastiera()
    if tastiera.tiene:
        print("  Le note si spengono quando lasci il tasto.")
    # Che cosa sta suonando: dal tasto della tastiera del PC e dalla tastiera
    # MIDI, tenuti separati perche' lo stesso Do puo' arrivare da tutte e due.
    da_tasto = {}
    da_midi = {}

    def voce_libera():
        """Una voce che non stia suonando e non sia di un tasto ancora giu',
        o la piu' vecchia se sono tutte impegnate: con sedici voci e dieci
        dita capita solo tenendo il pedale di un accordo mentre se ne suona
        un altro. Una nota tenuta oltre la sua durata ha finito il buffer ma
        la voce e' ancora sua: data a un'altra nota, il rilascio della prima
        avrebbe chiuso la seconda."""
        occupate = {voce for _midi, voce in da_tasto.values()} | set(da_midi.values())
        for _giro in range(NUM_VOCI):
            v = stato['voce'] % NUM_VOCI
            stato['voce'] += 1
            if v not in occupate and not poly_player.sta_suonando(v):
                return v
        v = stato['voce'] % NUM_VOCI
        stato['voce'] += 1
        return v

    def accendi(midi_num, velocity=127):
        """Fa partire una nota e dice su quale voce, per poterla poi spegnere.
        La velocita' della tastiera MIDI esterna ne fa il volume."""
        v = voce_libera()
        if suoni.tieni_nota(poly_player, v, GBAudio.midi_to_freq(midi_num), stato['parametri'], tiene=tastiera.tiene,
                            guadagno=max(0.1, velocity / 127)):
            return v
        return None

    def spegni(_midi_num, voce):
        if voce is not None and tastiera.tiene:
            suoni.lascia_nota(poly_player, voce, stato['parametri'])

    def spegni_tutto():
        """Chiude quello che sta suonando: serve al cambio di suono, dove le
        note vecchie non avrebbero piu' chi le spenga, e all'uscita."""
        for _nome, (midi_num, voce) in list(da_tasto.items()):
            spegni(midi_num, voce)
        da_tasto.clear()
        for nota, voce in list(da_midi.items()):
            spegni(nota, voce)
        da_midi.clear()

    def nome_nota(midi_num):
        return get_nota(pitch.Pitch(midi=midi_num).nameWithOctave.replace('-', 'b'))

    def scrivi_riga(testo):
        """La riga che si riscrive fra due ritorni carrello, allungata quanto
        serve a coprire la precedente: le descrizioni del banco sono lunghe,
        e la riga piu' corta dopo ne lasciava i pezzi sulla barra braille."""
        print(f"\r{testo}{' ' * max(0, stato.get('lunghezza', 0) - len(testo))}\r", end="", flush=True)
        stato['lunghezza'] = len(testo)

    def riga_stato():
        scrivi_riga(f"[Suono: {suoni.descrizione_suono(stato['suono'])}] Ottava base: {stato['ottava']}")

    midi_in = GBAudio.get_midi_in()
    old_on_note_on = old_on_note_off = None
    if midi_in is not None:
        # I rilasci da qui in poi vengono al player: le note esterne accese
        # dal menu si chiudono adesso, o resterebbero accese per sempre
        suoni.chiudi_note_esterne()
        old_on_note_on = midi_in.on_note_on
        old_on_note_off = midi_in.on_note_off

        def player_note_on(note_num, velocity):
            da_midi[note_num] = accendi(note_num, velocity)
            scrivi_riga(f"[Tastiera MIDI] Nota: {nome_nota(note_num)} ({GBAudio.midi_to_freq(note_num):.1f} Hz)")

        def player_note_off(note_num):
            spegni(note_num, da_midi.pop(note_num, None))

        midi_in.on_note_on = player_note_on
        midi_in.on_note_off = player_note_off
    poly_player.start()
    riga_stato()
    finito = False
    try:
        while not finito:
            for nome, azione in tastiera.eventi(None):
                if azione == "su":
                    acceso = da_tasto.pop(nome, None)
                    if acceso is not None:
                        spegni(*acceso)
                    continue
                if nome == chr(27):
                    finito = True
                    break
                if nome == ' ':
                    spegni_tutto()
                    stato['suono'] = suoni.prossimo_suono(stato['suono'])
                    stato['parametri'] = suoni.parametri_suono(stato['suono'])
                    riga_stato()
                elif nome in OTTAVE_FUNZIONE:
                    stato['ottava'] = OTTAVE_FUNZIONE[nome]
                    riga_stato()
                elif nome in KB_MAP and nome not in da_tasto:
                    semitones, oct_offset = KB_MAP[nome]
                    # Tiene le frequenze dentro l'udibile
                    actual_octave = min(9, max(1, stato['ottava'] + oct_offset))
                    midi_num = 12 + semitones + 12 * actual_octave
                    da_tasto[nome] = (midi_num, accendi(midi_num))
                    scrivi_riga(f"Ultima nota: {nome_nota(midi_num)} ({GBAudio.midi_to_freq(midi_num):.1f} Hz) [Ottava base: {stato['ottava']}]")
    finally:
        if midi_in is not None:
            midi_in.on_note_on = old_on_note_on
            midi_in.on_note_off = old_on_note_off
        spegni_tutto()
        tastiera.chiudi()
        poly_player.stop()
        print("\nUscita dal Player Generico.")
