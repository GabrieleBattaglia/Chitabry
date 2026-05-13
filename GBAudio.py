# GBAudio.py
# Motore Audio Condiviso per i progetti di Gabriele Battaglia
# Contiene la sintesi sonora, il rendering e le utility per la gestione delle frequenze.
# Data creazione: 6 gennaio 2026

import numpy as np
from scipy import signal
from collections import deque
import re
import sounddevice as sd
import threading

# --- Costanti Globali ---
FS = 44100  # Aumentata frequenza di campionamento per KS
BLOCK_SIZE = 256
HARMONICS = [1, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.125, 0.11, 0.1, 0.09, 0.08, 0.07]

def note_to_freq(note):
    """Converte la notazione (es. "C4") in frequenza (Hz)."""
    if isinstance(note, (int, float)): return float(note)
    if isinstance(note, str):
        note_lower = note.lower()
        if note_lower == 'p': return 0.0 # Pausa
        note_lower = note_lower.replace('-', 'b')
        match = re.match(r"^([a-g])([#b]?)(\d)$", note_lower)
        if not match: return 0.0
        note_letter, accidental, octave_str = match.groups()
        try: octave = int(octave_str)
        except ValueError: return 0.0
        note_base = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        semitone = note_base[note_letter]
        if accidental == '#': semitone += 1
        elif accidental == 'b': semitone -= 1
        midi_num = 12 + semitone + 12 * octave
        freq = 440.0 * (2.0 ** ((midi_num - 69) / 12.0))
        return freq
    return 0.0

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
        x[:L] = excitation
        
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

class PolyphonicPlayer:
    """
    Motore di stream continuo. Mixa N canali (bus) indipendenti in real-time.
    Se una corda viene ri-suonata, il suo buffer si azzera e riparte,
    mentre le altre corde continuano a suonare.
    """
    def __init__(self, fs=FS, num_strings=6):
        self.fs = fs
        self.num_strings = num_strings
        self.buses = [np.zeros(0, dtype=np.float32) for _ in range(num_strings)]
        self.indices = [0 for _ in range(num_strings)]
        
        # Panning base (modificabile via set_pan)
        self.pans = np.zeros(num_strings, dtype=np.float32)
        
        self.lock = threading.Lock()
        self.stream = sd.OutputStream(
            samplerate=self.fs, channels=2, dtype=np.float32,
            callback=self._audio_callback, latency='low'
        )
        self.is_running = False

    def start(self):
        if not self.is_running:
            self.stream.start()
            self.is_running = True

    def stop(self):
        if self.is_running:
            self.stream.stop()
            self.is_running = False

    def set_pan(self, string_idx, pan_value):
        if 0 <= string_idx < self.num_strings:
            self.pans[string_idx] = np.clip(pan_value, -1.0, 1.0)

    def pluck(self, string_idx, audio_mono):
        """Suona una corda. Sostituisce il suo bus interrompendone il suono precedente."""
        if 0 <= string_idx < self.num_strings:
            with self.lock:
                self.buses[string_idx] = audio_mono
                self.indices[string_idx] = 0

    def mute(self, string_idx=None):
        """Silenzia una corda specifica o tutte."""
        with self.lock:
            if string_idx is None:
                for i in range(self.num_strings):
                    self.buses[i] = np.zeros(0, dtype=np.float32)
                    self.indices[i] = 0
            elif 0 <= string_idx < self.num_strings:
                self.buses[string_idx] = np.zeros(0, dtype=np.float32)
                self.indices[string_idx] = 0

    def _audio_callback(self, outdata, frames, time, status):
        mix = np.zeros((frames, 2), dtype=np.float32)
        
        with self.lock:
            for i in range(self.num_strings):
                buf = self.buses[i]
                idx = self.indices[i]
                buf_len = len(buf)
                
                if idx < buf_len:
                    remaining = buf_len - idx
                    chunk_len = min(frames, remaining)
                    
                    pan = self.pans[i]
                    pan_l = np.cos((pan + 1.0) * np.pi / 4.0)
                    pan_r = np.sin((pan + 1.0) * np.pi / 4.0)
                    
                    mono_chunk = buf[idx : idx + chunk_len]
                    
                    mix[:chunk_len, 0] += mono_chunk * pan_l
                    mix[:chunk_len, 1] += mono_chunk * pan_r
                    
                    self.indices[i] += chunk_len
                    
        # Hard limiter per evitare clipping polifonico
        mix = np.clip(mix, -1.0, 1.0)
        outdata[:] = mix

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
        attack_samples = int(round((a_pct/100.0)*n_samples))
        decay_samples = int(round((d_pct/100.0)*n_samples))
        release_samples = int(round((r_pct/100.0)*n_samples))
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
        if self.freq <= 0.0: return np.array([], dtype=np.float32)
        total_note_samples = int(round(self.dur * self.fs))
        if total_note_samples == 0: return np.array([], dtype=np.float32)
        
        if self.pluck_hardness > 0.0:
            wave = self._render_karplus_strong(total_note_samples)
        else:
            wave = self._render_legacy_osc(total_note_samples)
            
        wave *= self.vol
        stereo = np.zeros((total_note_samples, 2), dtype=np.float32)
        stereo[:, 0] = wave * self.pan_l
        stereo[:, 1] = wave * self.pan_r
        return stereo

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