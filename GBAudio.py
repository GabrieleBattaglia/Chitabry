# GBAudio.py
# Motore Audio Condiviso per i progetti di Gabriele Battaglia
# Contiene la sintesi sonora, il rendering e le utility per la gestione delle frequenze.
# Data creazione: 6 gennaio 2026

import atexit
import ctypes
import re
import threading
import time
import numpy as np
import sounddevice as sd
from scipy import signal

# --- Costanti Globali ---
FS = 44100  # Aumentata frequenza di campionamento per KS
BLOCK_SIZE = 256
HARMONICS = [1, 0.5, 0.33, 0.25, 0.2, 0.17, 0.14, 0.125, 0.11, 0.1, 0.09, 0.08, 0.07]

def note_to_freq(note):
    """Converte la notazione (es. "C4", "F~5", "B`5") in frequenza (Hz)."""
    if isinstance(note, (int, float)): return float(note)
    if isinstance(note, str):
        note_lower = note.lower()
        if note_lower == 'p': return 0.0 # Pausa
        note_lower = note_lower.replace('-', 'b')
        
        # Estrai l'ottava (cifre finali)
        match_octave = re.search(r"\d+$", note_lower)
        if not match_octave:
            return 0.0
        octave_str = match_octave.group()
        try:
            octave = int(octave_str)
        except ValueError:
            return 0.0
            
        # Rimuovi l'ottava per ottenere la nota e le alterazioni
        note_base = note_lower[:-len(octave_str)]
        
        # Estrai i simboli microtonali alla fine di note_base
        micro_offset = 0.0
        # Ordina dal più lungo al più corto per evitare match parziali
        possible_micros = [("~~", 1.5), ("``", -1.5), ("~", 0.5), ("`", -0.5)]
        for micro, offset in possible_micros:
            if note_base.endswith(micro):
                micro_offset = offset
                note_base = note_base[:-len(micro)]
                break
                
        # Ora note_base contiene solo la nota e le alterazioni standard (es. "c", "c#", "eb")
        match_std = re.match(r"^([a-g])([#b]?)$", note_base)
        if not match_std:
            return 0.0
        note_letter, accidental = match_std.groups()
        
        note_base_semitones = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        semitone = note_base_semitones[note_letter]
        if accidental == '#':
            semitone += 1
        elif accidental == 'b':
            semitone -= 1
            
        midi_num = 12 + semitone + 12 * octave + micro_offset
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
        
        self.is_running = False

        self.stream = sd.OutputStream(
            samplerate=self.fs, channels=2, dtype=np.float32,
            callback=self._audio_callback, latency='low'
        )

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
            self.buses[string_idx] = audio_mono
            self.indices[string_idx] = 0

    def mute(self, string_idx=None):
        """Silenzia una corda specifica o tutte."""
        if string_idx is None:
            for i in range(self.num_strings):
                self.buses[i] = np.zeros(0, dtype=np.float32)
                self.indices[i] = 0
        elif 0 <= string_idx < self.num_strings:
            self.buses[string_idx] = np.zeros(0, dtype=np.float32)
            self.indices[string_idx] = 0

    def _audio_callback(self, outdata, frames, time, status):
        mix = np.zeros((frames, 2), dtype=np.float32)
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

class WindowsMidiOut:
    """Gestore dell'output MIDI nativo di Windows tramite winmm.dll."""
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
        except Exception as e:
            self.h_midi = None
            print(f"\n[MIDI] Inizializzazione fallita: {e}")

    def select_instrument(self, program):
        if self.h_midi is not None and program != self.active_program:
            self.active_program = program
            # Program Change: status 0xC0 (channel 0)
            msg = (program << 8) | 0xC0
            self.winmm.midiOutShortMsg(self.h_midi, msg)

    def note_on(self, note_num, velocity=127):
        if self.h_midi is not None and note_num is not None:
            # Note On: status 0x90 (channel 0)
            msg = (velocity << 16) | (note_num << 8) | 0x90
            self.winmm.midiOutShortMsg(self.h_midi, msg)

    def note_off(self, note_num):
        if self.h_midi is not None and note_num is not None:
            # Note Off: status 0x80 (channel 0)
            msg = (note_num << 8) | 0x80
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
            program = config.impostazioni.get("midi_strumento", 0)
            _midi_out.select_instrument(program)
        except Exception:
            pass
    return _midi_out

@atexit.register
def cleanup_midi():
    """Garantisce la chiusura pulita del canale MIDI all'uscita di Python."""
    global _midi_out
    if _midi_out is not None:
        _midi_out.close_port()
        _midi_out = None

def note_to_midi(note_str):
    """Converte un nome di nota standard (es. 'C4', 'F#3') in un numero MIDI (0-127)."""
    if isinstance(note_str, int): return note_str
    if isinstance(note_str, float): return int(round(note_str))
    if isinstance(note_str, str):
        note_lower = note_str.lower()
        if note_lower == 'p': return None
        note_lower = note_lower.replace('-', 'b')
        
        match_octave = re.search(r"\d+$", note_lower)
        if not match_octave:
            return None
        octave_str = match_octave.group()
        try:
            octave = int(octave_str)
        except ValueError:
            return None
            
        note_base = note_lower[:-len(octave_str)]
        
        micro_offset = 0
        possible_micros = [("~~", 1), ("``", -1), ("~", 0), ("`", 0)]
        for micro, offset in possible_micros:
            if note_base.endswith(micro):
                micro_offset = offset
                note_base = note_base[:-len(micro)]
                break
                
        match_std = re.match(r"^([a-g])([#b]?)$", note_base)
        if not match_std:
            return None
        note_letter, accidental = match_std.groups()
        
        note_base_semitones = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}
        semitone = note_base_semitones[note_letter]
        if accidental == '#':
            semitone += 1
        elif accidental == 'b':
            semitone -= 1
            
        midi_num = 12 + semitone + 12 * octave + micro_offset
        return int(round(midi_num))
    return None

def freq_to_midi(freq):
    """Converte una frequenza Hz in numero MIDI standard (0-127)."""
    if freq <= 0.0: return None
    return int(round(12 * np.log2(freq / 440.0) + 69))

def play_midi_note_temp(note_num, duration, velocity=127):
    """Riproduce una nota MIDI per una determinata durata in secondi."""
    if note_num is None: return
    try:
        m_out = get_midi_out()
        m_out.note_on(note_num, velocity)
        
        def off():
            time.sleep(duration)
            if m_out.h_midi is not None:
                m_out.note_off(note_num)
                
        threading.Thread(target=off, daemon=True).start()
    except Exception as e:
        print(f"\n[MIDI] Errore riproduzione nota {note_num}: {e}")