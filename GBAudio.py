# GBAudio.py
# Motore Audio Condiviso per i progetti di Gabriele Battaglia
# Contiene la sintesi sonora, il rendering e le utility per la gestione delle frequenze.
# Data creazione: 6 gennaio 2026

import numpy as np
import sounddevice as sd
from scipy import signal
from collections import deque
import re

# --- Costanti Globali ---
FS = 22050  # Frequenza di campionamento (Hz)
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

def _generate_harmonic_pluck(buffer_length_N, pluck_hardness_float):
    """Genera un "pluck" di eccitazione ibrido."""
    N = buffer_length_N
    t = np.linspace(0., 1., N, endpoint=False)
    base_amplitudes = np.array([1.00, 0.15, 0.34, 0.30, 0.09, 0.03, 0.08, 0.03, 0.06, 0.04])
    roll_off_strength = 1.0 - pluck_hardness_float 
    n = np.arange(0, len(base_amplitudes))
    hardness_scalar = np.power(roll_off_strength, n)
    amplitudes = base_amplitudes * hardness_scalar
    waveform = np.zeros(N, dtype=np.float32)
    for i in range(len(amplitudes)):
        if amplitudes[i] > 0.001:
            phase = 2 * np.pi * (i + 1) * t
            waveform += amplitudes[i] * np.sin(phase)
    waveform -= np.mean(waveform)
    max_val = np.max(np.abs(waveform))
    if max_val > 0: waveform /= max_val
    return waveform

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
        self.kind = 0
        self.pluck_hardness = 0.0
        self.damping_factor = 0.0

    def set_params(self, freq, dur, vol, pan, **kwargs):
        self.freq = freq
        self.dur = dur
        self.vol = vol
        pan_clipped = np.clip(pan, -1.0, 1.0)
        pan_angle = pan_clipped * (np.pi / 4.0)
        self.pan_l = np.cos(pan_angle + np.pi / 4.0)
        self.pan_r = np.sin(pan_angle + np.pi / 4.0)
        
        self.kind = 0
        self.pluck_hardness = 0.0
        
        if 'kind' in kwargs: # Legacy
            self.adsr_list = kwargs.get('adsr_list', [0,0,0,0])
            self.kind = kwargs.get('kind', 1)
        elif 'pluck_hardness' in kwargs: # Karplus-Strong
            self.pluck_hardness = kwargs.get('pluck_hardness', 0.5)
            self.damping_factor = kwargs.get('damping_factor', 0.996)
        else:
            self.kind = 1 

    def _render_karplus_strong(self, n_samples):
        N = int(self.fs / self.freq)
        if N <= 1: return np.zeros(n_samples, dtype=np.float32)
        pluck = _generate_harmonic_pluck(N, self.pluck_hardness)
        buf = deque(pluck)
        samples = np.zeros(n_samples, dtype=np.float32)
        for i in range(n_samples):
            samples[i] = buf[0]
            avg = self.damping_factor * 0.5 * (buf[0] + buf[1])
            buf.append(avg)
            buf.popleft()
        return samples

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
    s_kind = suono_params['kind']
    s_adsr = suono_params['adsr']
    s_vol = suono_params['volume']
    s_dur = 60.0 / bpm
    
    renderer = NoteRenderer(fs=FS)
    segmenti = []

    for item in note_list:
        freq = note_to_freq(item) if isinstance(item, str) else (float(item) if item else 0.0)
        if freq <= 0:
            segmenti.append(np.zeros((int(s_dur * FS), 2), dtype=np.float32))
            continue
            
        renderer.set_params(freq, s_dur, s_vol, 0.0, kind=s_kind, adsr_list=s_adsr)
        note_audio = renderer.render()
        if note_audio.size > 0: segmenti.append(note_audio)
        else: segmenti.append(np.zeros((int(s_dur * FS), 2), dtype=np.float32))

    return np.concatenate(segmenti, axis=0) if segmenti else np.array([], dtype=np.float32)