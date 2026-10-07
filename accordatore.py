# Chitabry, accordatore: rileva la nota fondamentale dal microfono con YIN.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.
# Dalla 9.7.0, dopo il collaudo di Gabriele del 7 ottobre 2026: YIN al posto
# dell'autocorrelazione, da 27,5 a 4500 Hz invece che da 50 a 2000, la media
# fra un secondo e l'altro solo se la nota non e' cambiata, una riga che
# dice cosa succede mentre si ascoltano le periferiche, e la piu' forte
# proposta per prima.

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
# YIN: il primo minimo della differenza normalizzata sotto la soglia da' il
# periodo; se nessuno ci scende, sotto quella di ripiego. Misurato su toni
# sintetici dal MI1 al LA7, puliti e con rumore: con 0,15 nessun errore
# d'ottava, dove l'autocorrelazione di prima ne faceva dall'uno al cinque per
# cento nel registro centrale e li sbagliava tutti sopra i 1900 Hz.
SOGLIA_YIN = 0.15
SOGLIA_RIPIEGO = 0.35
# L'estensione: dal LA0 del pianoforte, che tiene dentro il SI0 del basso a
# cinque corde, 31 Hz, alla cima delle armoniche acute,
# come il FA#7 di un'armonica in FA#. Fino alla 9.6 era da 50 a 2000 Hz, e il
# foro 10 soffiato di un'armonica in DO, un DO7 a 2093 Hz, si leggeva
# un'ottava sotto.
FREQUENZA_MINIMA = 27.5
FREQUENZA_MASSIMA = 4500.0
# Media mobile esponenziale sulla frequenza mostrata, per un display stabile,
# ma solo fra due secondi che danno la stessa nota: entro trenta centesimi.
# Fino alla 9.6 mescolava anche una nota nuova con la vecchia, e passando da
# DO4 a RE4 la riga diceva DO#4 per due secondi.
EMA_ALPHA = 0.4
CENTESIMI_STESSA_NOTA = 30.0
# Ogni quanto si aggiorna la riga mentre si ascoltano le periferiche
AGGIORNAMENTO_RILEVAMENTO = 0.5
SECONDI_RILEVAMENTO = 5.0
ERRORI_AUDIO = (sd.PortAudioError, ValueError, OSError)


def _midi_to_note_std(midi_num):
    """Da numero MIDI a nome standard, per esempio C#4, senza passare da music21
    dentro il ciclo dell'accordatore."""
    return f"{config.NOTE_STD[int(midi_num) % 12]}{(int(midi_num) // 12) - 1}"


def rileva_frequenza(mono, sr):
    """Frequenza fondamentale di un blocco con YIN, di de Cheveigne' e
    Kawahara: la differenza quadratica fra il segnale e se stesso spostato,
    normalizzata con la sua media cumulata, ha un minimo al periodo, e il
    primo minimo sotto la soglia evita gli errori d'ottava che il picco piu'
    alto dell'autocorrelazione commette. La parabola sulla differenza grezza
    raffina il periodo fra due campioni: nelle note acute, dove un periodo e'
    di venti campioni, porta l'ancia da quaranta a novanta letture su cento
    entro cinque centesimi. Restituisce 0.0 se il blocco non ha una nota."""
    n = len(mono)
    tau_min = max(2, int(sr / FREQUENZA_MASSIMA))
    tau_max = min(n // 2, int(sr / FREQUENZA_MINIMA))
    if tau_min + 2 >= tau_max:
        return 0.0
    x = np.asarray(mono, dtype=np.float64)
    x = x - np.mean(x)
    finestra = n - tau_max
    fft_size = 1
    while fft_size < 2 * n:
        fft_size *= 2
    # La differenza d(tau) con la FFT: energia della finestra, piu' energia
    # della finestra spostata, meno due volte la correlazione incrociata
    correlazione = np.fft.irfft(np.fft.rfft(x, fft_size) * np.conj(np.fft.rfft(x[:finestra], fft_size)))[:tau_max + 1]
    energia = np.concatenate(([0.0], np.cumsum(x ** 2)))
    taus = np.arange(tau_max + 1)
    d = energia[finestra] + (energia[taus + finestra] - energia[taus]) - 2.0 * correlazione
    d[0] = 0.0
    if energia[finestra] < 1e-12:
        return 0.0
    normalizzata = np.ones_like(d)
    cumulata = np.cumsum(d[1:])
    normalizzata[1:] = d[1:] * taus[1:] / np.where(cumulata == 0, 1.0, cumulata)
    tau = None
    for soglia in (SOGLIA_YIN, SOGLIA_RIPIEGO):
        sotto = np.nonzero(normalizzata[tau_min:tau_max] < soglia)[0]
        if len(sotto):
            tau = tau_min + int(sotto[0])
            # Si scende fino al fondo della valle
            while tau + 1 < tau_max and normalizzata[tau + 1] < normalizzata[tau]:
                tau += 1
            break
    if tau is None or tau < 1 or tau + 1 > tau_max:
        return 0.0
    a, b, c = d[tau - 1], d[tau], d[tau + 1]
    curvatura = a - 2.0 * b + c
    periodo = tau + 0.5 * (a - c) / curvatura if curvatura > 1e-12 else float(tau)
    if periodo <= 0:
        return 0.0
    return sr / periodo


def frequenza_da_mostrare(letture, precedente=None):
    """La frequenza della riga di questo secondo: la mediana delle letture
    dei blocchi, che toglie le letture sbagliate isolate, mediata con quella
    del secondo prima solo se da' la stessa nota, entro trenta centesimi.
    precedente e' la frequenza mostrata il secondo prima, o None.
    Restituisce None se le letture non danno una nota nell'estensione."""
    if not letture:
        return None
    mediana = float(np.median(letture))
    if not FREQUENZA_MINIMA <= mediana <= FREQUENZA_MASSIMA:
        return None
    if precedente and abs(1200 * math.log2(mediana / precedente)) <= CENTESIMI_STESSA_NOTA:
        return EMA_ALPHA * mediana + (1 - EMA_ALPHA) * precedente
    return mediana


def decibel(rms):
    """Il volume nella scala della riga dell'accordatore: zero a 1e-5 di RMS."""
    return 20 * math.log10(rms / 1e-5) if rms > 1e-5 else 0.0


def _misura_rumore(device_idx, secondi=SECONDI_RILEVAMENTO, livelli=None):
    """Ascolta il dispositivo per qualche secondo e restituisce il picco RMS.
    Se livelli e' un dizionario, ci scrive il picco fin li' sotto l'indice
    del dispositivo, per chi mostra l'avanzamento.
    Solleva uno degli ERRORI_AUDIO se il dispositivo non si apre."""
    dev_info = sd.query_devices(device_idx, 'input')
    sr = int(dev_info['default_samplerate'])
    max_rms = [0.0]

    def callback(indata, frames, time_info, status):
        rms = float(np.sqrt(np.mean(indata[:, 0] ** 2)))
        max_rms[0] = max(max_rms[0], rms)
        if livelli is not None:
            livelli[device_idx] = max_rms[0]

    with sd.InputStream(device=device_idx, samplerate=sr, channels=1, blocksize=BLOCK_SIZE, dtype='float32', callback=callback):
        time.sleep(secondi)
    return max_rms[0]


def _riga_di_ascolto(inizio, livelli, prefisso="Ascolto"):
    """La riga che si riscrive mentre si ascoltano le periferiche, entro i
    quaranta caratteri del display braille: i secondi passati e il volume
    piu' forte sentito fin li'. Fino alla 9.6 per cinque secondi non si
    leggeva niente, e non si capiva se il programma stesse facendo qualcosa."""
    passati = min(int(time.monotonic() - inizio) + 1, int(SECONDI_RILEVAMENTO))
    picco = max(livelli.values(), default=0.0)
    return f"\r{prefisso} {passati}/{SECONDI_RILEVAMENTO:.0f} s, picco {decibel(picco):.0f} dB\r"


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
    """Ascolta tutti i dispositivi insieme e tiene quelli con segnale, dal
    piu' forte al piu' debole: il primo e' quello che Invio sceglie. Chi non
    si apre in parallelo si riprova in serie. Mentre ascolta, una riga dice
    i secondi passati e il volume piu' forte sentito. Se nessuno ha segnale
    si restituiscono tutti."""
    print(f"Rilevamento automatico: ascolto di tutte le periferiche per {SECONDI_RILEVAMENTO:.0f} secondi. Suona o parla vicino al microfono.")
    results = {}
    livelli = {}
    failed_parallel = []
    lock = threading.Lock()

    def test_device(device_idx):
        try:
            rumore = _misura_rumore(device_idx, livelli=livelli)
        except ERRORI_AUDIO:
            with lock:
                failed_parallel.append(device_idx)
            return
        with lock:
            results[device_idx] = rumore

    threads = [threading.Thread(target=test_device, args=(int(idx_str),)) for idx_str in input_devices]
    inizio = time.monotonic()
    for t in threads:
        t.start()
    # La riga si scrive almeno una volta, anche se l'ascolto finisce subito
    while True:
        print(_riga_di_ascolto(inizio, livelli), end="", flush=True)
        if not any(t.is_alive() for t in threads):
            break
        for t in threads:
            t.join(timeout=AGGIORNAMENTO_RILEVAMENTO / max(1, len(threads)))
    for numero, idx in enumerate(failed_parallel, start=1):
        esito = {}
        filo = threading.Thread(target=lambda i=idx, e=esito: e.update(rms=_misura_rumore_sicura(i, livelli)))
        inizio = time.monotonic()
        filo.start()
        while filo.is_alive():
            print(_riga_di_ascolto(inizio, livelli, f"Riprovo {numero}/{len(failed_parallel)}:"), end="", flush=True)
            filo.join(timeout=AGGIORNAMENTO_RILEVAMENTO)
        results[idx] = esito.get("rms", 0.0)
    print()
    con_segnale = sorted(((results.get(int(idx_str), 0.0), idx_str) for idx_str in input_devices), reverse=True)
    filtered = {}
    for rms_val, idx_str in con_segnale:
        if rms_val >= RMS_THRESHOLD:
            filtered[idx_str] = f"{input_devices[idx_str]} (segnale {decibel(rms_val):.0f} dB)"
    if not filtered:
        print(f"Nessun segnale significativo rilevato (sotto {decibel(RMS_THRESHOLD):.0f} dB). Vengono mostrati tutti i dispositivi.")
        return input_devices
    return filtered


def _misura_rumore_sicura(device_idx, livelli):
    """Come _misura_rumore, ma zero se il dispositivo non si apre."""
    try:
        return _misura_rumore(device_idx, livelli=livelli)
    except ERRORI_AUDIO:
        return 0.0


def _predefinito_prima(input_devices):
    """Senza rilevamento, il dispositivo di ingresso predefinito del sistema
    viene per primo, cosi' Invio sceglie quello."""
    try:
        predefinito = str(sd.default.device[0])
    except (TypeError, IndexError, sd.PortAudioError):
        return input_devices
    if predefinito not in input_devices:
        return input_devices
    ordinati = {predefinito: f"{input_devices[predefinito]} (predefinito del sistema)"}
    ordinati.update((k, v) for k, v in input_devices.items() if k != predefinito)
    return ordinati


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
        proposta = "il primo, il piu' forte"
    else:
        filtered_devices = _predefinito_prima(input_devices)
        proposta = "il primo"
    print("Dispositivi di input disponibili.")
    # Invio a vuoto sceglie il primo dell'elenco, che e' gia' in ordine
    scelta_device = menu(d=filtered_devices, p=f"Seleziona il dispositivo di input (Invio per {proposta}): ", show=True,
                         numbered=True, ordered=False, empty_enter=next(iter(filtered_devices)))
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
        detected_freq = rileva_frequenza(mono, device_sr)
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
            db_val = decibel(rms)
            above_threshold = rms >= RMS_THRESHOLD
            if rms > 1e-6:
                all_dbs.append(db_val)
            # La media mobile lega la lettura a quella del secondo prima, solo
            # se anche quella era valida e dava la stessa nota: al primo suono,
            # e a ogni nota nuova, si riparte da zero.
            valida = False
            precedente = ema_state['freq'] if ema_state['active'] else None
            avg_freq = frequenza_da_mostrare(readings, precedente) if above_threshold else None
            if avg_freq is not None:
                valida = True
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
