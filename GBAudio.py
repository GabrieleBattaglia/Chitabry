# GBAudio, motore audio di Chitabry: sintesi dello strumento e dialogo con il MIDI.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Data creazione: 6 gennaio 2026.
# Non e' un doppione di Acusticator e non va unificato con quello: Acusticator
# riproduce effetti brevi da uno score, questo suona uno strumento con note
# tenute e polifoniche e parla con le porte MIDI di Windows. L'unica cosa
# duplicata fra i due e' la conversione da nome di nota a frequenza, tracciata
# nella issue 49.
# Revisione 1 del 2026-09-09: un solo interprete dei nomi di nota da cui
# derivano note_to_freq e note_to_midi; il mixer polifonico protegge buffer e
# indici con un lucchetto e chiude il flusso audio quando si ferma; le
# eccezioni catturate sono quelle che si sanno nominare. Dal 2026-09-10 i
# messaggi MIDI accettano il canale, per le percussioni del canale 10.

import atexit
import ctypes
import math
import re
import threading
import time
import weakref

import numpy as np
import sounddevice as sd
from scipy import signal

# --- Costanti Globali ---
FS = 44100  # Aumentata frequenza di campionamento per KS
BLOCK_SIZE = 256
HARMONICS = [1, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.125, 0.11, 0.1, 0.09, 0.08, 0.07]

_SEMITONI = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
# Simboli microtonali in coda al nome, dal piu' lungo al piu' corto per non
# confondere la doppia tilde con quella singola. Valgono in semitoni.
_MICROTONI = (("~~", 1.5), ("``", -1.5), ("~", 0.5), ("`", -0.5))
_RE_OTTAVA = re.compile(r"\d+$")
_RE_NOTA = re.compile(r"^([a-g])([#b]?)$")


def scomponi_nota(nome):
    """Legge un nome di nota come C4, F#3, Eb2, F~5 o B``4 e restituisce la
    coppia (numero MIDI intero, scostamento microtonale in semitoni), oppure
    None se il testo non e' una nota o e' la pausa p.
    E' l'unico punto in cui si interpreta il nome di una nota: note_to_freq e
    note_to_midi derivano da qui. Fino alla 7.8.3 ognuna aveva la propria
    tabella e le proprie regole, e una nota scritta in un modo poteva valere
    per una e non per l'altra."""
    if not isinstance(nome, str):
        return None
    testo = nome.strip().lower().replace('-', 'b')
    if testo == 'p':
        return None
    ottava = _RE_OTTAVA.search(testo)
    if not ottava:
        return None
    base = testo[:ottava.start()]
    micro = 0.0
    for simbolo, scostamento in _MICROTONI:
        if base.endswith(simbolo):
            micro = scostamento
            base = base[:-len(simbolo)]
            break
    lettera = _RE_NOTA.match(base)
    if not lettera:
        return None
    nota, alterazione = lettera.groups()
    semitono = _SEMITONI[nota] + {'#': 1, 'b': -1}.get(alterazione, 0)
    return 12 + semitono + 12 * int(ottava.group()), micro


def midi_to_freq(midi_num):
    """Frequenza in Hz di un numero MIDI, anche frazionario, con il La a 440."""
    return 440.0 * (2.0 ** ((midi_num - 69) / 12.0))


def note_to_freq(note):
    """Converte la notazione (es. C4, F~5, B`5) in frequenza in Hz.
    Un numero lo considera gia' una frequenza; 0.0 per la pausa o un nome non valido."""
    if isinstance(note, (int, float)) and not isinstance(note, bool):
        return float(note)
    scomposta = scomponi_nota(note)
    if scomposta is None:
        return 0.0
    midi_num, micro = scomposta
    return midi_to_freq(midi_num + micro)

def apri_flusso_uscita(samplerate, channels, dtype, callback, latency='low'):
    """Apre un flusso di uscita sull'interfaccia piu' pronta fra quelle che
    puntano al dispositivo scelto nel sistema.
    Senza dire niente, sounddevice prende la prima interfaccia che trova, che su
    Windows e' MME: misurati novantuno millesimi di scorta contro i ventidue di
    WASAPI, sulla stessa scheda. Sono ritardo che chi suona sente fra il dito e
    la nota, e sono tre quarti del ritardo totale.
    A scegliere e' scegli_dispositivo_audio di GBUtils, la stessa che usano
    CWzator e Acusticator: guarda solo le interfacce che portano allo stesso
    dispositivo, perche' scegliere per sola latenza manderebbe il suono da
    un'altra parte. Costa quattro millesimi la prima volta e niente dopo.
    Se quella scelta non si apre, o se GBUtils non c'e', si lascia fare al
    sistema come si e' sempre fatto: un ritardo si sopporta, restare muti no.
    """
    scelto = None
    try:
        from GBUtils import scegli_dispositivo_audio
        scelto, _api = scegli_dispositivo_audio()
    except Exception:  # noqa: BLE001 - senza la scelta si va avanti col predefinito
        scelto = None
    if scelto is not None:
        try:
            return sd.OutputStream(samplerate=samplerate, channels=channels, dtype=dtype,
                                   device=scelto, callback=callback, latency=latency)
        except Exception:  # noqa: BLE001, S110 - l'interfaccia scelta non regge questo formato, si ripiega sotto
            pass
    return sd.OutputStream(samplerate=samplerate, channels=channels, dtype=dtype,
                           callback=callback, latency=latency)


class FastGuitarSynth:
    """
    Sintetizzatore Karplus-Strong ottimizzato.
    Usa scipy.signal.lfilter per generare l'intero decadimento istantaneamente in C,
    senza lenti cicli for in Python. Aggiunge pick_position per maggior realismo.
    """
    def __init__(self, fs=FS):
        self.fs = fs

    def render_string(self, freq, dur, vol, pluck_hardness=0.6, damping_factor=0.996, pick_position=0.15, brightness=0.4):
        if freq <= 0: return np.zeros(0, dtype=np.float32)

        N_samples = int(self.fs * dur)
        L = int(self.fs / freq)
        if L <= 1: return np.zeros(N_samples, dtype=np.float32)

        # 1. Generazione dell'eccitazione (Rumore + Armoniche)
        noise = np.random.uniform(-1, 1, L).astype(np.float32)

        t = np.linspace(0., 1., L, endpoint=False)
        harmonics = np.zeros(L, dtype=np.float32)
        base_amps = [1.0, 0.5, 0.25, 0.12, 0.06, 0.03]
        for i, amp in enumerate(base_amps):
            harmonics += amp * np.sin(2 * np.pi * (i + 1) * t)

        excitation = (noise * (1.0 - pluck_hardness)) + (harmonics * pluck_hardness)

        # Effetto Comb Filter per la posizione del plettro
        pick_delay = int(pick_position * L)
        if pick_delay > 0:
            excitation = excitation - np.roll(excitation, pick_delay)

        max_e = np.max(np.abs(excitation))
        if max_e > 0: excitation /= max_e

        # 2. Prepara l'input per il filtro IIR
        x = np.zeros(N_samples, dtype=np.float32)
        actual_L = min(L, N_samples)
        x[:actual_L] = excitation[:actual_L]

        # 3. Calcola i coefficienti del filtro Karplus-Strong
        # Eq: y[n] = x[n] + damping * ( (1-S)*y[n-L] + S*y[n-L-1] )
        # S = brightness (0.5 = media standard, <0.5 = più brillante)
        a = np.zeros(L + 2, dtype=np.float32)
        a[0] = 1.0
        a[L] = -damping_factor * (1.0 - brightness)
        a[L+1] = -damping_factor * brightness
        b = [1.0]

        # 4. Applica il filtro (Istantaneo in C)
        y = signal.lfilter(b, a, x)

        max_y = np.max(np.abs(y))
        if max_y > 0: y /= max_y

        y *= vol
        return y.astype(np.float32)

_giocatori_aperti = weakref.WeakSet()


class PolyphonicPlayer:
    """
    Motore di stream continuo. Mixa N canali (bus) indipendenti in tempo reale.
    Se una corda viene ri-suonata, il suo buffer si azzera e riparte,
    mentre le altre corde continuano a suonare.
    Il flusso audio si apre con start e si chiude con stop: fino alla 7.8.3
    si apriva nel costruttore e non si chiudeva mai, e il dispositivo restava
    impegnato finche' il processo non moriva. Buffer e indici di lettura sono
    condivisi fra il thread principale e quello audio, e un lucchetto li tiene
    coerenti: senza, la callback poteva trovare il buffer nuovo con l'indice
    vecchio, e una nota partiva a meta' o non partiva affatto.
    """
    def __init__(self, fs=FS, num_strings=6):
        self.fs = fs
        self.num_strings = num_strings
        self.buses = [np.zeros(0, dtype=np.float32) for _ in range(num_strings)]
        self.indices = [0] * num_strings
        self.pans = np.zeros(num_strings, dtype=np.float32)
        # Il tratto da ripetere finche' la nota e' tenuta, come coppia di
        # indici, o None per le note che decadono da sole e per tutte quelle
        # suonate con pluck, che restano one-shot come sono sempre state.
        self.cicli = [None] * num_strings
        # Il rilascio in corso: quanti campioni ne sono stati fatti e quanti
        # ne servono in tutto. La rampa scende da dov'era il suono fino a zero,
        # cosi' lasciare un tasto non produce lo scatto di un taglio netto.
        self.rilasci = [None] * num_strings
        self._lock = threading.Lock()
        self.stream = None
        self.is_running = False
        _giocatori_aperti.add(self)

    def start(self):
        if self.is_running:
            return
        self.stream = apri_flusso_uscita(
            samplerate=self.fs, channels=2, dtype=np.float32,
            callback=self._audio_callback, latency='low'
        )
        self.stream.start()
        self.is_running = True

    def stop(self):
        """Ferma e chiude il flusso, liberando il dispositivo audio."""
        if not self.is_running:
            return
        self.is_running = False
        self.stream.stop()
        self.stream.close()
        self.stream = None
        self.mute()

    def set_pan(self, string_idx, pan_value):
        if 0 <= string_idx < self.num_strings:
            self.pans[string_idx] = np.clip(pan_value, -1.0, 1.0)

    def pluck(self, string_idx, audio_mono):
        """Suona una corda. Sostituisce il suo bus interrompendone il suono precedente."""
        if 0 <= string_idx < self.num_strings:
            with self._lock:
                self.buses[string_idx] = audio_mono
                self.indices[string_idx] = 0
                self.cicli[string_idx] = None
                self.rilasci[string_idx] = None

    def tieni(self, string_idx, audio_mono, ciclo=None):
        """Suona una nota che resta viva finche' non le si dice di lasciare.
        ciclo e' la coppia di indici del tratto da ripetere, quello che
        render_tenuta ha ricavato dall'inviluppo: finche' la nota e' tenuta il
        suono gira li' dentro invece di finire. Senza ciclo la nota decade come
        con pluck, e lasciare il tasto la smorza prima: e' il caso della corda
        pizzicata, dove tenere non allunga niente ma lasciare mette la mano
        sulla corda."""
        if not 0 <= string_idx < self.num_strings:
            return
        with self._lock:
            self.buses[string_idx] = audio_mono
            self.indices[string_idx] = 0
            self.cicli[string_idx] = ciclo
            self.rilasci[string_idx] = None

    def lascia(self, string_idx, secondi=0.06):
        """Chiude una nota con una rampa discendente, invece di troncarla.
        Sessanta millesimi sono il compromesso trovato: piu' corti si sente lo
        scatto, piu' lunghi la nota strascica sotto quella dopo. La voce esce
        dal ciclo e finisce, quindi anche una nota tenuta da un'ora si spegne."""
        if not 0 <= string_idx < self.num_strings:
            return
        with self._lock:
            if self.indices[string_idx] >= len(self.buses[string_idx]) and self.cicli[string_idx] is None:
                return
            if self.rilasci[string_idx] is not None:
                return
            quanti = max(1, round(secondi * self.fs))
            self.rilasci[string_idx] = [0, quanti]

    def sta_suonando(self, string_idx):
        """Se quella voce ha ancora qualcosa da dire: serve a chi distribuisce
        le note fra le voci per sapere quale puo' riusare."""
        if not 0 <= string_idx < self.num_strings:
            return False
        with self._lock:
            if self.cicli[string_idx] is not None and self.rilasci[string_idx] is None:
                return True
            return self.indices[string_idx] < len(self.buses[string_idx])

    def mute(self, string_idx=None):
        """Silenzia una corda specifica o tutte, subito e senza rampa."""
        with self._lock:
            quali = range(self.num_strings) if string_idx is None else [string_idx]
            for i in quali:
                if 0 <= i < self.num_strings:
                    self.buses[i] = np.zeros(0, dtype=np.float32)
                    self.indices[i] = 0
                    self.cicli[i] = None
                    self.rilasci[i] = None

    def _preleva(self, i, frames):
        """I prossimi campioni di una voce, gia' passati per il ciclo e per il
        rilascio. Restituisce None quando quella voce non ha piu' niente da
        dire, cosi' chi mixa la salta.
        Va chiamata con il lucchetto in mano: tocca buffer, indici e stato."""
        buf = self.buses[i]
        ciclo = self.cicli[i]
        idx = self.indices[i]
        fine = len(buf) if ciclo is None else ciclo[1]
        if idx >= fine and ciclo is None:
            return None
        fuori = np.zeros(frames, dtype=np.float32)
        scritti = 0
        while scritti < frames:
            if ciclo is not None and idx >= ciclo[1]:
                # Torna all'inizio del tratto da ripetere: la coda del tratto e'
                # stata raccordata a questo punto quando la nota e' nata,
                # quindi il giro non produce nessuno scatto.
                idx = ciclo[0]
            if idx >= fine:
                break
            quanti = min(frames - scritti, fine - idx)
            fuori[scritti:scritti + quanti] = buf[idx:idx + quanti]
            idx += quanti
            scritti += quanti
        self.indices[i] = idx
        rilascio = self.rilasci[i]
        if rilascio is not None:
            fatti, totali = rilascio
            restano = totali - fatti
            if restano <= 0:
                self._spegni(i)
                return None
            quanti = min(frames, restano)
            # Il guadagno scende linearmente da dov'era rimasto fino a zero, e
            # riprende dallo stesso punto al blocco dopo: senza la memoria di
            # quanti campioni sono gia' passati, ogni blocco ripartirebbe da
            # uno e la rampa non scenderebbe mai.
            passi = np.arange(fatti, fatti + quanti, dtype=np.float32)
            fuori[:quanti] *= 1.0 - passi / totali
            fuori[quanti:] = 0.0
            rilascio[0] = fatti + quanti
            if rilascio[0] >= totali:
                self._spegni(i)
        return fuori

    def _spegni(self, i):
        """Chiude una voce e libera il suo buffer. Con il lucchetto in mano."""
        self.buses[i] = np.zeros(0, dtype=np.float32)
        self.indices[i] = 0
        self.cicli[i] = None
        self.rilasci[i] = None

    def _audio_callback(self, outdata, frames, time, status):
        mix = np.zeros((frames, 2), dtype=np.float32)
        with self._lock:
            for i in range(self.num_strings):
                mono = self._preleva(i, frames)
                if mono is None:
                    continue
                pan = self.pans[i]
                pan_l = np.cos((pan + 1.0) * np.pi / 4.0)
                pan_r = np.sin((pan + 1.0) * np.pi / 4.0)
                mix[:, 0] += mono * pan_l
                mix[:, 1] += mono * pan_r
        np.clip(mix, -1.0, 1.0, out=mix)
        outdata[:] = mix


@atexit.register
def chiudi_giocatori():
    """Chiusura di sicurezza dei flussi audio rimasti aperti all'uscita."""
    for giocatore in list(_giocatori_aperti):
        giocatore.stop()

class NoteRenderer:
    """
    Gestisce il rendering "one-shot" di una singola nota.
    Supporta Karplus-Strong e Sintesi Additiva/Semplice.
    """
    def __init__(self, fs=FS):
        self.fs = fs
        self.freq = 0.0
        self.vol = 0.0
        self.dur = 0
        self.pan_l, self.pan_r = 0.707, 0.707
        self.adsr_list = [0, 0, 0, 0]
        self.kind = 1
        self.pluck_hardness = 0.0
        self.damping_factor = 0.0
        self.pick_position = 0.15
        self.brightness = 0.4
        self.fast_synth = FastGuitarSynth(fs=self.fs)

    def set_params(self, freq, dur, vol, pan, **kwargs):
        self.freq = freq
        self.dur = dur
        self.vol = vol
        pan_clipped = np.clip(pan, -1.0, 1.0)
        pan_angle = pan_clipped * (np.pi / 4.0)
        self.pan_l = np.cos(pan_angle + np.pi / 4.0)
        self.pan_r = np.sin(pan_angle + np.pi / 4.0)

        self.kind = 1
        self.pluck_hardness = 0.0

        if 'kind' in kwargs: # Legacy
            self.adsr_list = kwargs.get('adsr_list', [0,0,0,0])
            self.kind = kwargs.get('kind', 1)
        elif 'pluck_hardness' in kwargs: # Karplus-Strong
            self.pluck_hardness = kwargs.get('pluck_hardness', 0.5)
            self.damping_factor = kwargs.get('damping_factor', 0.996)
            self.pick_position = kwargs.get('pick_position', 0.15)
            self.brightness = kwargs.get('brightness', 0.4)

    def _render_karplus_strong(self, n_samples):
        # Utilizza il nuovo synth veloce e realistico
        dur_secs = n_samples / self.fs
        return self.fast_synth.render_string(
            self.freq, dur_secs, 1.0,
            self.pluck_hardness, self.damping_factor,
            self.pick_position, self.brightness
        )

    def _render_legacy_osc(self, n_samples):
        t = np.linspace(0., n_samples / self.fs, n_samples, endpoint=False)
        phase_vector = 2 * np.pi * self.freq * t

        if self.kind == 2: wave = signal.square(phase_vector)
        elif self.kind == 3: wave = signal.sawtooth(phase_vector, 0.5)
        elif self.kind == 4: wave = signal.sawtooth(phase_vector)
        elif self.kind == 5:
            wave = np.zeros(n_samples, dtype=np.float32)
            for i, h_amp in enumerate(HARMONICS):
                wave += np.sin((i + 1) * phase_vector) * h_amp
            max_val = np.max(np.abs(wave))
            if max_val > 0: wave /= max_val
        else: wave = np.sin(phase_vector)

        wave = wave.astype(np.float32)
        a_pct, d_pct, s_level_pct, r_pct = self.adsr_list
        attack_samples = round((a_pct / 100.0) * n_samples)
        decay_samples = round((d_pct / 100.0) * n_samples)
        release_samples = round((r_pct / 100.0) * n_samples)
        sustain_level = s_level_pct / 100.0
        sustain_samples = n_samples - (attack_samples + decay_samples + release_samples)
        if sustain_samples < 0:
            release_samples = max(0, release_samples + sustain_samples)
            sustain_samples = 0

        envelope = np.zeros(n_samples, dtype=np.float32)
        curr = 0
        if attack_samples > 0:
            envelope[curr:curr+attack_samples] = np.linspace(0., 1., attack_samples)
            curr += attack_samples
        if decay_samples > 0:
            envelope[curr:curr+decay_samples] = np.linspace(1., sustain_level, decay_samples)
            curr += decay_samples
        if sustain_samples > 0:
            envelope[curr:curr+sustain_samples] = sustain_level
            curr += sustain_samples
        if release_samples > 0:
            envelope[curr:curr+release_samples] = np.linspace(sustain_level, 0., release_samples)

        return wave * envelope

    def render(self):
        wave = self._mono()
        if wave.size == 0:
            return np.array([], dtype=np.float32)
        stereo = np.zeros((wave.size, 2), dtype=np.float32)
        stereo[:, 0] = wave * self.pan_l
        stereo[:, 1] = wave * self.pan_r
        return stereo

    def render_tenuta(self, ciclo_minimo=2048, raccordo=256):
        """La nota pronta a essere tenuta: il suono in mono e, se il suo
        inviluppo ha un mantenimento, il tratto da ripetere finche' il dito
        resta giu'.
        Restituisce la coppia (mono, ciclo), dove ciclo e' la coppia di indici
        del tratto ripetibile oppure None quando non c'e' niente da ripetere:
        la corda pizzicata decade e basta, e cosi' fa anche un inviluppo con il
        mantenimento a zero, che e' come dire che il suono finisce da solo.
        Il tratto da ripetere e' lungo un numero intero di periodi dell'onda,
        cosi' il giro cade sempre nello stesso punto della forma; l'ultimo
        pezzetto viene raccordato a cio' che precede l'inizio del tratto, cosi'
        il salto fra la fine e l'inizio non si sente. Il raccordo sta in coda e
        non in testa apposta: la prima volta che il suono entra nel tratto ci
        arriva dal decadimento, e quel passaggio deve restare intatto.
        ciclo_minimo e' la lunghezza minima in campioni del tratto ripetibile:
        piu' e' lungo, meno spesso si torna indietro. raccordo e' quanti
        campioni durano le due rampe incrociate della giunzione.
        """
        if self.pluck_hardness > 0.0:
            # Karplus-Strong: la corda decade, e ripetere un tratto del suo
            # decadimento vorrebbe dire risentire sempre lo stesso pezzo di
            # spegnimento. Tenere non allunga; lasciare, quello si', smorza.
            return self._mono(), None
        livello = self.adsr_list[2] / 100.0
        if livello <= 0.0 or self.freq <= 0.0:
            return self._mono(), None
        # Da qui in poi la nota si tiene, e il suono lungo quanto dur non
        # servira' mai: calcolarlo per poi buttarlo via sarebbero secondi di
        # sintesi fra il dito e il suono.
        n = round(self.dur * self.fs)
        attacco = round((self.adsr_list[0] / 100.0) * n)
        decadimento = round((self.adsr_list[1] / 100.0) * n)
        inizio = attacco + decadimento
        periodo = self.fs / self.freq
        giri = max(1, math.ceil(ciclo_minimo / periodo))
        lunghezza = max(2, round(giri * periodo))
        raccordo = min(raccordo, lunghezza // 2, inizio)
        # Il suono si rigenera lungo quanto serve: attacco, decadimento e poi
        # il tratto al livello di mantenimento, con la fase che continua.
        quanti = inizio + lunghezza
        onda = self._onda(quanti)
        inviluppo = np.full(quanti, livello, dtype=np.float32)
        if attacco > 0:
            inviluppo[:attacco] = np.linspace(0.0, 1.0, attacco, dtype=np.float32)
        if decadimento > 0:
            inviluppo[attacco:inizio] = np.linspace(1.0, livello, decadimento, dtype=np.float32)
        tenuto = (onda * inviluppo * self.vol).astype(np.float32)
        if raccordo > 1:
            rampa = np.linspace(0.0, 1.0, raccordo, dtype=np.float32)
            coda = slice(quanti - raccordo, quanti)
            prima = slice(inizio - raccordo, inizio)
            tenuto[coda] = tenuto[coda] * (1.0 - rampa) + tenuto[prima] * rampa
        return tenuto, (inizio, quanti)

    def _onda(self, n_samples):
        """La forma d'onda nuda, senza inviluppo e senza volume."""
        t = np.linspace(0., n_samples / self.fs, n_samples, endpoint=False)
        phase_vector = 2 * np.pi * self.freq * t
        if self.kind == 2:
            onda = signal.square(phase_vector)
        elif self.kind == 3:
            onda = signal.sawtooth(phase_vector, 0.5)
        elif self.kind == 4:
            onda = signal.sawtooth(phase_vector)
        elif self.kind == 5:
            onda = np.zeros(n_samples, dtype=np.float32)
            for i, h_amp in enumerate(HARMONICS):
                onda += np.sin((i + 1) * phase_vector) * h_amp
            massimo = np.max(np.abs(onda))
            if massimo > 0:
                onda /= massimo
        else:
            onda = np.sin(phase_vector)
        return onda.astype(np.float32)

    def _mono(self):
        """Il suono della nota in mono, cioe' quello che render mette poi nei
        due canali. Sta a parte perche' il mixer vuole il mono e ricavarlo
        dividendo per il pan costava una divisione e un cambio di tipo."""
        if self.freq <= 0.0:
            return np.array([], dtype=np.float32)
        total_note_samples = round(self.dur * self.fs)
        if total_note_samples == 0:
            return np.array([], dtype=np.float32)
        if self.pluck_hardness > 0.0:
            wave = self._render_karplus_strong(total_note_samples)
        else:
            wave = self._render_legacy_osc(total_note_samples)
        return (wave * self.vol).astype(np.float32)

def render_scale_audio(note_list, suono_params, bpm):
    s_vol = suono_params.get('volume', 0.35)
    s_dur = 60.0 / bpm

    renderer = NoteRenderer(fs=FS)
    segmenti = []

    is_ks = 'pluck_hardness' in suono_params
    if is_ks:
        hardness = suono_params.get('pluck_hardness', 0.6)
        damping = suono_params.get('damping_factor', 0.997)
        pick_pos = suono_params.get('pick_position', 0.15)
        bright = suono_params.get('brightness', 0.4)
    else:
        s_kind = suono_params.get('kind', 1)
        s_adsr = suono_params.get('adsr', [0,0,0,0])

    for item in note_list:
        freq = note_to_freq(item) if isinstance(item, str) else (float(item) if item else 0.0)
        if freq <= 0:
            segmenti.append(np.zeros((int(s_dur * FS), 2), dtype=np.float32))
            continue

        if is_ks:
            renderer.set_params(freq, s_dur, s_vol, 0.0,
                                pluck_hardness=hardness, damping_factor=damping,
                                pick_position=pick_pos, brightness=bright)
        else:
            renderer.set_params(freq, s_dur, s_vol, 0.0, kind=s_kind, adsr_list=s_adsr)

        note_audio = renderer.render()
        if note_audio.size > 0: segmenti.append(note_audio)
        else: segmenti.append(np.zeros((int(s_dur * FS), 2), dtype=np.float32))

    return np.concatenate(segmenti, axis=0) if segmenti else np.array([], dtype=np.float32)


# --- Supporto MIDI Nativo ---


MIDI_INSTRUMENTS = [
    # Piano (0-7)
    "Acoustic Grand Piano", "Bright Acoustic Piano", "Electric Grand Piano", "Honky-tonk Piano",
    "Electric Piano 1", "Electric Piano 2", "Harpsichord", "Clavi",
    # Chromatic Percussion (8-15)
    "Celesta", "Glockenspiel", "Music Box", "Vibraphone",
    "Marimba", "Xylophone", "Tubular Bells", "Dulcimer",
    # Organ (16-23)
    "Drawbar Organ", "Percussive Organ", "Rock Organ", "Church Organ",
    "Reed Organ", "Accordion", "Harmonica", "Tango Accordion",
    # Guitar (24-31)
    "Acoustic Guitar (nylon)", "Acoustic Guitar (steel)", "Electric Guitar (jazz)", "Electric Guitar (clean)",
    "Electric Guitar (muted)", "Overdriven Guitar", "Distortion Guitar", "Guitar Harmonics",
    # Bass (32-39)
    "Acoustic Bass", "Electric Bass (finger)", "Electric Bass (pick)", "Fretless Bass",
    "Slap Bass 1", "Slap Bass 2", "Synth Bass 1", "Synth Bass 2",
    # Strings (40-47)
    "Violin", "Viola", "Cello", "Contrabass",
    "Tremolo Strings", "Pizzicato Strings", "Orchestral Harp", "Timpani",
    # Ensemble (48-55)
    "String Ensemble 1", "String Ensemble 2", "SynthStrings 1", "SynthStrings 2",
    "Choir Aahs", "Voice Oohs", "Synth Voice", "Orchestra Hit",
    # Brass (56-63)
    "Trumpet", "Trombone", "Tuba", "Muted Trumpet",
    "French Horn", "Brass Section", "SynthBrass 1", "SynthBrass 2",
    # Reed (64-71)
    "Soprano Sax", "Alto Sax", "Tenor Sax", "Baritone Sax",
    "Oboe", "English Horn", "Bassoon", "Clarinet",
    # Pipe (72-79)
    "Piccolo", "Flute", "Recorder", "Pan Flute",
    "Blown Bottle", "Shakuhachi", "Whistle", "Ocarina",
    # Synth Lead (80-87)
    "Lead 1 (square)", "Lead 2 (sawtooth)", "Lead 3 (calliope)", "Lead 4 (chiff)",
    "Lead 5 (charang)", "Lead 6 (voice)", "Lead 7 (fifths)", "Lead 8 (bass+lead)",
    # Synth Pad (88-95)
    "Pad 1 (new age)", "Pad 2 (warm)", "Pad 3 (polysynth)", "Pad 4 (choir)",
    "Pad 5 (bowed)", "Pad 6 (metallic)", "Pad 7 (halo)", "Pad 8 (sweep)",
    # Synth Effects (96-103)
    "FX 1 (rain)", "FX 2 (soundtrack)", "FX 3 (crystal)", "FX 4 (atmosphere)",
    "FX 5 (brightness)", "FX 6 (goblins)", "FX 7 (echoes)", "FX 8 (sci-fi)",
    # Ethnic (104-111)
    "Sitar", "Banjo", "Shamisen", "Koto",
    "Kalimba", "Bagpipe", "Fiddle", "Shanai",
    # Percussive (112-119)
    "Tinkle Bell", "Agogo", "Steel Drums", "Woodblock",
    "Taiko Drum", "Melodic Tom", "Synth Drum", "Reverse Cymbal",
    # Sound Effects (120-127)
    "Guitar Fret Noise", "Breath Noise", "Seashore", "Bird Tweet",
    "Telephone Ring", "Helicopter", "Applause", "Gunshot"
]

# Il click dell'esercizio delle scale, quando il suono e' MIDI, suona su un
# canale melodico tutto suo con il programma Woodblock del General MIDI. Sul
# canale delle percussioni il kit GS di Windows tiene i wood block a destra e
# il pan del canale non li sposta; su un canale melodico il pan comanda.
CANALE_CLICK = 1
PROGRAMMA_WOODBLOCK = 115
# Controlli continui: pan al centro, e riverbero e chorus a zero, perche' il
# sintetizzatore GS li mette di suo su ogni canale e un click li vuole secchi.
CC_PAN = 10
CC_RIVERBERO = 91
CC_CHORUS = 93
PAN_CENTRO = 64


class WindowsMidiOut:
    """Gestore dell'output MIDI nativo di Windows tramite winmm.dll.
    Note on, note off, program change e controlli vanno di norma sul canale
    1, che nei messaggi vale 0; con canale si scrive su un altro, per esempio
    CANALE_CLICK."""
    def __init__(self):
        self.h_midi = None
        self.winmm = None
        self.active_program = -1
        self.open_port()

    def open_port(self):
        try:
            self.winmm = ctypes.windll.winmm

            # Ottimizzazione dei tipi ctypes per abbattere la latenza delle chiamate
            self.winmm.midiOutShortMsg.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
            self.winmm.midiOutShortMsg.restype = ctypes.c_uint

            HMIDIOUT = ctypes.c_void_p
            self.h_midi = HMIDIOUT()
            res = self.winmm.midiOutOpen(ctypes.byref(self.h_midi), -1, None, None, 0)
            if res != 0:
                self.h_midi = None
                print(f"\n[MIDI] Errore apertura MIDI Mapper (Codice: {res})")
        except (AttributeError, OSError) as e:
            self.h_midi = None
            print(f"\n[MIDI] Inizializzazione fallita: {e}")

    def select_instrument(self, program):
        """Lo strumento del canale 1, quello delle note: si manda solo se cambia."""
        if self.h_midi is not None and program != self.active_program:
            self.active_program = program
            self.program_change(program)

    def program_change(self, program, canale=0):
        if self.h_midi is not None:
            # Program Change: status 0xC0 piu' il canale
            msg = (program << 8) | (0xC0 | canale)
            self.winmm.midiOutShortMsg(self.h_midi, msg)

    def note_on(self, note_num, velocity=127, canale=0):
        if self.h_midi is not None and note_num is not None:
            # Note On: status 0x90 piu' il canale
            msg = (velocity << 16) | (note_num << 8) | (0x90 | canale)
            self.winmm.midiOutShortMsg(self.h_midi, msg)

    def note_off(self, note_num, canale=0):
        if self.h_midi is not None and note_num is not None:
            # Note Off: status 0x80 piu' il canale
            msg = (note_num << 8) | (0x80 | canale)
            self.winmm.midiOutShortMsg(self.h_midi, msg)

    def control_change(self, controllo, valore, canale=0):
        """Manda un controllo continuo, per esempio CC_RIVERBERO a zero."""
        if self.h_midi is not None:
            # Control Change: status 0xB0 piu' il canale
            msg = (valore << 16) | (controllo << 8) | (0xB0 | canale)
            self.winmm.midiOutShortMsg(self.h_midi, msg)

    def close_port(self):
        if self.h_midi is not None:
            # Spegne eventuali note prima della chiusura
            for n in range(128):
                self.note_off(n)
            self.winmm.midiOutClose(self.h_midi)
            self.h_midi = None

_midi_out = None

def get_midi_out():
    """Restituisce l'istanza condivisa di WindowsMidiOut."""
    global _midi_out
    if _midi_out is None:
        _midi_out = WindowsMidiOut()
        # Seleziona lo strumento impostato inizialmente per evitare overhead successivi
        try:
            import config
        except ImportError:
            return _midi_out
        _midi_out.select_instrument(config.impostazioni.get("midi_strumento", 0))
    return _midi_out

@atexit.register
def cleanup_midi():
    """Garantisce la chiusura pulita del canale MIDI all'uscita di Python."""
    global _midi_out
    if _midi_out is not None:
        _midi_out.close_port()
        _midi_out = None

def note_to_midi(note_str):
    """Converte un nome di nota in numero MIDI intero; un numero lo arrotonda;
    None per la pausa o un nome non valido. Lo scostamento microtonale si
    tronca verso lo zero, come e' sempre stato: un quarto di tono non cambia
    il tasto MIDI, tre quarti lo spostano di uno."""
    if isinstance(note_str, bool):
        return None
    if isinstance(note_str, int):
        return note_str
    if isinstance(note_str, float):
        return round(note_str)
    scomposta = scomponi_nota(note_str)
    if scomposta is None:
        return None
    midi_num, micro = scomposta
    return midi_num + int(micro)


def freq_to_midi(freq):
    """Converte una frequenza in Hz nel numero MIDI intero piu' vicino; None se non positiva."""
    if freq <= 0.0:
        return None
    return round(12 * math.log2(freq / 440.0) + 69)

def play_midi_note_temp(note_num, duration, velocity=127, canale=0):
    """Riproduce una nota MIDI per una determinata durata in secondi, sul canale indicato."""
    if note_num is None:
        return
    m_out = get_midi_out()
    m_out.note_on(note_num, velocity, canale)

    def off():
        time.sleep(duration)
        if m_out.h_midi is not None:
            m_out.note_off(note_num, canale)

    threading.Thread(target=off, daemon=True).start()


# --- Supporto MIDI IN Nativo ---

class MIDIINCAPSW(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint),
        ("szPname", ctypes.c_wchar * 32),
        ("dwSupport", ctypes.c_uint)
    ]

class MIDIINCAPSA(ctypes.Structure):
    _fields_ = [
        ("wMid", ctypes.c_ushort),
        ("wPid", ctypes.c_ushort),
        ("vDriverVersion", ctypes.c_uint),
        ("szPname", ctypes.c_char * 32),
        ("dwSupport", ctypes.c_uint)
    ]

MidiInCallbackType = ctypes.WINFUNCTYPE(
    None,
    ctypes.c_void_p,
    ctypes.c_uint,
    ctypes.c_void_p,
    ctypes.c_void_p,
    ctypes.c_void_p
)

def get_midi_in_devices():
    """Elenca i nomi dei dispositivi MIDI di input disponibili nel sistema."""
    try:
        winmm = ctypes.windll.winmm
        num_devs = winmm.midiInGetNumDevs()
        devices = []
        for i in range(num_devs):
            caps = MIDIINCAPSW()
            res = winmm.midiInGetDevCapsW(i, ctypes.byref(caps), ctypes.sizeof(caps))
            if res == 0:
                devices.append(caps.szPname)
            else:
                # fallback ANSI
                caps_a = MIDIINCAPSA()
                res_a = winmm.midiInGetDevCapsA(i, ctypes.byref(caps_a), ctypes.sizeof(caps_a))
                if res_a == 0:
                    devices.append(caps_a.szPname.decode('ansi', errors='ignore'))
        return devices
    except (AttributeError, OSError):
        return []

class WindowsMidiIn:
    """Gestore dell'input MIDI nativo di Windows tramite winmm.dll."""
    def __init__(self, device_idx, on_note_on_cb=None, on_note_off_cb=None):
        self.h_midi = None
        self.winmm = None
        self.device_idx = device_idx
        self.on_note_on = on_note_on_cb
        self.on_note_off = on_note_off_cb
        # Memorizza il callback per evitare che venga rimosso dal Garbage Collector
        self.callback_ref = MidiInCallbackType(self._midi_callback)
        self.open_port()

    def open_port(self):
        try:
            self.winmm = ctypes.windll.winmm
            HMIDIIN = ctypes.c_void_p
            self.h_midi = HMIDIIN()

            # midiInOpen(LPHMIDIIN lphmi, UINT uDeviceID, DWORD_PTR dwCallback, DWORD_PTR dwCallbackInstance, DWORD fdwOpen)
            CALLBACK_FUNCTION = 0x30000
            res = self.winmm.midiInOpen(
                ctypes.byref(self.h_midi),
                self.device_idx,
                self.callback_ref,
                None,
                CALLBACK_FUNCTION
            )
            if res != 0:
                self.h_midi = None
                print(f"\n[MIDI-IN] Errore apertura dispositivo {self.device_idx} (Codice: {res})")
                return

            res_start = self.winmm.midiInStart(self.h_midi)
            if res_start != 0:
                print(f"\n[MIDI-IN] Errore avvio acquisizione (Codice: {res_start})")
                self.close_port()
        except (AttributeError, OSError) as e:
            self.h_midi = None
            print(f"\n[MIDI-IN] Inizializzazione fallita: {e}")

    def _midi_callback(self, hmi, wMsg, dwInstance, dwParam1, dwParam2):
        # MM_MIM_DATA = 0x3C3
        if wMsg == 0x3C3:
            status = dwParam1 & 0xFF
            note_num = (dwParam1 >> 8) & 0xFF
            velocity = (dwParam1 >> 16) & 0xFF

            # Note On: status 0x90-0x9F; con velocity zero vale come Note Off
            if (status & 0xF0) == 0x90 and velocity > 0:
                if self.on_note_on:
                    self.on_note_on(note_num, velocity)
            elif (status & 0xF0) in (0x80, 0x90) and self.on_note_off:
                self.on_note_off(note_num)

    def close_port(self):
        if self.h_midi is not None:
            try:
                self.winmm.midiInStop(self.h_midi)
                self.winmm.midiInReset(self.h_midi)
                self.winmm.midiInClose(self.h_midi)
            except (AttributeError, OSError):
                # In chiusura non resta niente da fare se il driver non risponde.
                pass
            self.h_midi = None

_midi_in = None

def get_midi_in():
    """Restituisce l'istanza di input MIDI attiva."""
    return _midi_in

def on_midi_in_note_on(note_num, velocity):
    """Callback di default per Note On da tastiera MIDI."""
    try:
        import config
        tipo_suono = config.impostazioni.get('tipo_suono', 'suono_1')
        if tipo_suono == 'midi':
            get_midi_out().note_on(note_num, velocity)
        else:
            freq = midi_to_freq(note_num)
            suono = config.impostazioni[tipo_suono]
            dur = suono.get('dur_accordi', 2.0)
            vol = suono.get('volume', 0.35)
            renderer = NoteRenderer(fs=FS)
            if 'pluck_hardness' in suono:
                renderer.set_params(freq, dur, vol, 0.0,
                                    pluck_hardness=suono.get('pluck_hardness', 0.6),
                                    damping_factor=suono.get('damping_factor', 0.997))
            else:
                renderer.set_params(freq, dur, vol, 0.0, kind=suono.get('kind', 1), adsr_list=suono.get('adsr', [0, 0, 0, 0]))
            note_audio = renderer.render()
            if note_audio.size > 0:
                sd.play(note_audio, samplerate=FS, blocking=False)
    except Exception as e:  # noqa: BLE001 - callback di winmm: un errore qui non ha nessuno a cui risalire
        print(f"Nota MIDI non riprodotta: {e}")


def on_midi_in_note_off(note_num):
    """Callback di default per Note Off da tastiera MIDI."""
    try:
        import config
        if config.impostazioni.get('tipo_suono', 'suono_1') == 'midi':
            get_midi_out().note_off(note_num)
    except Exception as e:  # noqa: BLE001 - callback di winmm: un errore qui non ha nessuno a cui risalire
        print(f"Nota MIDI non spenta: {e}")

def open_global_midi_in(device_idx):
    """Apre la connessione globale al dispositivo MIDI In indicato."""
    global _midi_in
    close_global_midi_in()
    if device_idx >= 0:
        _midi_in = WindowsMidiIn(device_idx, on_midi_in_note_on, on_midi_in_note_off)

@atexit.register
def close_global_midi_in():
    """Chiude in modo sicuro la connessione globale del MIDI In."""
    global _midi_in
    if _midi_in is not None:
        _midi_in.close_port()
        _midi_in = None
