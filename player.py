# Chitabry, player: l'ascolto di una diteggiatura corda per corda e la tastiera del PC.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.
# Le corde si contano con NUM_CORDE: fino alla 7.8.3 il numero sei era
# scritto nel codice, e su un ukulele nessuna corda suonava.

from time import sleep as aspetta

from GBUtils import key
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


def Suona(tablatura):
    """Ascolto interattivo di una tablatura, un tasto per corda e le pennate.
    tablatura e' l'elenco dei tasti dalla corda piu' grave alla piu' acuta,
    con x per la corda muta. Usa il mixer polifonico, una voce per corda."""
    num_corde = config.NUM_CORDE
    max_keys = min(num_corde, 10)
    keys_str = "1 a " + (str(max_keys) if max_keys < 10 else "0")
    print("Ascolta le corde.")
    print(f"Tasti da {keys_str}, A pennata in levare, Q pennata in battere, SPAZIO cambia suono, ESC esce.")
    stato = {'suono': suoni.suono_attivo()}
    stato['parametri'] = suoni.parametri_suono(stato['suono'])
    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=num_corde)
    renderers = [GBAudio.NoteRenderer(fs=GBAudio.FS) for _ in range(num_corde)]
    note_freq, midi_nums, nomi = [], [], []
    for i in range(num_corde):
        corda = num_corde - i
        tasto = tablatura[i]
        poly_player.set_pan(i, suoni.pan_per_voce(i, num_corde))
        posizione = f"{corda}.{tasto}"
        if tasto.isdigit() and posizione in config.CORDE:
            nota_std = config.CORDE[posizione]
            note_freq.append(GBAudio.note_to_freq(nota_std))
            midi_nums.append(GBAudio.note_to_midi(nota_std))
            nomi.append(get_nota(nota_std))
        else:
            note_freq.append(0.0)
            midi_nums.append(None)
            nomi.append("X")

    def configura_tutti():
        for i in range(num_corde):
            if note_freq[i] > 0:
                suoni.configura_renderer(renderers[i], note_freq[i], stato['parametri'])

    def suona_corda(i):
        if note_freq[i] <= 0:
            return
        if stato['suono'] == 'midi':
            if midi_nums[i] is not None:
                GBAudio.play_midi_note_temp(midi_nums[i], stato['parametri']['dur'])
            return
        mono = suoni.mono_da_renderer(renderers[i])
        if mono is not None:
            poly_player.pluck(i, mono)

    configura_tutti()
    note_prompt_str = " - ".join(nomi)
    poly_player.start()
    try:
        while True:
            print(f"\rNote: {note_prompt_str} (1-{max_keys}, A, Q, SPAZIO, ESC): {' ' * 10}\r", end="", flush=True)
            scelta = key().lower()
            if scelta.isdigit():
                key_int = int(scelta) if scelta != '0' else 10
                if 1 <= key_int <= max_keys:
                    suona_corda(key_int - 1)
            elif scelta == ' ':
                stato['suono'] = suoni.prossimo_suono(stato['suono'])
                stato['parametri'] = suoni.parametri_suono(stato['suono'])
                configura_tutti()
                print(f"\nSuono: {suoni.descrizione_suono(stato['suono'])}")
            elif scelta == chr(27):
                print("\nUscita dal menu ascolto.")
                break
            elif scelta in ('a', 'q'):
                # In battere dalla corda grave, in levare dalla acuta
                ordine = range(num_corde) if scelta == 'q' else range(num_corde - 1, -1, -1)
                for i in ordine:
                    if note_freq[i] > 0:
                        suona_corda(i)
                        aspetta(0.07)
            else:
                print(f"\nComando non valido. Premi 1-{max_keys}, A, Q, SPAZIO o ESC.")
    finally:
        poly_player.stop()


def PlayerGenerico():
    """La tastiera del PC come strumento, con la tastiera MIDI se collegata."""
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
    renderers = [GBAudio.NoteRenderer(fs=GBAudio.FS) for _ in range(NUM_VOCI)]

    def suona_sintesi(midi_num):
        """Una voce a rotazione, cosi' le note tenute continuano a suonare."""
        v = stato['voce'] % NUM_VOCI
        stato['voce'] += 1
        suoni.configura_renderer(renderers[v], GBAudio.midi_to_freq(midi_num), stato['parametri'])
        mono = suoni.mono_da_renderer(renderers[v])
        if mono is not None:
            poly_player.pluck(v, mono)

    def nome_nota(midi_num):
        return get_nota(pitch.Pitch(midi=midi_num).nameWithOctave.replace('-', 'b'))

    def riga_stato():
        print(f"\r[Suono: {suoni.descrizione_suono(stato['suono'])}] Ottava base: {stato['ottava']}{' ' * 20}\r", end="", flush=True)

    midi_in = GBAudio.get_midi_in()
    old_on_note_on = old_on_note_off = None
    if midi_in is not None:
        old_on_note_on = midi_in.on_note_on
        old_on_note_off = midi_in.on_note_off

        def player_note_on(note_num, velocity):
            if stato['suono'] == 'midi':
                GBAudio.get_midi_out().note_on(note_num, velocity)
            else:
                suona_sintesi(note_num)
            print(f"\r[Tastiera MIDI] Nota: {nome_nota(note_num)} ({GBAudio.midi_to_freq(note_num):.1f} Hz){' ' * 15}\r", end="", flush=True)

        def player_note_off(note_num):
            if stato['suono'] == 'midi':
                GBAudio.get_midi_out().note_off(note_num)

        midi_in.on_note_on = player_note_on
        midi_in.on_note_off = player_note_off
    poly_player.start()
    riga_stato()
    try:
        while True:
            ch = key()
            if not ch:
                continue
            if ch == chr(27):
                break
            if ch == ' ':
                stato['suono'] = suoni.prossimo_suono(stato['suono'])
                stato['parametri'] = suoni.parametri_suono(stato['suono'])
                riga_stato()
            elif ch in OTTAVE_FUNZIONE:
                stato['ottava'] = OTTAVE_FUNZIONE[ch]
                riga_stato()
            elif ch in KB_MAP:
                semitones, oct_offset = KB_MAP[ch]
                # Tiene le frequenze dentro l'udibile
                actual_octave = min(9, max(1, stato['ottava'] + oct_offset))
                midi_num = 12 + semitones + 12 * actual_octave
                if stato['suono'] == 'midi':
                    GBAudio.play_midi_note_temp(midi_num, stato['parametri']['dur'])
                else:
                    suona_sintesi(midi_num)
                print(f"\rUltima nota: {nome_nota(midi_num)} ({GBAudio.midi_to_freq(midi_num):.1f} Hz) [Ottava base: {stato['ottava']}]{' ' * 15}\r", end="", flush=True)
    finally:
        if midi_in is not None:
            midi_in.on_note_on = old_on_note_on
            midi_in.on_note_off = old_on_note_off
        poly_player.stop()
        print("\nUscita dal Player Generico.")
