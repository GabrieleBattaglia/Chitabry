# Ultima modifica: 21 maggio 2026 (v0.4.8)

import os
import sys
import re
import json
import time
import numpy as np
import sounddevice as sd
import mido
import ctypes
from music21 import converter, stream, note, chord, meter, tempo, key as m21key
from GBUtils import menu, key
from fractions import Fraction
import GBAudio

# Costanti
MIDISTUDY_VERSION = "0.4.8 (Alpha) del 21 maggio 2026"
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
        
    if nom_stile == 'anglo' or nom_stile == 'anglosassone':
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
    files = [f for f in os.listdir(DEFAULT_MIDI_DIR) if f.lower().endswith(('.mid', '.midi', '.abc'))]
    if not files:
        print(f"Nessun file musicale trovato in: {DEFAULT_MIDI_DIR}")
        return None

    d_files = {}
    for f in files:
        filepath = os.path.join(DEFAULT_MIDI_DIR, f)
        dur_str = "??:??"
        if f.lower().endswith(('.mid', '.midi')):
            try:
                mid = mido.MidiFile(filepath)
                durata = mid.length
                m = int(durata // 60)
                s = int(durata % 60)
                dur_str = f"{m:02d}:{s:02d}"
            except Exception:
                pass
        d_files[f] = dur_str

    scelta = menu(d=d_files, show=True, numbered=False, p="Scegli il file da analizzare [INVIO per annullare]: ")
    if scelta: return os.path.join(DEFAULT_MIDI_DIR, scelta)
    return None
def gestisci_tools_abc(filepath):
    from config import impostazioni, salva_impostazioni
    from GBUtils import dgt
    import subprocess

    abc_dir = impostazioni.get('abc_tools_dir', '')
    if abc_dir:
        abc_dir = abc_dir.strip('"\'')
        
    if not abc_dir or not os.path.exists(abc_dir):
        print("\nCartella ABC Tools non configurata o inesistente.")
        print("Per usare queste funzioni avanzate devi avere i binari di abcMIDI (es. midi2abc, abc2midi).")
        print("Puoi scaricarli da: https://github.com/sshlien/abcmidi")
        abc_dir = dgt("Inserisci il percorso assoluto alla cartella con gli eseguibili (o Invio per annullare): ", kind="s")
        if not abc_dir:
            print("Operazione annullata.")
            return
            
        abc_dir = abc_dir.strip('"\'')
        if not os.path.exists(abc_dir):
            print(f"La cartella specificata non esiste: {abc_dir}")
            return
            
        impostazioni['abc_tools_dir'] = abc_dir
        salva_impostazioni()
        print(f"Cartella configurata con successo: {abc_dir}")

    tools_found = {
        'midi2abc': os.path.exists(os.path.join(abc_dir, 'midi2abc.exe')),
        'abc2midi': os.path.exists(os.path.join(abc_dir, 'abc2midi.exe')),
        'abc2midiu': os.path.exists(os.path.join(abc_dir, 'abc2midiu.exe')),
        'abc2abc': os.path.exists(os.path.join(abc_dir, 'abc2abc.exe')),
        'mftext': os.path.exists(os.path.join(abc_dir, 'mftext.exe')),
        'midistats': os.path.exists(os.path.join(abc_dir, 'midistats.exe')),
        'midicopy': os.path.exists(os.path.join(abc_dir, 'midicopy.exe')),
        'abcm2ps': os.path.exists(os.path.join(abc_dir, 'abcm2ps.exe')),
        'yaps': os.path.exists(os.path.join(abc_dir, 'yaps.exe'))
    }

    is_abc = filepath.lower().endswith('.abc')
    is_midi = filepath.lower().endswith(('.mid', '.midi'))

    while True:
        print(f"\n--- Strumenti ABC (Cartella: {abc_dir}) ---")
        opzioni_abc = {}

        if is_midi:
            if tools_found['midi2abc']: opzioni_abc["Converti in ABC (midi2abc)"] = "Genera un file .abc dal MIDI corrente"
            if tools_found['mftext']: opzioni_abc["Converti in Testo (mftext)"] = "Genera un dump testuale dal MIDI corrente"
            if tools_found['midistats']: opzioni_abc["Statistiche MIDI (midistats)"] = "Mostra statistiche dettagliate sul MIDI"
            if tools_found['midicopy']: opzioni_abc["Copia porzione MIDI (midicopy)"] = "Estrai e copia parti o tracce del MIDI"

        if is_abc:
            if tools_found['abc2midi']: opzioni_abc["Converti in MIDI (abc2midi)"] = "Genera un file .mid dall'ABC corrente"
            if tools_found['abc2midiu']: opzioni_abc["Converti in MIDI Unicode (abc2midiu)"] = "Genera un .mid (supporto Unicode avanzato)"
            if tools_found['abc2abc']: opzioni_abc["Formatta / Trasponi (abc2abc)"] = "Applica operazioni sull'ABC corrente"
            if tools_found['abcm2ps']: opzioni_abc["Genera PostScript (abcm2ps)"] = "Crea un file grafico .ps per la stampa"
            if tools_found['yaps']: opzioni_abc["Genera PostScript avanzato (yaps)"] = "Crea file grafico .ps (motore alternativo)"

        if not opzioni_abc:
            print("Nessuno strumento compatibile trovato per questo tipo di file nella cartella configurata.")
            break

        scelta = menu(d=opzioni_abc, show=True, numbered=False, p="Scegli lo strumento da lanciare [INVIO per tornare]: ")
        if not scelta:
            break

        try:
            base_path = os.path.splitext(filepath)[0]
            if scelta == "Converti in ABC (midi2abc)":
                out_path = base_path + "_converted.abc"
                exe = os.path.join(abc_dir, 'midi2abc.exe')
                print(f"Esecuzione: {exe} ...")
                subprocess.run([exe, filepath, '-o', out_path], check=True)
                print(f"File generato con successo: {out_path}")
            elif scelta == "Converti in Testo (mftext)":
                out_path = base_path + "_dump.txt"
                exe = os.path.join(abc_dir, 'mftext.exe')
                print(f"Esecuzione: {exe} ...")
                with open(out_path, "w", encoding="utf-8") as out_f:
                    subprocess.run([exe, filepath], check=True, stdout=out_f)
                print(f"File generato con successo: {out_path}")
            elif scelta == "Statistiche MIDI (midistats)":
                out_path = base_path + "_stats.txt"
                exe = os.path.join(abc_dir, 'midistats.exe')
                print(f"Esecuzione: {exe} ...")
                with open(out_path, "w", encoding="utf-8") as out_f:
                    subprocess.run([exe, filepath], check=True, stdout=out_f)
                print(f"Statistiche salvate in: {out_path}")
            elif scelta == "Copia porzione MIDI (midicopy)":
                print("\nQuesto strumento richiede parametri aggiuntivi da riga di comando (es. -trk 1).")
                print(f"Puoi eseguirlo manualmente dal terminale: midicopy [opzioni] {os.path.basename(filepath)} output.mid")
                from GBUtils import aspetta
                aspetta(2)
            elif scelta == "Converti in MIDI (abc2midi)":
                out_path = base_path + "_converted.mid"
                exe = os.path.join(abc_dir, 'abc2midi.exe')
                print(f"Esecuzione: {exe} ...")
                subprocess.run([exe, filepath, '-o', out_path], check=True)
                print(f"File generato con successo: {out_path}")
            elif scelta == "Converti in MIDI Unicode (abc2midiu)":
                out_path = base_path + "_converted_unicode.mid"
                exe = os.path.join(abc_dir, 'abc2midiu.exe')
                print(f"Esecuzione: {exe} ...")
                subprocess.run([exe, filepath, '-o', out_path], check=True)
                print(f"File generato con successo: {out_path}")
            elif scelta == "Formatta / Trasponi (abc2abc)":
                out_path = base_path + "_formatted.abc"
                exe = os.path.join(abc_dir, 'abc2abc.exe')
                print(f"Esecuzione: {exe} ...")
                with open(out_path, "w", encoding="utf-8") as out_f:
                    subprocess.run([exe, filepath], check=True, stdout=out_f)
                print(f"File generato con successo: {out_path}")
            elif scelta == "Genera PostScript (abcm2ps)":
                out_path = base_path + ".ps"
                exe = os.path.join(abc_dir, 'abcm2ps.exe')
                print(f"Esecuzione: {exe} ...")
                subprocess.run([exe, filepath, '-O', out_path], check=True)
                print(f"File generato con successo: {out_path}")
            elif scelta == "Genera PostScript avanzato (yaps)":
                out_path = base_path + ".ps"
                exe = os.path.join(abc_dir, 'yaps.exe')
                print(f"Esecuzione: {exe} ...")
                subprocess.run([exe, filepath, '-o', out_path], check=True)
                print(f"File generato con successo: {out_path}")
        except subprocess.CalledProcessError as e:
            print(f"Errore durante l'esecuzione dello strumento: {e}")
        except Exception as e:
            print(f"Errore imprevisto: {e}")

def analizza_tracce(filepath):
    """Carica il MIDI e mostra le opzioni principali del brano."""
    print(f"\nCaricamento di: {os.path.basename(filepath)}...")
    print("Attendere, analisi in corso (richiede music21)...")
    try:
        s = converter.parse(filepath)

        while True:
            bpm, time_sig, key_sig = get_metadata(s)
            print(f"\n--- Analisi Brano: {os.path.basename(filepath)} ---")
            print(f"Metadati: BPM={bpm} | Tempo={time_sig} | Tonalità={key_sig}")

            opzioni_brano = {
                "Ascolta l'intero brano": "Riproduce il file corrente (Player MCI)",
                "Trasposizione del brano": "Modifica la tonalità globale",
                "BPM del brano": "Imposta i BPM globali",
                "Strumenti ABC": "Accedi alla suite esterna abcMIDI",
                "Scegli tracce": "Seleziona una o più tracce da studiare"
            }
            scelta_brano = menu(d=opzioni_brano, show=True, numbered=False, p="Azione sul brano [INVIO o ESC per tornare]: ")

            if not scelta_brano:
                cleanup_temp_files()
                break

            if scelta_brano == "Ascolta l'intero brano":
                print("Avvio riproduzione MIDI completo (MCI)...")
                # play_preview scrive l'oggetto 's' (che può essere stato trasposto) in un file temp e lo riproduce
                play_preview(s)

            elif scelta_brano == "Trasposizione del brano":
                esegui_trasposizione(s)

            elif scelta_brano == "Strumenti ABC":
                gestisci_tools_abc(filepath)

            elif scelta_brano == "BPM del brano":
                from GBUtils import dgt
                nuovi_bpm = dgt("Inserisci i nuovi BPM: ", kind="f", fmin=20, fmax=500)
                if nuovi_bpm:
                    marks_found = False
                    for p in s.parts:
                        for mm in p.flatten().getElementsByClass(tempo.MetronomeMark):
                            mm.number = float(nuovi_bpm)
                            marks_found = True
                    if not marks_found:
                        new_mm = tempo.MetronomeMark(number=float(nuovi_bpm))
                        if s.parts:
                            s.parts[0].insert(0, new_mm)
                        else:
                            s.insert(0, new_mm)
                    print(f"BPM del brano impostati a {nuovi_bpm}.")
                    
            elif scelta_brano == "Scegli tracce":
                parti = list(s.parts)
                if not parti: parti = [s]
                tot_tracce = len(parti)
                selected_indices = set()

                print("\n--- Scegli Tracce (Multi-selezione) ---")
                print("Comandi: <num> Seleziona/Deseleziona | 0 Fatto | ? Info | [INVIO] Annulla")
                for i, p in enumerate(parti):
                    nome = p.partName if p.partName else f"Traccia {i}"
                    num_note = len(p.flatten().notes)
                    print(f"  {i+1}: {nome} ({num_note} note)")

                from GBUtils import dgt
                while True:
                    tot_sel = len(selected_indices)
                    scelta_traccia = dgt(f"\nTracce selezionate {tot_sel}/{tot_tracce} > ", kind="s")

                    if not scelta_traccia:
                        break # Torna indietro con invio a vuoto

                    scelta_traccia = scelta_traccia.strip().lower()
                    if scelta_traccia == '?':
                        print("\nStato delle tracce:")
                        for i, p in enumerate(parti):
                            nome = p.partName if p.partName else f"Traccia {i}"
                            num_note = len(p.flatten().notes)
                            status = "[X]" if i in selected_indices else "[ ]"
                            print(f"  {i+1}: {status} {nome} ({num_note} note)")
                        print("Comandi: <num> Seleziona/Deseleziona | 0 Fatto | ? Info | [INVIO] Annulla")
                    elif scelta_traccia == '0':
                        if not selected_indices:
                            print("Nessuna traccia selezionata!")
                            continue

                        # Combiniamo le tracce in uno Score per preservare gli strumenti MIDI originali
                        if len(selected_indices) == 1:
                            idx_part = list(selected_indices)[0]
                            traccia_finale = parti[idx_part]
                            nome_finale = parti[idx_part].partName if parti[idx_part].partName else f"Traccia {idx_part}"
                        else:
                            traccia_finale = stream.Score()
                            nomi = []
                            for idx in sorted(list(selected_indices)):
                                traccia_finale.insert(0, parti[idx])
                                nome_p = parti[idx].partName if parti[idx].partName else str(idx+1)
                                nomi.append(nome_p)
                            nome_finale = "Mix: " + ", ".join(nomi)

                        studia_traccia(traccia_finale, nome_finale, filepath, 1, 1)
                        if len(parti) == 1: break
                    elif scelta_traccia.isdigit():
                        idx = int(scelta_traccia) - 1
                        if 0 <= idx < tot_tracce:
                            if idx in selected_indices:
                                selected_indices.remove(idx)
                                print(f"Traccia {idx+1} rimossa.")
                            else:
                                selected_indices.add(idx)
                                print(f"Traccia {idx+1} aggiunta.")
                        else:
                            print("Numero traccia non valido.")
    except Exception as e:
        print(f"Errore durante l'analisi del file: {e}")

def play_preview(part):
    """Salva la parte in un file MIDI temporaneo e lo apre con il player interno MCI."""
    try:
        part.write('midi', fp=TEMP_PREVIEW_FILE)

        try:
            mid = mido.MidiFile(TEMP_PREVIEW_FILE)
            durata_sec = mid.length
        except Exception:
            # Fallback se mido fallisce a causa di metadati strani (es. 8 sharps)
            try:
                bpm_str, _, _ = get_metadata(part)
                bpm_val = float(bpm_str)
            except Exception:
                bpm_val = 120.0
            durata_sec = float(part.duration.quarterLength) * (60.0 / bpm_val)

        print(f"\nRiproduzione in corso... (Durata: {durata_sec:.1f}s)")
        print("Premi ESC o Q per interrompere.")        
        send_mci_command("close preview_player")
        cmd_open = f'open "{os.path.abspath(TEMP_PREVIEW_FILE)}" type sequencer alias preview_player'
        send_mci_command(cmd_open)
        send_mci_command('play preview_player')
        start_time = time.time()
        try:
            while True:
                elapsed = time.time() - start_time
                if elapsed >= durata_sec + 0.5:
                    break

                perc = min(100.0, (elapsed / durata_sec) * 100.0) if durata_sec > 0 else 0.0
                m_val = int(elapsed // 60)
                s_val = int(elapsed % 60)
                print(f"\r{m_val:02d}:{s_val:02d} | {perc:.1f}% > {' '*5}\r", end="", flush=True)

                k = key(attesa=0.3)
                if k and k.lower() in ('esc', 'q', chr(27)):
                    print("\nRiproduzione interrotta.")
                    break
        finally:
            send_mci_command("stop preview_player")
            send_mci_command("close preview_player")
            
    except Exception as e:
        print(f"Errore durante la riproduzione MCI: {e}")

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
        except Exception: key_sig = f"{ks[0].sharps} accidenti"
    key_sig = key_sig.replace('-', 'b')
    mm = flat_part.getElementsByClass(tempo.MetronomeMark)
    if mm:
        try: bpm = str(mm[0].getQuarterBPM())
        except Exception: pass
    return bpm, time_sig, key_sig

def genera_lista_eventi_per_battute(part):
    output_lines = []
    try:
        # Se la parte è uno Score (multi-traccia), fondiamola in un unico rigo di accordi
        if isinstance(part, stream.Score) or len(part.getElementsByClass(stream.Part)) > 0:
            target_part = part.chordify()
        else:
            target_part = part

        q_part = target_part.quantize()
        measures = q_part.makeMeasures()
    except Exception:
        measures = part
    measure_list = measures.getElementsByClass(stream.Measure)
    if not measure_list:
        output_lines.append("(Nessuna suddivisione in battute rilevata)")
        return output_lines
        
    last_bpm = None
    for m in measure_list:
        numero_battuta = m.measureNumber if m.measureNumber is not None else 0
        
        mm_list = m.getElementsByClass(tempo.MetronomeMark)
        current_bpm = None
        if mm_list:
            current_bpm = mm_list[0].getQuarterBPM()
            
        bpm_str = ""
        if current_bpm is not None and current_bpm != last_bpm:
            # Formattiamo senza decimali se è intero
            if float(current_bpm).is_integer():
                bpm_str = f" [BPM: {int(current_bpm)}]"
            else:
                bpm_str = f" [BPM: {float(current_bpm):.1f}]"
            last_bpm = current_bpm
            
        contenuto_battuta = []
        for el in m.notesAndRests:
            txt = formatta_evento(el, el.duration.quarterLength)
            if txt:
                tie_str = " ~" if (hasattr(el, 'tie') and el.tie and el.tie.type in ['start', 'continue']) else ""
                contenuto_battuta.append(txt + tie_str)
        if contenuto_battuta:
            output_lines.append(f"B{numero_battuta:02d}{bpm_str}: " + " | ".join(contenuto_battuta))
    return output_lines

def play_battuta_audio(part, numero_battuta, tipo_suono=2, bpm_override=None):
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
        if bpm_override: bpm = float(bpm_override)
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

def esegui_trasposizione(part):
    from GBUtils import enter_escape, dgt
    from music21 import note, chord

    # 1. Trova le note più basse e più alte per evitare out-of-bounds
    min_midi = 127
    max_midi = 0
    for n in part.flatten().notes:
        if isinstance(n, note.Note) and n.pitch.midi is not None:
            if n.pitch.midi < min_midi: min_midi = n.pitch.midi
            if n.pitch.midi > max_midi: max_midi = n.pitch.midi
        elif isinstance(n, chord.Chord):
            for p in n.pitches:
                if p.midi is not None:
                    if p.midi < min_midi: min_midi = p.midi
                    if p.midi > max_midi: max_midi = p.midi

    # Se la traccia è vuota o non ha note valide, bypassa i limiti
    if min_midi == 127 and max_midi == 0:
        min_midi, max_midi = 60, 60

    limite_inf = -min_midi
    limite_sup = 127 - max_midi

    # Restringiamo a -24 / +24 massimo
    limite_inf = max(-24, limite_inf)
    limite_sup = min(24, limite_sup)

    print("\n\nAnalisi delle trasposizioni possibili...")
    best_interval = 0
    min_accidentals = 999999
    total_notes_in_track = 0

    # Conta accidenti per ogni trasposizione da -5 a +6 (se nel range)
    for i in range(max(-5, limite_inf), min(7, limite_sup + 1)):
        test_part = part.transpose(i)
        accidentals = 0
        total_notes = 0
        for n in test_part.flatten().notes:
            if isinstance(n, note.Note):
                total_notes += 1
                if n.pitch.accidental and n.pitch.accidental.alter != 0:
                    accidentals += 1
            elif isinstance(n, chord.Chord):
                for p in n.pitches:
                    total_notes += 1
                    if p.accidental and p.accidental.alter != 0:
                        accidentals += 1

        if accidentals < min_accidentals:
            min_accidentals = accidentals
            best_interval = i
            total_notes_in_track = total_notes

    segno = "+" if best_interval > 0 else ""
    print(f"Traccia: {total_notes_in_track} note totali.")
    if min_accidentals != 999999:
        print(f"Tonalità ottimale calcolata: trasposizione di {segno}{best_interval} semitoni.")
        print(f"Note alterate (non naturali) previste: {min_accidentals}")
        scelta = enter_escape("Vuoi applicare questa trasposizione ottimale? [INVIO=Sì, ESC=No]")
    else:
        print("Impossibile calcolare una tonalità ottimale.")
        scelta = False

    if scelta:
        part.transpose(best_interval, inPlace=True)
        print(f"Traccia trasposta di {segno}{best_interval} semitoni.")
    else:
        print(f"\nLimiti di trasposizione consentiti: da {limite_inf} a +{limite_sup} semitoni (Max +/- 24).")
        if limite_inf > limite_sup:
            print("Nessuna trasposizione possibile per questa traccia senza sforare i limiti.")
            return

        man = dgt(f"Inserisci i semitoni per la trasposizione manuale (da {limite_inf} a +{limite_sup}): ", kind="i", imin=limite_inf, imax=limite_sup)
        if man is not None:
            part.transpose(man, inPlace=True)
            segno_man = "+" if man > 0 else ""
            print(f"Traccia trasposta di {segno_man}{man} semitoni.")
        else:
            print("Trasposizione annullata.")
def visualizzatore_interattivo(output_lines, part):
    tot_righe = len(output_lines)
    idx = 0
    play_continuo = False
    current_sound_type = 2 # Default: Synth/Flauto
    sound_names = {1: "Chitarra", 2: "Synth (Flauto)"}
    
    with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
        bpm = float(json.load(f).get('default_bpm', 60))

    print("\nComandi: [Z/X] Naviga, [+] [-] [=] BPM, [T] Trasponi, [SPAZIO] Play, [P] Strumento, [INVIO] Continuo, [ESC] Esci")
    
    from GBUtils import dgt
    last_printed_bpm = None
    
    while True:
        riga = output_lines[idx]
        match_num = re.search(r"B(\d+)", riga)
        num_battuta = int(match_num.group(1)) if match_num else 0
        
        # Aggiorna il BPM se la riga contiene un cambio
        match_bpm = re.search(r"\[BPM:\s*([\d\.]+)\]", riga)
        if match_bpm:
            bpm = float(match_bpm.group(1))
            
        bpm_display = ""
        # Stampa il BPM solo se è stato cambiato manualmente e non è già nella riga
        if bpm != last_printed_bpm and not match_bpm:
            if float(bpm).is_integer():
                bpm_display = f" (BPM:{int(bpm)})"
            else:
                bpm_display = f" (BPM:{bpm:.1f})"
                
        sys.stdout.write(f"\r{' '*110}\r")
        sys.stdout.write(f"\r{riga}{bpm_display} > \r")
        sys.stdout.flush()
        
        last_printed_bpm = bpm
        
        k = ''
        if play_continuo:
            m = part.measure(num_battuta)
            dur_battuta = m.duration.quarterLength * (60.0 / bpm)
            
            play_battuta_audio(part, num_battuta, current_sound_type, bpm_override=bpm)
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
        
        if k == chr(27) or k == 'q' or k == 'esc': sd.stop(); break
        elif k == 'x' or k == 'right' or k == 'down': idx = min(idx + 1, tot_righe - 1)
        elif k == 'z' or k == 'left' or k == 'up': idx = max(idx - 1, 0)
        elif k == '+': bpm += 1
        elif k == '-': bpm = max(1, bpm - 1)
        elif k == '=':
            nuovo_bpm = dgt("\nNuovi BPM: ", kind='f', fmin=1, fmax=500)
            if nuovo_bpm: bpm = nuovo_bpm
        elif k == 't':
            esegui_trasposizione(part)
            # Dobbiamo rigenerare le linee di output
            output_lines.clear()
            output_lines.extend(genera_lista_eventi_per_battute(part))
            idx = 0
            # Reimposta print header
            print("\nComandi: [Z/X] Naviga, [+] [-] [=] BPM, [T] Trasponi, [SPAZIO] Play, [P] Strumento, [INVIO] Continuo, [ESC] Esci")
        elif k == ' ':
            sd.stop()
            play_battuta_audio(part, num_battuta, current_sound_type, bpm_override=bpm)
        elif k == 'p':
            current_sound_type = 1 if current_sound_type == 2 else 2
            print(f"\n[Audio] Preset cambiato: {sound_names[current_sound_type]}")
            time.sleep(0.5)
        elif k == '\r' or k == 'enter': play_continuo = True        
    print("\nUscita visualizzatore.")

def estrai_e_mostra_note(part, idx, tot, filepath):
    print("\nElaborazione battute...")
    output_lines = genera_lista_eventi_per_battute(part)
    if not output_lines: return
    bpm, time_sig, key_sig = get_metadata(part)
    print(f"\nAnalisi: {os.path.basename(filepath)} | Traccia {idx}/{tot}")
    print(f"BPM: {bpm} | Tempo: {time_sig} | Tonalità: {key_sig}\n" + "-"*40)
    visualizzatore_interattivo(output_lines, part)

def salva_txt(part, label, filepath, idx, tot):
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    out_name = f"{base_name}_{''.join([c for c in label if c.isalnum() or c in (' ','-','_')]).strip()}.txt"
    out_path = os.path.join(DEFAULT_MIDI_DIR, out_name)
    print(f"Esportazione in {out_path}...")
    lines = genera_lista_eventi_per_battute(part)
    bpm, ts, ks = get_metadata(part)
    header = ["MidiStudy (Chitabry Engine)", f"File: {os.path.basename(filepath)}", f"Traccia: {idx}/{tot} - {label}", f"BPM={bpm}, Tempo={ts}, Tonalità: {ks}", f"Nomenclatura: {get_nomenclatura().upper()}", "="*40, ""]
    try:
        with open(out_path, "w", encoding="utf-8") as f: f.write("\n".join(header + lines + ["", f"Totale Battute: {len(lines)}"]))
        print("Salvato.")
    except Exception as e: print(f"Errore: {e}")

def salva_pdf(part, label, filepath):
    import shutil
    from GBUtils import enter_escape
    
    # 1. Check if lilypond is in PATH
    lilypond_path = shutil.which("lilypond")
    if not lilypond_path:
        print("\n*** LilyPond non trovato nel sistema! ***")
        print("Per generare spartiti PDF, Chitabry necessita del motore grafico gratuito LilyPond.")
        print("Per installarlo:")
        print(" 1. Apri un terminale come Amministratore")
        print(" 2. Esegui il comando: winget install LilyPond.LilyPond")
        print(" 3. Oppure scaricalo da: https://lilypond.org/download.html")
        print("Una volta installato, riavvia Chitabry o il terminale per aggiornare i percorsi di sistema.")
        
        # Optionally allow them to say they just installed it
        scelta = enter_escape("\nHai appena installato LilyPond e vuoi riprovare? [INVIO=Sì, ESC=No]")
        if scelta:
            # Re-check (sometimes PATH changes don't propagate without a shell restart, but we try)
            lilypond_path = shutil.which("lilypond")
            if not lilypond_path:
                print("LilyPond non ancora rilevato. Riavvia Chitabry e riprova.")
                return
        else:
            return
            
    # 2. Configure music21 to use the found LilyPond
    from music21 import environment
    env = environment.UserSettings()
    env['lilypondPath'] = lilypond_path
    
    # 3. Insert Title Metadata for the PDF
    from music21 import metadata
    from Chitabry import VERSIONE
    
    if not part.metadata:
        part.metadata = metadata.Metadata()
        
    part.metadata.title = f"Traccia: {label}"
    part.metadata.composer = f"Chitabry v{VERSIONE.split(' ')[0]}"
    
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    out_name = f"{base_name}_{''.join([c for c in label if c.isalnum() or c in (' ','-','_')]).strip()}.pdf"
    out_path = os.path.join(DEFAULT_MIDI_DIR, out_name)
    
    print("\nGenerazione spartito PDF in corso con LilyPond...")
    print(f"Destinazione: {out_path}")
    print("Attendere, potrebbe richiedere alcuni secondi...")
    
    try:
        generated_path = part.write('lily.pdf')
        
        # move from temp directory to the target directory
        if os.path.exists(generated_path):
            shutil.move(generated_path, out_path)
            print("Salvato.")
        else:
            print("Errore: Il file PDF non è stato generato da music21/LilyPond.")
            
    except Exception as e:
        print(f"Errore durante l'esportazione PDF: {e}")

def salva_menu(part, label, filepath, idx, tot):
    print(f"\n--- Salva Traccia {idx}/{tot}: {label} ---")
    opzioni = {
        "Testo": "Salva in formato testo semplice (Standard Chitabry)",
        "PDF": "Salva spartito grafico (Richiede LilyPond)"
    }
    s = menu(d=opzioni, p="Formato di esportazione [INVIO per annullare] > ", show=True)
    if s == "Testo":
        salva_txt(part, label, filepath, idx, tot)
    elif s == "PDF":
        salva_pdf(part, label, filepath)

def send_mci_command(command):
    buffer_size = 256
    buffer = ctypes.create_unicode_buffer(buffer_size)
    error_code = ctypes.windll.winmm.mciSendStringW(command, buffer, buffer_size, None)
    return error_code

def studia_traccia(part, label, filepath, idx, tot):
    while True:
        print(f"\n--- Traccia {idx}/{tot}: {label} ---")
        opzioni = {
            "Ascolta": "Riproduce la traccia (Player MCI)",
            "Visualizza": "Mostra gli eventi (Battute/Audio)",
            "Trasponi": "Cambia tonalità (-24/+24 semitoni)",
            "Salva": "Esporta traccia (TXT, ABC, PDF)"
        }
        s = menu(d=opzioni, p="Azione [INVIO per Indietro] > ", show=True)
        if not s: cleanup_temp_files(); break
        elif s == "Ascolta": play_preview(part)
        elif s == "Visualizza": estrai_e_mostra_note(part, idx, tot, filepath)
        elif s == "Trasponi": esegui_trasposizione(part)
        elif s == "Salva": salva_menu(part, label, filepath, idx, tot)

def check_midi_folder_cleanup():
    import datetime
    from GBUtils import enter_escape
    from config import impostazioni, salva_impostazioni
    
    if not os.path.exists(DEFAULT_MIDI_DIR):
        return
        
    oggi = datetime.datetime.now()
    ultimo_controllo_str = impostazioni.get("ultimo_controllo_pulizia_midi")
    if ultimo_controllo_str:
        try:
            ultimo_controllo = datetime.datetime.strptime(ultimo_controllo_str, "%Y-%m-%d")
            if (oggi - ultimo_controllo).days < 30:
                return
        except ValueError:
            pass
            
    un_anno_fa = oggi - datetime.timedelta(days=365)
    
    file_vecchi = []
    
    for root, _, files in os.walk(DEFAULT_MIDI_DIR):
        for f in files:
            filepath = os.path.join(root, f)
            try:
                mtime = os.path.getmtime(filepath)
                mtime_dt = datetime.datetime.fromtimestamp(mtime)
                if mtime_dt < un_anno_fa:
                    file_vecchi.append((f, filepath, mtime_dt))
            except Exception:
                pass
                
    if not file_vecchi:
        # Se non ci sono file vecchi, segniamo comunque che abbiamo fatto il controllo oggi
        impostazioni["ultimo_controllo_pulizia_midi"] = oggi.strftime("%Y-%m-%d")
        salva_impostazioni()
        return
        
    print("\n" + "="*50)
    print("ATTENZIONE: MANUTENZIONE CARTELLA MIDI")
    print("="*50)
    print(f"Sono stati trovati {len(file_vecchi)} file nella cartella 'midi' non modificati da oltre un anno.")
    
    scelta = enter_escape("Desideri fare pulizia e cancellarli definitivamente? [INVIO=Sì, ESC=No]")
    
    if scelta:
        print("\nElenco dei file che verranno ELIMINATI PERMANENTEMENTE:")
        for nome, path, mtime in file_vecchi:
            print(f"- {nome} (Ultima modifica: {mtime.strftime('%Y-%m-%d')})")
            
        conferma = enter_escape("\nSei ASSOLUTAMENTE SICURO di voler eliminare questi file? [INVIO=Procedi, ESC=Annulla]")
        if conferma:
            cancellati = 0
            for _, path, _ in file_vecchi:
                try:
                    os.remove(path)
                    cancellati += 1
                except Exception as e:
                    print(f"Impossibile cancellare {path}: {e}")
            print(f"\nPulizia completata. {cancellati} file eliminati.")
        else:
            print("\nOperazione annullata.")
    else:
        print("\nOperazione rimandata di 30 giorni.")
        
    print("="*50 + "\n")
    
    # Aggiorna la data dell'ultimo controllo in ogni caso
    impostazioni["ultimo_controllo_pulizia_midi"] = oggi.strftime("%Y-%m-%d")
    salva_impostazioni()

def MidiStudyMain():
    _header()
    cleanup_temp_files()
    while True:
        f = seleziona_file_midi()
        if not f:
            cleanup_temp_files()
            break
        analizza_tracce(f)
    print("\nRitorno a Chitabry...")
