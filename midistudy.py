# Ultima modifica: 6 gennaio 2026 (v0.4.6)

import os
import sys
import re
import json
import time
import numpy as np
import sounddevice as sd
from music21 import converter, midi, stream, note, chord, meter, tempo, key as m21key
from GBUtils import dgt, menu, key
from fractions import Fraction
import GBAudio

# Costanti
MIDISTUDY_VERSION = "0.4.7 (Alpha) del 6 gennaio 2026"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MIDI_DIR = os.path.join(BASE_DIR, "midi")
SETTINGS_FILE = os.path.join(BASE_DIR, "chitabry-settings.json")
TEMP_PREVIEW_FILE = os.path.join(DEFAULT_MIDI_DIR, "preview_temp.mid")

def _header():
    print("\n" + "="*40)
    print(f"MidiStudy - Analisi Musicale v{MIDISTUDY_VERSION}")
    print("="*40 + "\n")

def cleanup_temp_files():
    """Rimuove i file temporanei creati durante la sessione."""
    try:
        if os.path.exists(TEMP_PREVIEW_FILE):
            os.remove(TEMP_PREVIEW_FILE)
    except Exception:
        pass

def get_nomenclatura():
    """Legge la preferenza di nomenclatura dal file impostazioni di Chitabry."""
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('nomenclatura', 'latino')
    except Exception:
        pass
    return 'latino'

def traduci_nota(nota_std):
    """Converte una nota music21 (es. C#4, BB4) nella nomenclatura scelta."""
    nom_stile = get_nomenclatura()
    nota_pulita = nota_std.replace('-', 'b')
    
    if len(nota_pulita) >= 2 and nota_pulita[0] == nota_pulita[1] and nota_pulita[0].isalpha():
        nota_pulita = nota_pulita[0] + "b" + nota_pulita[2:]
        
    if nom_stile == 'anglo':
        return nota_pulita

    mappa = {
        'C': 'DO', 'C#': 'DO#', 'Db': 'REb', 'D': 'RE', 'D#': 'RE#', 'Eb': 'MIb',
        'E': 'MI', 'F': 'FA', 'F#': 'FA#', 'Gb': 'SOLb', 'G': 'SOL', 'G#': 'SOL#',
        'Ab': 'LAb', 'A': 'LA', 'A#': 'LA#', 'Bb': 'SIb', 'B': 'SI'
    }
    
    match = re.match(r"^([A-Ga-g][#b]?)([0-9]?)$", nota_pulita)
    if match:
        nome_base, ottava = match.groups()
        nome_latino = mappa.get(nome_base.title(), nome_base.title())
        return f"{nome_latino}{ottava}"
    return nota_pulita

def seleziona_file_midi():
    """Scansiona la cartella e chiede all'utente di scegliere un file."""
    if not os.path.exists(DEFAULT_MIDI_DIR):
        print(f"Errore: La cartella {DEFAULT_MIDI_DIR} non esiste.")
        return None
    files = [f for f in os.listdir(DEFAULT_MIDI_DIR) if f.lower().endswith(('.mid', '.midi'))]
    if not files:
        print(f"Nessun file MIDI trovato in: {DEFAULT_MIDI_DIR}")
        return None
    d_files = {str(i+1): f for i, f in enumerate(files)}
    scelta = menu(d=d_files, show=True, numbered=True, p="Scegli il file da analizzare: ")
    if scelta: return os.path.join(DEFAULT_MIDI_DIR, d_files[scelta])
    return None

def analizza_tracce(filepath):
    """Carica il MIDI e mostra le tracce disponibili."""
    print(f"\nCaricamento di: {os.path.basename(filepath)}...")
    print("Attendere, analisi in corso (richiede music21)...")
    try:
        s = converter.parse(filepath)
        parti = s.parts
        if not parti: parti = [s]
        tot_tracce = len(parti)
        while True:
            d_tracce = {"0": "Ascolta MIDI Completo (Player Sistema)"}
            for i, p in enumerate(parti):
                nome = p.partName if p.partName else f"Traccia {i}"
                num_note = len(p.flatten().notes)
                d_tracce[str(i+1)] = f"{nome} ({num_note} note)"
            print(f"\n--- Tracce in {os.path.basename(filepath)} ---")
            # RIMOSSO numbered=True per usare le chiavi 0, 1, 2...
            scelta = menu(d=d_tracce, show=True, numbered=False, p="Scegli la traccia da studiare [INVIO per tornare]: ")
            
            if not scelta:
                cleanup_temp_files()
                break
            
            if scelta == "0":
                print("Avvio riproduzione MIDI completo...")
                try: os.startfile(filepath)
                except Exception as e: print(f"Errore riproduzione: {e}")
                continue

            idx = int(scelta)
            studia_traccia(parti[idx-1], d_tracce[scelta], filepath, idx, tot_tracce)
            if len(parti) == 1: break
    except Exception as e:
        print(f"Errore durante l'analisi del file: {e}")



def play_preview(part):
    """Salva la parte in un file MIDI temporaneo e lo apre con il player di sistema."""
    try:
        part.write('midi', fp=TEMP_PREVIEW_FILE)
        os.startfile(TEMP_PREVIEW_FILE)
    except Exception as e:
        print(f"Errore durante la riproduzione: {e}")

def get_duration_concise(q_len):
    """Converte la quarterLength in notazione frazionaria reale (es. /4, 3/8, 5/16)."""
    f = Fraction(q_len / 4.0).limit_denominator(64)
    if f.numerator == 1: return f"/{f.denominator}"
    else: return f"{f.numerator}/{f.denominator}"

def formatta_evento(el, durata):
    """Restituisce la stringa formattata per Note o Accordi."""
    dur_str = get_duration_concise(durata)
    if isinstance(el, note.Note):
        nome = traduci_nota(el.nameWithOctave)
        return f"{nome} {dur_str}"
    elif isinstance(el, chord.Chord):
        pitches = sorted(el.pitches)
        nomi_note = [traduci_nota(p.nameWithOctave) for p in pitches]
        block = "[" + " ".join(nomi_note) + "]"
        return f"{block} {dur_str}"
    elif isinstance(el, note.Rest):
        if durata < 0.05: return None
        return f"PAUSA {dur_str}"
    return None

def get_metadata(part):
    bpm, time_sig, key_sig = "N/A", "4/4", "N/A"
    flat_part = part.flatten()
    ts = flat_part.getElementsByClass(meter.TimeSignature)
    if ts: time_sig = ts[0].ratioString
    ks = flat_part.getElementsByClass(m21key.KeySignature)
    if ks:
        try: key_sig = ks[0].asKey().name
        except: key_sig = f"{ks[0].sharps} accidenti"
    mm = flat_part.getElementsByClass(tempo.MetronomeMark)
    if mm:
        try: bpm = str(mm[0].getQuarterBPM())
        except: pass
    return bpm, time_sig, key_sig

def genera_lista_eventi_per_battute(part):
    output_lines = []
    try: measures = part.makeMeasures()
    except: measures = part
    measure_list = measures.getElementsByClass(stream.Measure)
    if not measure_list:
        output_lines.append("(Nessuna suddivisione in battute rilevata)")
        return output_lines
    for m in measure_list:
        numero_battuta = m.measureNumber if m.measureNumber is not None else 0
        contenuto_battuta = []
        for el in m.notesAndRests:
            txt = formatta_evento(el, el.duration.quarterLength)
            if txt:
                tie_str = " ~" if (hasattr(el, 'tie') and el.tie and el.tie.type in ['start', 'continue']) else ""
                contenuto_battuta.append(txt + tie_str)
        if contenuto_battuta:
            output_lines.append(f"B{numero_battuta:02d}: " + " | ".join(contenuto_battuta))
    return output_lines

def play_battuta_audio(part, numero_battuta, tipo_suono=2):
    """Riproduce l'audio di una singola battuta usando GBAudio."""
    try:
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            suono_params = cfg.get(f'suono_{tipo_suono}')
            bpm = float(cfg.get('default_bpm', 60))
        m = part.measure(numero_battuta)
        if not m: return
        mm = m.flatten().getElementsByClass(tempo.MetronomeMark)
        if mm: bpm = mm[0].getQuarterBPM()
        segmenti = []
        renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
        q_dur = 60.0 / bpm
        for el in m.flatten().notesAndRests:
            dur_sec = el.duration.quarterLength * q_dur
            if dur_sec <= 0: continue
            if isinstance(el, note.Note):
                f = GBAudio.note_to_freq(el.nameWithOctave)
                if tipo_suono == 1: renderer.set_params(f, dur_sec, suono_params['volume'], 0.0, pluck_hardness=suono_params['pluck_hardness'], damping_factor=suono_params['damping_factor'])
                else: renderer.set_params(f, dur_sec, suono_params['volume'], 0.0, kind=suono_params['kind'], adsr_list=suono_params['adsr'])
                buf = renderer.render()
                if buf.size > 0: segmenti.append(buf)
            elif isinstance(el, chord.Chord):
                chord_buf = np.zeros((int(dur_sec * GBAudio.FS), 2), dtype=np.float32)
                for p in el.pitches:
                    f = GBAudio.note_to_freq(p.nameWithOctave)
                    if tipo_suono == 1: renderer.set_params(f, dur_sec, suono_params['volume'], 0.0, pluck_hardness=suono_params['pluck_hardness'], damping_factor=suono_params['damping_factor'])
                    else: renderer.set_params(f, dur_sec, suono_params['volume'], 0.0, kind=suono_params['kind'], adsr_list=suono_params['adsr'])
                    n_buf = renderer.render()
                    if n_buf.size > 0:
                        min_l = min(len(chord_buf), len(n_buf))
                        chord_buf[:min_l] += n_buf[:min_l]
                mx = np.max(np.abs(chord_buf))
                if mx > 1.0: chord_buf /= mx
                segmenti.append(chord_buf)
            elif isinstance(el, note.Rest): segmenti.append(np.zeros((int(dur_sec * GBAudio.FS), 2), dtype=np.float32))
        if segmenti: sd.play(np.concatenate(segmenti, axis=0), samplerate=GBAudio.FS, blocking=False)
    except Exception as e: print(f"Errore audio: {e}")

def visualizzatore_interattivo(output_lines, part):
    tot_righe = len(output_lines)
    idx = 0
    play_continuo = False
    current_sound_type = 2 # Default: Synth/Flauto
    sound_names = {1: "Chitarra", 2: "Synth (Flauto)"}
    
    print("\n[<-/->] Naviga, [SPAZIO] Play, [P] Cambia Strumento, [INVIO] Continuo, [ESC] Esci")
    
    while True:
        riga = output_lines[idx]
        match_num = re.search(r"B(\d+):", riga)
        num_battuta = int(match_num.group(1)) if match_num else 0
        
        sys.stdout.write(f"\r{' '*110}\r")
        sys.stdout.write(f"{riga} > ")
        sys.stdout.flush()
        
        k = ''
        if play_continuo:
            with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
                bpm = float(json.load(f).get('default_bpm', 60))
            m = part.measure(num_battuta)
            dur_battuta = m.duration.quarterLength * (60.0 / bpm)
            
            play_battuta_audio(part, num_battuta, current_sound_type)
            k = key(attesa=dur_battuta + 0.05).lower()
            
            if k:
                play_continuo = False
                sd.stop()
            else:
                if idx < tot_righe - 1:
                    idx += 1
                    continue
                else:
                    play_continuo = False
        
        if not k:
            k = key().lower()
        
        if k == chr(27) or k == 'q': sd.stop(); break
        elif k == 'm' or k == 'n': idx = min(idx + 1, tot_righe - 1)
        elif k == 'k' or k == 'b': idx = max(idx - 1, 0)
        elif k == ' ':
            sd.stop()
            play_battuta_audio(part, num_battuta, current_sound_type)
        elif k == 'p': 
            current_sound_type = 1 if current_sound_type == 2 else 2
            print(f"\n[Audio] Preset cambiato: {sound_names[current_sound_type]}")
            time.sleep(0.5)
        elif k == '\r': play_continuo = True
        
    print("\nUscita visualizzatore.")

def estrai_e_mostra_note(part, idx, tot, filepath):
    print("\nElaborazione battute...")
    output_lines = genera_lista_eventi_per_battute(part)
    if not output_lines: return
    bpm, time_sig, key_sig = get_metadata(part)
    print(f"\nAnalisi: {os.path.basename(filepath)} | Traccia {idx}/{tot}")
    print(f"BPM: {bpm} | Tempo: {time_sig} | Tonalità: {key_sig}\n" + "-"*40)
    visualizzatore_interattivo(output_lines, part)

def salva_su_file(part, label, filepath, idx, tot):
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    out_name = f"{base_name}_{''.join([c for c in label if c.isalnum() or c in (' ','-','_')]).strip()}.txt"
    out_path = os.path.join(DEFAULT_MIDI_DIR, out_name)
    print(f"Esportazione in {out_path}...")
    lines = genera_lista_eventi_per_battute(part)
    bpm, ts, ks = get_metadata(part)
    header = [f"MidiStudy v{MIDISTUDY_VERSION}", f"File: {os.path.basename(filepath)}", f"Traccia: {idx}/{tot} - {label}", f"BPM={bpm}, Tempo={ts}, Tonalità={ks}", f"Nomenclatura: {get_nomenclatura().upper()}", "="*40, ""]
    try:
        with open(out_path, "w", encoding="utf-8") as f: f.write("\n".join(header + lines + ["", f"Totale Battute: {len(lines)}"]))
        print("Salvato.")
    except Exception as e: print(f"Errore: {e}")

def studia_traccia(part, label, filepath, idx, tot):
    while True:
        print(f"\n--- Traccia {idx}/{tot}: {label} ---")
        s = menu(d={"a": "Ascolta (Player Sistema)", "e": "Visualizza (Battute/Audio)", "s": "Salva TXT", "x": "Indietro"}, p="Azione > ", show=True)
        if s == "x" or s is None: cleanup_temp_files(); break
        elif s == "a": play_preview(part)
        elif s == "e": estrai_e_mostra_note(part, idx, tot, filepath)
        elif s == "s": salva_su_file(part, label, filepath, idx, tot)

def MidiStudyMain():
    _header()
    cleanup_temp_files()
    while True:
        s = menu(d={"1": "Seleziona file MIDI", "x": "Esci"}, p="MidiStudy > ", show=True)
        if s == "x" or s is None: cleanup_temp_files(); break
        elif s == "1":
            f = seleziona_file_midi()
            if f: analizza_tracce(f)
    print("\nRitorno a Chitabry...")
