# Chitabry, suoni: cio' che tastiera, accordi, scale e gioco hanno in comune per suonare una nota.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09: le stesse trenta righe per leggere i
# parametri del suono, configurare il renderer e ricavare il mono per il mixer
# erano ripetute in sei punti di views.py e gioca_suono.py.

import sounddevice as sd

import config
import GBAudio

CICLO_SUONI = ("suono_1", "suono_2", "midi")


def suono_attivo():
    """La chiave del suono scelto nelle impostazioni."""
    return config.impostazioni.get('tipo_suono', 'suono_1')


def prossimo_suono(chiave):
    """Il suono che segue nella rotazione suono_1, suono_2, midi, che e' quella della barra spaziatrice."""
    if chiave not in CICLO_SUONI:
        return CICLO_SUONI[0]
    return CICLO_SUONI[(CICLO_SUONI.index(chiave) + 1) % len(CICLO_SUONI)]


def descrizione_suono(chiave):
    """Come chiamare il suono a voce."""
    if chiave == "midi":
        inst_idx = config.impostazioni.get("midi_strumento", 0)
        return f"MIDI ({GBAudio.MIDI_INSTRUMENTS[inst_idx]})"
    return config.impostazioni[chiave]["descrizione"]


def sigla_suono(chiave):
    """La sigla corta per le righe di stato: S1, S2 o MID."""
    if chiave == "midi":
        return "MID"
    return "S2" if chiave == "suono_2" else "S1"


def parametri_suono(chiave):
    """I parametri di sintesi del suono indicato, con i ripieghi di sempre.
    Per midi si prendono quelli del suono 1, che servono per la durata."""
    s = config.impostazioni["suono_1" if chiave == "midi" else chiave]
    return {
        'karplus': 'pluck_hardness' in s,
        'dur': s.get('dur_accordi', 9.0),
        'vol': s.get('volume', 0.35),
        'hardness': s.get('pluck_hardness', 0.6),
        'damping': s.get('damping_factor', 0.997),
        'pick_pos': s.get('pick_position', 0.15),
        'bright': s.get('brightness', 0.4),
        'kind': s.get('kind', 1),
        'adsr': s.get('adsr', [0, 0, 0, 0]),
    }


def configura_renderer(renderer, freq, parametri, dur=None):
    """Imposta il renderer per una nota, senza pan: della posizione stereo si
    occupa il mixer con set_pan, cosi' il mono si ricava sempre allo stesso modo."""
    durata = parametri['dur'] if dur is None else dur
    if parametri['karplus']:
        renderer.set_params(freq, durata, parametri['vol'], 0.0,
                            pluck_hardness=parametri['hardness'], damping_factor=parametri['damping'],
                            pick_position=parametri['pick_pos'], brightness=parametri['bright'])
    else:
        renderer.set_params(freq, durata, parametri['vol'], 0.0, kind=parametri['kind'], adsr_list=parametri['adsr'])


def mono_da_renderer(renderer):
    """Rende la nota e ne restituisce il canale mono, senza il pan del renderer;
    None se non c'e' niente da suonare."""
    stereo = renderer.render()
    if stereo.size == 0:
        return None
    if renderer.pan_l != 0:
        return stereo[:, 0] / renderer.pan_l
    return stereo[:, 0]


def pan_per_voce(indice, numero_voci):
    """Posizione stereo della voce indice fra numero_voci, da -0.8 a sinistra a 0.8 a destra."""
    if numero_voci <= 1:
        return 0.0
    return -0.8 + indice * (1.6 / (numero_voci - 1))


def suona_una_nota(nota_std, pan=0.0):
    """Suona subito una nota con il suono attivo, senza mixer: per le prove
    isolate come Trova Posizione."""
    chiave = suono_attivo()
    parametri = parametri_suono(chiave)
    if chiave == 'midi':
        GBAudio.play_midi_note_temp(GBAudio.note_to_midi(nota_std), parametri['dur'])
        return
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    freq = GBAudio.note_to_freq(nota_std)
    if parametri['karplus']:
        renderer.set_params(freq, parametri['dur'], parametri['vol'], pan,
                            pluck_hardness=parametri['hardness'], damping_factor=parametri['damping'],
                            pick_position=parametri['pick_pos'], brightness=parametri['bright'])
    else:
        renderer.set_params(freq, parametri['dur'], parametri['vol'], pan, kind=parametri['kind'], adsr_list=parametri['adsr'])
    note_audio = renderer.render()
    if note_audio.size > 0:
        sd.play(note_audio, samplerate=GBAudio.FS, blocking=False)
