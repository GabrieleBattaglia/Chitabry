# Chitabry, accordatore: rileva la nota fondamentale dal microfono per autocorrelazione.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.

import math
import threading
import time

import numpy as np
import sounddevice as sd
from GBUtils import enter_escape, key, menu

import config
from nomenclatura import get_nota

BLOCK_SIZE = 4096
RMS_THRESHOLD = 0.002
# Autocorrelazione: soglia per il primo picco significativo
AUTOCORR_THRESHOLD = 0.5
# Media mobile esponenziale sulla frequenza mostrata, per un display stabile
EMA_ALPHA = 0.4
SECONDI_RILEVAMENTO = 5.0
ERRORI_AUDIO = (sd.PortAudioError, ValueError, OSError)


def _midi_to_note_std(midi_num):
    """Da numero MIDI a nome standard, per esempio C#4, senza passare da music21
    dentro il ciclo dell'accordatore."""
    return f"{config.NOTE_STD[int(midi_num) % 12]}{(int(midi_num) // 12) - 1}"


def _parabolic_interp(data, peak_idx):
    """Interpolazione parabolica per raffinare la posizione del picco."""
    if peak_idx <= 0 or peak_idx >= len(data) - 1:
        return float(peak_idx)
    alpha = data[peak_idx - 1]
    beta = data[peak_idx]
    gamma = data[peak_idx + 1]
    denom = alpha - 2.0 * beta + gamma
    if abs(denom) < 1e-12:
        return float(peak_idx)
    return peak_idx + 0.5 * (alpha - gamma) / denom


def _detect_pitch_autocorr(mono, sr):
    """Frequenza fondamentale per autocorrelazione normalizzata (McLeod semplificato).
    Immune agli errori d'ottava: cerca la periodicita', non il picco spettrale."""
    N = len(mono)
    # Limiti di lag: 2000 Hz al minimo, 50 Hz al massimo
    min_lag = max(2, int(sr / 2000))
    max_lag = min(N // 2, int(sr / 50))
    if min_lag >= max_lag:
        return 0.0
    windowed = mono * np.hanning(N)
    fft_size = 1
    while fft_size < 2 * N:
        fft_size *= 2
    fft_x = np.fft.rfft(windowed, n=fft_size)
    autocorr = np.fft.irfft(fft_x * np.conj(fft_x))[:N]
    if autocorr[0] < 1e-10:
        return 0.0
    autocorr_norm = autocorr / autocorr[0]
    region = autocorr_norm[min_lag:max_lag]
    if len(region) < 3:
        return 0.0
    # Il primo punto sotto la soglia, poi il primo picco sopra
    below = np.where(region < AUTOCORR_THRESHOLD)[0]
    if len(below) == 0:
        return 0.0
    search_start = below[0]
    remaining = region[search_start:]
    if len(remaining) < 3:
        return 0.0
    above = np.where(remaining > AUTOCORR_THRESHOLD)[0]
    if len(above) == 0:
        return 0.0
    peak_region_start = search_start + above[0]
    peak_end = peak_region_start
    while peak_end < len(region) - 1 and region[peak_end] > AUTOCORR_THRESHOLD:
        peak_end += 1
    local_peak = peak_region_start + int(np.argmax(region[peak_region_start:peak_end + 1]))
    refined_lag = _parabolic_interp(autocorr_norm, local_peak + min_lag)
    if refined_lag <= 0:
        return 0.0
    return sr / refined_lag


def _misura_rumore(device_idx, secondi=SECONDI_RILEVAMENTO):
    """Ascolta il dispositivo per qualche secondo e restituisce il picco RMS.
    Solleva uno degli ERRORI_AUDIO se il dispositivo non si apre."""
    dev_info = sd.query_devices(device_idx, 'input')
    sr = int(dev_info['default_samplerate'])
    max_rms = [0.0]

    def callback(indata, frames, time_info, status):
        rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        max_rms[0] = max(max_rms[0], rms)

    with sd.InputStream(device=device_idx, samplerate=sr, channels=1, blocksize=BLOCK_SIZE, dtype='float32', callback=callback):
        time.sleep(secondi)
    return max_rms[0]


def _dispositivi_di_ingresso():
    """Dizionario indice -> nome dei dispositivi con almeno un canale di ingresso."""
    input_devices = {}
    for idx, dev in enumerate(sd.query_devices()):
        if dev['max_input_channels'] > 0:
            try:
                api_name = sd.query_hostapis(dev['hostapi'])['name']
            except (sd.PortAudioError, ValueError, IndexError, KeyError):
                api_name = "Sconosciuto"
            input_devices[str(idx)] = f"{dev['name']} [{api_name}]"
    return input_devices


def _rileva_dispositivi_attivi(input_devices):
    """Ascolta tutti i dispositivi insieme e tiene quelli con segnale.
    Chi non si apre in parallelo si riprova in serie. Se nessuno ha segnale
    si restituiscono tutti."""
    print("Rilevamento automatico in corso...")
    print(f"Ascolto di tutte le periferiche per {SECONDI_RILEVAMENTO:.0f} secondi...")
    results = {}
    failed_parallel = []
    lock = threading.Lock()

    def test_device(device_idx):
        try:
            rumore = _misura_rumore(device_idx)
        except ERRORI_AUDIO:
            with lock:
                failed_parallel.append(device_idx)
            return
        with lock:
            results[device_idx] = rumore

    threads = [threading.Thread(target=test_device, args=(int(idx_str),)) for idx_str in input_devices]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for idx in failed_parallel:
        try:
            results[idx] = _misura_rumore(idx)
        except ERRORI_AUDIO:
            results[idx] = 0.0
    filtered = {}
    for idx_str, name in input_devices.items():
        rms_val = results.get(int(idx_str), 0.0)
        if rms_val >= RMS_THRESHOLD:
            filtered[idx_str] = f"{name} (Rumore: {rms_val:.4f})"
    if not filtered:
        print(f"Nessun segnale significativo rilevato (sotto {RMS_THRESHOLD} RMS). Vengono mostrati tutti i dispositivi.")
        return input_devices
    return filtered


def _riepilogo(all_midi, all_freqs, all_dbs):
    """Note, frequenze e volumi ascoltati: minimo, mediana e massimo, scartando gli estremi."""
    if len(all_midi) >= 3:
        all_midi, all_freqs, all_dbs = sorted(all_midi)[1:-1], sorted(all_freqs)[1:-1], sorted(all_dbs)[1:-1]
    nota_min = get_nota(_midi_to_note_std(min(all_midi)))
    nota_max = get_nota(_midi_to_note_std(max(all_midi)))
    nota_med = get_nota(_midi_to_note_std(round(float(np.median(all_midi)))))
    print(f"Note ascoltate: {nota_min} ({nota_med}) {nota_max}")
    print(f"Frequenze (Hz): {min(all_freqs):.1f} ({np.median(all_freqs):.1f}) {max(all_freqs):.1f}")
    print(f"Volumi (dB): {min(all_dbs):.0f} ({np.median(all_dbs):.0f}) {max(all_dbs):.0f}")


def Accordatore():
    """Accordatore cromatico: rileva la nota fondamentale dal microfono e la
    mostra ogni secondo con lo scarto in centesimi, su una riga da 40 caratteri."""
    input_devices = _dispositivi_di_ingresso()
    if not input_devices:
        print("Errore: Nessun dispositivo di input audio (microfono) trovato.")
        key("Premi un tasto per continuare...")
        return
    if enter_escape("Desideri il rilevamento automatico della periferica di input attiva? (INVIO per si', ESC per no): "):
        filtered_devices = _rileva_dispositivi_attivi(input_devices)
    else:
        filtered_devices = input_devices
    print("Dispositivi di input disponibili.")
    scelta_device = menu(d=filtered_devices, p="Seleziona il dispositivo di input: ", show=True, numbered=True)
    if scelta_device is None:
        return
    device_idx = int(scelta_device)
    device_sr = int(sd.query_devices(device_idx, 'input')['default_samplerate'])
    pitch_readings = []
    current_rms = [0.0]
    pitch_lock = threading.Lock()
    stop_event = threading.Event()
    ema_state = {'freq': 0.0, 'active': False}

    def _audio_callback(indata, frames, time_info, status):
        if stop_event.is_set():
            raise sd.CallbackAbort
        mono = indata[:, 0]
        rms = float(np.sqrt(np.mean(mono ** 2)))
        current_rms[0] = rms
        if rms < RMS_THRESHOLD:
            return
        detected_freq = _detect_pitch_autocorr(mono, device_sr)
        if detected_freq > 0.0:
            with pitch_lock:
                pitch_readings.append(detected_freq)

    print("Accordatore cromatico.")
    print("ESC per uscire.")
    try:
        stream = sd.InputStream(device=device_idx, samplerate=device_sr, channels=1, blocksize=BLOCK_SIZE, dtype='float32', callback=_audio_callback)
        stream.start()
    except ERRORI_AUDIO as e:
        print(f"Errore apertura audio: {e}")
        key("Premi un tasto...")
        return
    last_print_time = 0
    last_nota = ""
    last_cents = 0.0
    last_freq = 0.0
    all_midi, all_freqs, all_dbs = [], [], []
    try:
        while True:
            ch = key(attesa=0.05)
            if ch == '\x1b':
                break
            current_time = time.time()
            if current_time - last_print_time < 1.0:
                continue
            with pitch_lock:
                readings = pitch_readings.copy()
                pitch_readings.clear()
            rms = current_rms[0]
            db_val = 20 * math.log10(rms / 1e-5) if rms > 1e-5 else 0.0
            above_threshold = rms >= RMS_THRESHOLD
            if rms > 1e-6:
                all_dbs.append(db_val)
            # La media mobile lega la lettura a quella del secondo prima, solo
            # se anche quella era valida: al primo suono si riparte da zero.
            valida = False
            if readings and above_threshold:
                avg_freq = float(np.median(readings))
                if 30.0 <= avg_freq <= 2000.0:
                    valida = True
                    if ema_state['active']:
                        avg_freq = EMA_ALPHA * avg_freq + (1 - EMA_ALPHA) * ema_state['freq']
                    ema_state['freq'] = avg_freq
                    midi_num = 69 + 12 * math.log2(avg_freq / 440.0)
                    target_midi = round(midi_num)
                    last_cents = (midi_num - target_midi) * 100
                    last_nota = get_nota(_midi_to_note_std(target_midi))
                    last_freq = avg_freq
                    all_midi.append(target_midi)
                    all_freqs.append(avg_freq)
            ema_state['active'] = valida
            if last_nota:
                segno = "+" if last_cents >= 0 else ""
                cents_str = f"{segno}{last_cents:.0f}%"
                hz_str = f"{last_freq:.1f}"
                nota_str = last_nota
            else:
                cents_str = "0%"
                hz_str = "0.0"
                nota_str = "nessuna"
            db_str = f"dB:{db_val:.0f}"
            db_formatted = f"[{db_str}]" if above_threshold else f"<{db_str}>"
            line = f"N:{nota_str} ({cents_str}) Hz:{hz_str} {db_formatted}"
            print(f"\r{line:<40}\r", end="", flush=True)
            last_print_time = current_time
    finally:
        stop_event.set()
        stream.stop()
        stream.close()
        print("\nAccordatore chiuso.")
        if all_midi and all_freqs and all_dbs:
            _riepilogo(all_midi, all_freqs, all_dbs)
