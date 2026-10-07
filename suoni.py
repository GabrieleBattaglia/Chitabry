# Chitabry, suoni: cio' che tastiera, accordi, scale e gioco hanno in comune per suonare una nota.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la revisione 1 del 2026-09-09: le stesse trenta righe per leggere i
# parametri del suono, configurare il renderer e ricavare il mono per il mixer
# erano ripetute in sei punti di views.py e gioca_suono.py.
# Dalla 9.10.0 c'e' il banco: un soundfont General MIDI suonato da
# FluidSynth, nota per nota, che passa dal mixer come i sintetici. Dalla
# 10.0.0 e' l'unico MIDI: il sintetizzatore di Windows, lento a rispondere,
# se ne va (collaudo di Gabriele del 7 ottobre 2026), e il banco suona in due
# modi, con lo strumento scelto nelle impostazioni e con quello dello
# strumento attivo.

import os
import threading

import numpy as np
import sounddevice as sd

import banchi
import config
import GBAudio

# Il giro della barra spaziatrice: i due sintetici, il banco con lo strumento
# scelto e il banco con lo strumento General MIDI dello strumento attivo
CICLO_SUONI = ("suono_1", "suono_2", "banco", "banco_strumento")
# Il rilascio di una nota del banco lasciata sulla Tastiera, in secondi
RILASCIO_BANCO = 0.15
# Se il banco non suona, lo si dice una volta sola e non a ogni nota
_BANCO_AVVISATO = []


def banco_pronto():
    """Vero se il banco si puo' usare: FluidSynth c'e' e il banco scelto
    c'e' ancora. Se no, i suoni del banco si saltano nel giro."""
    banco = config.impostazioni.get('banco')
    percorso = banco.get('percorso', '') if isinstance(banco, dict) else ''
    return isinstance(percorso, str) and bool(percorso) and os.path.isfile(percorso) and banchi.fluidsynth_presente()


def programma_scelto():
    """Lo strumento General MIDI scelto per il banco nelle impostazioni."""
    programma = config.impostazioni.get('midi_strumento', 0)
    if isinstance(programma, bool) or not isinstance(programma, int) or not 0 <= programma <= 127:
        return 0
    return programma


def programma_attivo():
    """Lo strumento General MIDI dello strumento attivo, o None se non ne ha
    uno, come un ukulele."""
    strumenti = config.impostazioni.get('strumenti', {})
    conf = strumenti.get(config.impostazioni.get('strumento_attivo')) if isinstance(strumenti, dict) else None
    return config.programma_dello_strumento(conf)


def suono_disponibile(chiave):
    """Se quel suono si puo' suonare adesso. Il banco con lo strumento
    dell'attivo c'e' solo quando l'attivo ha uno strumento General MIDI
    diverso da quello scelto: se sono lo stesso, il giro ha un suono in meno."""
    if chiave in ("suono_1", "suono_2"):
        return True
    if chiave == "banco":
        return banco_pronto()
    if chiave == "banco_strumento":
        programma = programma_attivo()
        return programma is not None and programma != programma_scelto() and banco_pronto()
    return False


def suono_attivo():
    """La chiave del suono scelto nelle impostazioni, se adesso si puo'
    suonare; altrimenti il banco con lo strumento scelto, se e' pronto, o il
    primo suono sintetico."""
    chiave = config.impostazioni.get('tipo_suono', 'suono_1')
    if suono_disponibile(chiave):
        return chiave
    return "banco" if chiave == "banco_strumento" and banco_pronto() else "suono_1"


def prossimo_suono(chiave):
    """Il suono che segue nel giro della barra spaziatrice, saltando quelli
    che adesso non si possono suonare."""
    ciclo = [c for c in CICLO_SUONI if suono_disponibile(c)]
    if chiave not in ciclo:
        return ciclo[0]
    return ciclo[(ciclo.index(chiave) + 1) % len(ciclo)]


def nome_del_programma(programma):
    """Il nome General MIDI di uno strumento, o nessuno."""
    return GBAudio.MIDI_INSTRUMENTS[programma] if programma is not None else "nessuno"


def descrizione_suono(chiave):
    """Come chiamare il suono a voce."""
    if chiave in ("banco", "banco_strumento"):
        banco = config.impostazioni.get('banco', {})
        nome = os.path.basename(banco.get('percorso', '') if isinstance(banco, dict) else '') or "nessuno"
        if chiave == "banco":
            return f"Banco {nome}, strumento scelto ({nome_del_programma(programma_scelto())})"
        return f"Banco {nome}, strumento dell'attivo ({nome_del_programma(programma_attivo())})"
    return config.impostazioni[chiave]["descrizione"]


def sigla_suono(chiave):
    """La sigla corta per le righe di stato: S1, S2, BAN per il banco con lo
    strumento scelto e STR per quello con lo strumento dell'attivo."""
    if chiave == "banco":
        return "BAN"
    if chiave == "banco_strumento":
        return "STR"
    return "S2" if chiave == "suono_2" else "S1"


def parametri_suono(chiave):
    """I parametri di sintesi del suono indicato, con i ripieghi di sempre.
    Per il banco ci sono il file, lo strumento General MIDI, quello scelto o
    quello dell'attivo, la durata e il volume. Una chiave sconosciuta, come
    il midi di un archivio vecchio, vale il primo suono sintetico."""
    if chiave in ("banco", "banco_strumento"):
        b = config.impostazioni.get('banco', {})
        programma = programma_attivo() if chiave == "banco_strumento" else None
        return {
            'karplus': False, 'banco': True,
            'percorso': b.get('percorso', ''),
            'programma': programma if programma is not None else programma_scelto(),
            'dur': b.get('dur', 4.0), 'vol': b.get('volume', 0.8),
            'hardness': 0.6, 'damping': 0.997, 'pick_pos': 0.15, 'bright': 0.4,
            'kind': 1, 'adsr': [0, 0, 100, RILASCIO_BANCO * 1000],
        }
    s = config.impostazioni["suono_2" if chiave == "suono_2" else "suono_1"]
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


def suona_note(numeri_midi):
    """Suona subito una o piu' note insieme con il suono attivo, al centro e
    senza mixer: per esempio la nota trovata sull'armonica in Trova
    Posizione."""
    mix = mono_delle_note(numeri_midi, parametri_suono(suono_attivo()))
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


def tieni_nota(mixer, voce, frequenza, parametri, tiene=True, guadagno=1.0):
    """Fa partire su una voce del mixer una nota che dura finche' il tasto e'
    giu', come nella Tastiera: la nota tenuta del suono, che il mixer chiude
    con la rampa quando la si lascia. Con tiene falso, dove la tastiera non
    sa dire quando un tasto si lascia, la nota e' pizzicata e decade da sola.
    guadagno abbassa le note che suonano insieme, come in un accordo.
    Restituisce True se la nota suona."""
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    configura_renderer(renderer, frequenza, parametri)
    if not tiene:
        mono = mono_da_renderer(renderer)
        if mono is None or mono.size == 0:
            return False
        mixer.pluck(voce, mono * np.float32(guadagno) if guadagno != 1.0 else mono)
        return True
    mono, ciclo = tenuta_da_renderer(renderer)
    if mono.size == 0:
        return False
    mixer.tieni(voce, mono * np.float32(guadagno) if guadagno != 1.0 else mono, ciclo)
    return True


def tieni_note_insieme(mixer, voci_e_frequenze, parametri):
    """Piu' note tenute insieme, ciascuna sulla sua voce, come un accordo
    sull'armonica: se la somma dei loro picchi, al centro, supera il pieno,
    si abbassano tutte dello stesso tanto, perche' il mixer non tagli.
    Restituisce le voci che suonano."""
    tenute = []
    for voce, frequenza in voci_e_frequenze:
        renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
        configura_renderer(renderer, frequenza, parametri)
        mono, ciclo = tenuta_da_renderer(renderer)
        if mono.size > 0:
            tenute.append((voce, mono, ciclo))
    somma = sum(float(np.abs(mono).max()) for _, mono, _ in tenute) * float(np.cos(np.pi / 4))
    guadagno = np.float32(1.0 / somma) if somma > 1.0 else None
    for voce, mono, ciclo in tenute:
        mixer.tieni(voce, mono * guadagno if guadagno is not None else mono, ciclo)
    return [voce for voce, _, _ in tenute]


def lascia_nota(mixer, voce, parametri):
    """Chiude con la rampa del suono la nota tenuta su quella voce."""
    mixer.lascia(voce, secondi_di_rilascio(parametri))


# La tastiera MIDI esterna quando nessun ascolto se la prende, per esempio dal
# menu: le sue note suonano su un mixer tutto loro, finche' il tasto e' giu'.
# Fino alla 9.13 lo faceva il sintetizzatore di Windows, con il suono MIDI.
# Il mixer si apre alla prima nota e si chiude quando tace da un po': un
# flusso audio aperto per tutta la sessione terrebbe impegnato il dispositivo.
# Le note arrivano dal filo di winmm e la chiusura da un timer: il lucchetto
# li tiene in fila.
VOCI_ESTERNE = 16
SILENZIO_PRIMA_DI_CHIUDERE = 3.0
_ESTERNA = {}
_BLOCCO_ESTERNO = threading.RLock()


def _voce_esterna(mixer):
    """Una voce per la nota nuova: mai una che appartiene a un tasto ancora
    giu', anche se il suo buffer e' finito, e possibilmente una che taccia;
    solo con tutte occupate si prende la piu' vecchia a rotazione, e la nota
    che c'era non e' piu' di nessuno."""
    occupate = {voce for voce, _ in _ESTERNA['accese'].values()}
    libere = [v for v in range(VOCI_ESTERNE) if v not in occupate]
    voce = next((v for v in libere if not mixer.sta_suonando(v)), libere[0] if libere else None)
    if voce is None:
        voce = _ESTERNA['voce'] % VOCI_ESTERNE
        _ESTERNA['voce'] += 1
        for numero, (altra, _) in list(_ESTERNA['accese'].items()):
            if altra == voce:
                del _ESTERNA['accese'][numero]
    return voce


def nota_esterna_giu(numero, velocita=127):
    """Una nota della tastiera MIDI esterna scende: parte su una voce libera.
    Se la stessa nota era gia' accesa, per esempio da una tastiera che manda
    la nota su due canali, la si chiude prima: altrimenti resterebbe senza
    nessuno che la lasci."""
    with _BLOCCO_ESTERNO:
        if 'mixer' not in _ESTERNA:
            mixer = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=VOCI_ESTERNE)
            mixer.start()
            _ESTERNA.update(mixer=mixer, voce=0, accese={})
        mixer = _ESTERNA['mixer']
        gia = _ESTERNA['accese'].pop(numero, None)
        if gia is not None:
            lascia_nota(mixer, *gia)
        voce = _voce_esterna(mixer)
        parametri = parametri_suono(suono_attivo())
        if tieni_nota(mixer, voce, GBAudio.midi_to_freq(numero), parametri, guadagno=max(0.1, velocita / 127)):
            _ESTERNA['accese'][numero] = (voce, parametri)


def nota_esterna_su(numero):
    """Una nota della tastiera MIDI esterna risale: si chiude con la rampa."""
    with _BLOCCO_ESTERNO:
        accesa = _ESTERNA.get('accese', {}).pop(numero, None)
        if accesa is not None:
            lascia_nota(_ESTERNA['mixer'], *accesa)
        _forse_chiudi_dopo()


def chiudi_note_esterne():
    """Chiude con la rampa tutte le note della tastiera esterna: si chiama
    quando un ascolto si prende la tastiera, che da li' in poi manda i
    rilasci a lui, e quando la tastiera MIDI cambia o si scollega."""
    with _BLOCCO_ESTERNO:
        for voce, parametri in _ESTERNA.get('accese', {}).values():
            lascia_nota(_ESTERNA['mixer'], voce, parametri)
        if 'accese' in _ESTERNA:
            _ESTERNA['accese'].clear()
        _forse_chiudi_dopo()


def _forse_chiudi_dopo():
    """Con nessun tasto giu', fra qualche secondo si chiude il mixer."""
    if 'mixer' in _ESTERNA and not _ESTERNA['accese']:
        timer = threading.Timer(SILENZIO_PRIMA_DI_CHIUDERE, _chiudi_se_tace)
        timer.daemon = True
        timer.start()


def _chiudi_se_tace():
    with _BLOCCO_ESTERNO:
        mixer = _ESTERNA.get('mixer')
        if mixer is None or _ESTERNA['accese']:
            return
        if any(mixer.sta_suonando(v) for v in range(VOCI_ESTERNE)):
            # Una nota lasciata che sfuma ancora, o pizzicata che decade
            _forse_chiudi_dopo()
            return
        mixer.stop()
        _ESTERNA.clear()
