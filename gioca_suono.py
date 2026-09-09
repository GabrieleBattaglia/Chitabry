# Chitabry, gioca col suono: l'allenamento dell'orecchio su note e frequenze, con la classifica.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Revisione 1 del 2026-09-09: i parametri del suono passano dagli helper di
# suoni.py invece di essere riletti qui, la classifica si legge in modo
# lineare e il punteggio si salva subito.

import random
import time
from datetime import datetime

from GBUtils import dgt, enter_escape, key, menu
from music21 import pitch

import config
import GBAudio
import suoni
from nomenclatura import get_nota, nome_utente_in_std

NUM_ROUND = 30
MIDI_MIN = 36   # Do2
MIDI_MAX = 96   # Do7
FREQ_MIN = 65   # circa Do2
FREQ_MAX = 2093  # circa Do7
POSTI_IN_CLASSIFICA = 30
NATURALI = (0, 2, 4, 5, 7, 9, 11)


def _obiettivo(tipo, include_diesis):
    """La coppia (numero MIDI o None, frequenza) da indovinare in questo round."""
    if tipo == 'n':
        if include_diesis:
            target_midi = random.randint(MIDI_MIN, MIDI_MAX)
        else:
            target_midi = random.choice([m for m in range(MIDI_MIN, MIDI_MAX + 1) if m % 12 in NATURALI])
        return target_midi, GBAudio.midi_to_freq(target_midi)
    return None, float(random.randint(FREQ_MIN, FREQ_MAX))


def _risposta_nota(ans_str):
    """Da cio' che l'utente ha scritto, per esempio DO4 o C4, al numero MIDI; None se non valido."""
    if not ans_str[-1].isdigit():
        print("Errore: Includi l'ottava (es. DO4).")
        return None
    nota_std = nome_utente_in_std(ans_str[:-1])
    if nota_std is None:
        print(f"Nota non valida in {config.impostazioni['nomenclatura']}.")
        return None
    return pitch.Pitch(nota_std + ans_str[-1]).midi


def _durata_testo(durata_sec):
    minuti = int(durata_sec // 60)
    secondi = int(durata_sec % 60)
    millisecondi = int((durata_sec - int(durata_sec)) * 1000)
    return f"{minuti:02d}.{secondi:02d}.{millisecondi:03d}"


def _aggiorna_classifica(tipo, precisione_finale, durata_sec, durata_str):
    """Inserisce il risultato nella classifica se ci entra e la stampa."""
    tipo_classifica = 'classifica_note' if tipo == 'n' else 'classifica_freq'
    classifica = config.impostazioni.setdefault(tipo_classifica, [])
    entra = len(classifica) < POSTI_IN_CLASSIFICA
    if not entra:
        peggiore = classifica[-1]
        entra = precisione_finale > peggiore['precisione'] or (precisione_finale == peggiore['precisione'] and durata_sec < peggiore['durata_sec'])
    if entra:
        print(f"Complimenti! Sei entrato nei primi {POSTI_IN_CLASSIFICA} della Hall of Fame!")
        nome_giocatore = dgt("Inserisci il tuo nome (max 20 car): ", kind="s").strip() or "Anonimo"
        classifica.append({
            'nome': nome_giocatore[:20].title(),
            'precisione': precisione_finale,
            'durata_sec': durata_sec,
            'durata_str': durata_str,
            'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        })
        # Precisione decrescente, a parita' il tempo minore
        classifica.sort(key=lambda x: (-x['precisione'], x['durata_sec']))
        del classifica[POSTI_IN_CLASSIFICA:]
        config.salva_modifiche()
    print("Classifica:")
    for i, r in enumerate(classifica, 1):
        print(f"{i}. {r['nome'][:20]}: precisione {r['precisione']:.2f}%, tempo {r['durata_str']}, {r['data']}.")


def avvia():
    """Voce di menu: il gioco delle note e delle frequenze."""
    print("Gioca col suono.")
    tipo = menu(d={"n": "Note", "f": "Frequenze"}, keyslist=True, show=True, ntf="Scelta non valida", p="Scegli il tipo di gioco: ")
    if not tipo:
        print("Uscita dal gioco.")
        return
    include_diesis = False
    if tipo == 'n':
        include_diesis = enter_escape("Includere le note alterate (diesis/bemolli)? [INVIO per si', ESC per no]: ")
    score_totale = 0.0
    start_time = time.time()
    stato = {'suono': 'suono_1'}
    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=1)
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    poly_player.start()
    if tipo == 'n':
        print("Limiti di gioco: da C2 a C7 (Note)")
    else:
        print(f"Limiti di gioco: da {FREQ_MIN} Hz a {FREQ_MAX} Hz (Frequenze)")
    print("Comandi: qualsiasi tasto ascolta, Invio risponde, Spazio cambia suono, ESC esce.")

    def suona_obiettivo(target_freq):
        parametri = suoni.parametri_suono(stato['suono'])
        # Il suono sintetico dura due secondi, il pizzicato la sua durata naturale
        suoni.configura_renderer(renderer, target_freq, parametri, dur=None if parametri['karplus'] else 2.0)
        mono = suoni.mono_da_renderer(renderer)
        if mono is not None:
            poly_player.pluck(0, mono)

    try:
        round_idx = 1
        last_result_str = "Nuova partita,"
        while round_idx <= NUM_ROUND:
            target_midi, target_freq = _obiettivo(tipo, include_diesis)
            suona_obiettivo(target_freq)
            while True:
                print(f"\r{last_result_str} ({round_idx}/{NUM_ROUND}) > {' ' * 5}\r", end="", flush=True)
                comando = key()
                if comando is None or comando == chr(27):
                    print("\nEsercizio concluso prematuramente. Il punteggio non sara' salvato.")
                    return
                if comando == ' ':
                    stato['suono'] = 'suono_2' if stato['suono'] == 'suono_1' else 'suono_1'
                    print(f"\r[Suono: {suoni.descrizione_suono(stato['suono'])}]{' ' * 20}\r", end="", flush=True)
                    continue
                if comando not in ('\r', '\n'):
                    suona_obiettivo(target_freq)
                    continue
                poly_player.mute(0)
                print()
                if tipo == 'n':
                    ans_str = dgt("Inserisci la nota (es. DO4 o C4): ", kind="s").strip().upper()
                    if not ans_str:
                        continue
                    ans_midi = _risposta_nota(ans_str)
                    if ans_midi is None:
                        continue
                    diff = abs(target_midi - ans_midi)
                    punteggio_round = 100.0 if diff == 0 else max(0.0, 100.0 - (diff * (100.0 / 24.0)))
                    score_totale += punteggio_round
                    media_score = score_totale / round_idx
                    target_name = get_nota(pitch.Pitch(midi=target_midi).nameWithOctave.replace('-', 'b'))
                    segno = "" if diff == 0 else ("+" if ans_midi > target_midi else "-")
                    last_result_str = f"R:{ans_str}, {segno}{diff}, C:{target_name} S:{media_score:.0f}%,"
                else:
                    ans = dgt("Inserisci la frequenza in Hz: ", kind="f")
                    diff = abs(target_freq - ans)
                    if diff <= 10.0:
                        punteggio_round = 100.0
                    elif diff <= 100.0:
                        punteggio_round = 100.0 - ((diff - 10.0) * (100.0 / 90.0))
                    else:
                        punteggio_round = 0.0
                    score_totale += punteggio_round
                    media_score = score_totale / round_idx
                    segno = "" if diff == 0 else ("+" if ans > target_freq else "-")
                    last_result_str = f"R:{ans:.0f}, {segno}{diff:.0f}, C:{target_freq:.0f} S:{media_score:.0f}%,"
                round_idx += 1
                break
    finally:
        poly_player.stop()
    durata_sec = time.time() - start_time
    durata_str = _durata_testo(durata_sec)
    precisione_finale = score_totale / NUM_ROUND
    print("Gioco concluso!")
    print(f"Precisione: {precisione_finale:.2f}%")
    print(f"Tempo: {durata_str}")
    _aggiorna_classifica(tipo, precisione_finale, durata_sec, durata_str)
    key("Premi un tasto per tornare al menu...")
