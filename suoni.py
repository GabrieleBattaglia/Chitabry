# Chitabry, suoni: cio' che tastiera, accordi, scale e gioco hanno in comune per suonare una nota.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la revisione 1 del 2026-09-09: le stesse trenta righe per leggere i
# parametri del suono, configurare il renderer e ricavare il mono per il mixer
# erano ripetute in sei punti di views.py e gioca_suono.py.
# Dalla 9.10.0 c'e' un quarto suono, il banco: un soundfont General MIDI
# suonato da FluidSynth, nota per nota, che passa dal mixer come i sintetici.

import os

import numpy as np
import sounddevice as sd

import banchi
import config
import GBAudio

CICLO_SUONI = ("suono_1", "suono_2", "midi", "banco")
# Il rilascio di una nota del banco lasciata sulla Tastiera, in secondi
RILASCIO_BANCO = 0.15
# Se il banco non suona, lo si dice una volta sola e non a ogni nota
_BANCO_AVVISATO = []


def banco_pronto():
    """Vero se il suono banco si puo' usare: FluidSynth scaricato e un banco
    scelto che c'e' ancora. Se no, il banco si salta nella rotazione."""
    percorso = config.impostazioni.get('banco', {}).get('percorso', '')
    return bool(percorso) and os.path.isfile(percorso) and banchi.fluidsynth_presente()


def suono_attivo():
    """La chiave del suono scelto nelle impostazioni."""
    return config.impostazioni.get('tipo_suono', 'suono_1')


def prossimo_suono(chiave):
    """Il suono che segue nella rotazione suono_1, suono_2, midi, banco, che
    e' quella della barra spaziatrice. Il banco c'e' solo se e' pronto."""
    ciclo = [c for c in CICLO_SUONI if c != "banco" or banco_pronto()]
    if chiave not in ciclo:
        return ciclo[0]
    return ciclo[(ciclo.index(chiave) + 1) % len(ciclo)]


def descrizione_suono(chiave):
    """Come chiamare il suono a voce."""
    if chiave == "midi":
        inst_idx = config.impostazioni.get("midi_strumento", 0)
        return f"MIDI ({GBAudio.MIDI_INSTRUMENTS[inst_idx]})"
    if chiave == "banco":
        inst_idx = config.impostazioni.get("midi_strumento", 0)
        nome = os.path.basename(config.impostazioni.get('banco', {}).get('percorso', '')) or "nessuno"
        return f"Banco {nome} ({GBAudio.MIDI_INSTRUMENTS[inst_idx]})"
    return config.impostazioni[chiave]["descrizione"]


def sigla_suono(chiave):
    """La sigla corta per le righe di stato: S1, S2, MID o BAN."""
    if chiave == "midi":
        return "MID"
    if chiave == "banco":
        return "BAN"
    return "S2" if chiave == "suono_2" else "S1"


def parametri_suono(chiave):
    """I parametri di sintesi del suono indicato, con i ripieghi di sempre.
    Per midi si prendono quelli del suono 1, che servono per la durata. Per
    il banco ci sono il file, lo strumento General MIDI, che e' quello scelto
    per il MIDI, la durata e il volume."""
    if chiave == "banco":
        b = config.impostazioni.get('banco', {})
        return {
            'karplus': False, 'banco': True,
            'percorso': b.get('percorso', ''),
            'programma': config.impostazioni.get('midi_strumento', 0),
            'dur': b.get('dur', 4.0), 'vol': b.get('volume', 0.8),
            'hardness': 0.6, 'damping': 0.997, 'pick_pos': 0.15, 'bright': 0.4,
            'kind': 1, 'adsr': [0, 0, 100, RILASCIO_BANCO * 1000],
        }
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
    if parametri.get('banco'):
        # La nota del banco viaggia attaccata al renderer, che resta quello
        # di GBAudio: chi lo usa non deve sapere quale suono sta suonando
        renderer.nota_del_banco = banchi.RendererBanco(parametri['percorso'], parametri['programma'], renderer.fs)
        renderer.nota_del_banco.set_params(freq, durata, parametri['vol'])
        return
    renderer.nota_del_banco = None
    if parametri['karplus']:
        renderer.set_params(freq, durata, parametri['vol'], 0.0,
                            pluck_hardness=parametri['hardness'], damping_factor=parametri['damping'],
                            pick_position=parametri['pick_pos'], brightness=parametri['bright'])
    else:
        renderer.set_params(freq, durata, parametri['vol'], 0.0, kind=parametri['kind'], adsr_list=parametri['adsr'])


def mono_da_renderer(renderer):
    """Rende la nota e ne restituisce il canale mono, senza il pan del renderer;
    None se non c'e' niente da suonare. Resta float32 come il mixer: la
    divisione per il pan lo promuoverebbe a float64, il doppio della memoria."""
    if getattr(renderer, 'nota_del_banco', None) is not None:
        try:
            stereo = renderer.nota_del_banco.render()
        except OSError as e:
            _avvisa_banco(e)
            return None
        return stereo[:, 0] if stereo.size else None
    stereo = renderer.render()
    if stereo.size == 0:
        return None
    if renderer.pan_l != 0:
        return (stereo[:, 0] / renderer.pan_l).astype(np.float32, copy=False)
    return stereo[:, 0]


def tenuta_da_renderer(renderer):
    """La nota tenuta della Tastiera, come coppia (mono, ciclo): dal banco,
    se il renderer ne ha una, altrimenti dall'inviluppo del sintetico."""
    if getattr(renderer, 'nota_del_banco', None) is not None:
        try:
            return renderer.nota_del_banco.render_tenuta()
        except OSError as e:
            _avvisa_banco(e)
            return np.zeros(0, dtype=np.float32), None
    return renderer.render_tenuta()


def _avvisa_banco(errore):
    if not _BANCO_AVVISATO:
        print(f"Il banco di suoni non suona: {errore}.")
        _BANCO_AVVISATO.append(True)


def secondi_di_rilascio(parametri, minimo=0.02):
    """Quanto dura la chiusura di una nota lasciata, in secondi.
    E' il rilascio dell'inviluppo, cioe' il quarto valore dell'ADSR, che dal
    formato 2 delle impostazioni e' scritto in millesimi di secondo e non piu'
    in percentuale della durata. Il minimo serve per gli inviluppi che il
    rilascio non ce l'hanno:
    chiudere di colpo farebbe uno scatto, e venti millesimi bastano a evitarlo
    senza che la nota strascichi.
    La corda pizzicata non ha un inviluppo da leggere: li' il rilascio e' la
    mano appoggiata sulle corde, e sessanta millesimi sono il gesto giusto.
    """
    if parametri['karplus']:
        return 0.06
    return max(minimo, parametri['adsr'][3] / 1000.0)


def pan_per_voce(indice, numero_voci):
    """Posizione stereo della voce indice fra numero_voci, da -0.8 a sinistra a 0.8 a destra."""
    if numero_voci <= 1:
        return 0.0
    return -0.8 + indice * (1.6 / (numero_voci - 1))


def prepara_canale_armonica():
    """Mette il programma Harmonica sul canale dell'armonica. Restituisce il
    canale su cui suonare: quello dell'armonica, o il primo se la porta MIDI
    non si e' aperta, dove comunque non suonera' niente."""
    porta = GBAudio.get_midi_out()
    if porta.h_midi is None:
        return 0
    porta.program_change(GBAudio.PROGRAMMA_ARMONICA, GBAudio.CANALE_ARMONICA)
    porta.control_change(GBAudio.CC_VOLUME, volume_midi_attuale(), GBAudio.CANALE_ARMONICA)
    return GBAudio.CANALE_ARMONICA


def volume_midi_attuale():
    """Il volume delle note MIDI scelto nelle impostazioni, da 0 a 127."""
    return GBAudio.volume_midi(config.impostazioni.get('midi_volume', 100))


def applica_volume_midi():
    """Manda il volume delle impostazioni ai canali delle note: quello degli
    strumenti e quello dell'armonica. Si chiama quando il volume cambia."""
    porta = GBAudio.get_midi_out()
    if porta.h_midi is None:
        return
    for canale in (0, GBAudio.CANALE_ARMONICA):
        porta.control_change(GBAudio.CC_VOLUME, volume_midi_attuale(), canale)


def parametri_armonica(chiave):
    """I parametri del suono per le note dell'armonica: dal banco suonano
    con lo strumento Harmonica, come col MIDI."""
    parametri = parametri_suono(chiave)
    if parametri.get('banco'):
        parametri = dict(parametri, programma=GBAudio.PROGRAMMA_ARMONICA)
    return parametri


def mono_delle_note(numeri_midi, parametri, dur=None):
    """Piu' note insieme in un mono solo, gia' pronto per stare al centro:
    se la somma, divisa sui due canali, supera il pieno, si riporta giu'.
    dur e' la durata di ogni nota, o None per quella del suono. Restituisce
    None se non c'e' niente da suonare."""
    pezzi = []
    for numero in numeri_midi:
        renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
        configura_renderer(renderer, GBAudio.midi_to_freq(numero), parametri, dur=dur)
        mono = mono_da_renderer(renderer)
        if mono is not None and mono.size > 0:
            pezzi.append(mono)
    if not pezzi:
        return None
    mix = np.zeros(max(len(p) for p in pezzi), dtype=np.float32)
    for pezzo in pezzi:
        mix[:len(pezzo)] += pezzo
    if dur is not None and parametri['karplus']:
        # La corda pizzicata tagliata prima che si spenga da sola finirebbe
        # con uno scatto: si chiude con la stessa rampa di una nota lasciata
        coda = min(len(mix), round(secondi_di_rilascio(parametri) * GBAudio.FS))
        mix[len(mix) - coda:] *= np.linspace(1.0, 0.0, coda, dtype=np.float32)
    # Al centro ciascun canale riceve il mono per il coseno di 45 gradi:
    # piu' note insieme sommano il volume, e oltre il pieno si riporta giu'
    picco = float(np.abs(mix).max()) * float(np.cos(np.pi / 4))
    if picco > 1.0:
        mix /= np.float32(picco)
    return mix


def suona_note(numeri_midi, armonica=False):
    """Suona subito una o piu' note insieme con il suono attivo, al centro e
    senza mixer: una nota trovata sull'armonica, o un gruppo di fori.
    Con armonica vero e il suono MIDI, le note escono con il programma
    Harmonica sul suo canale."""
    chiave = suono_attivo()
    parametri = parametri_armonica(chiave) if armonica else parametri_suono(chiave)
    if chiave == 'midi':
        canale = prepara_canale_armonica() if armonica else 0
        for numero in numeri_midi:
            GBAudio.play_midi_note_temp(numero, parametri['dur'], canale=canale)
        return
    mix = mono_delle_note(numeri_midi, parametri)
    if mix is None:
        return
    # Al centro, con la stessa potenza di prima su ciascun canale
    stereo = np.column_stack([mix, mix]) * np.float32(np.cos(np.pi / 4))
    sd.play(stereo, samplerate=GBAudio.FS, blocking=False)


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
    if parametri.get('banco'):
        configura_renderer(renderer, freq, parametri)
        mono = mono_da_renderer(renderer)
        if mono is not None and mono.size > 0:
            angolo = (pan + 1.0) * np.pi / 4.0
            sd.play(np.column_stack([mono * np.cos(angolo), mono * np.sin(angolo)]).astype(np.float32),
                    samplerate=GBAudio.FS, blocking=False)
        return
    if parametri['karplus']:
        renderer.set_params(freq, parametri['dur'], parametri['vol'], pan,
                            pluck_hardness=parametri['hardness'], damping_factor=parametri['damping'],
                            pick_position=parametri['pick_pos'], brightness=parametri['bright'])
    else:
        renderer.set_params(freq, parametri['dur'], parametri['vol'], pan, kind=parametri['kind'], adsr_list=parametri['adsr'])
    note_audio = renderer.render()
    if note_audio.size > 0:
        sd.play(note_audio, samplerate=GBAudio.FS, blocking=False)
