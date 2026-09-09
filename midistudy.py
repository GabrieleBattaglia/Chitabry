# MidiStudy, analisi e studio dei file MIDI e ABC dentro Chitabry.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Revisione 1 del 2026-09-09: le impostazioni si leggono da config invece di
# rileggere il file da disco a ogni nota; la cartella midi sta accanto al
# programma e si crea da sola; la versione arriva da versione.py invece di
# rieseguire il modulo principale; le eccezioni catturate sono quelle che si
# sanno nominare, e dove music21 puo' sollevare di tutto lo si dice.

import ctypes
import datetime
import os
import re
import subprocess
import sys
import time
from fractions import Fraction

import mido
import numpy as np
import sounddevice as sd
from GBUtils import dgt, enter_escape, key, menu
from music21 import chord, converter, meter, note, stream, tempo
from music21 import key as m21key
from music21.exceptions21 import Music21Exception

import config
import GBAudio
import suoni
from versione import VERSIONE

DEFAULT_MIDI_DIR = config.CARTELLA_MIDI
TEMP_PREVIEW_FILE = os.path.join(DEFAULT_MIDI_DIR, "preview_temp.mid")
# Cio' che mido e music21 sollevano su un file MIDI malformato
ERRORI_MIDI = (OSError, EOFError, KeyError, ValueError, IndexError)

def _header():
    print(f"MidiStudy, analisi musicale, versione {VERSIONE}.")


def cleanup_temp_files():
    """Rimuove i file temporanei creati durante la sessione."""
    try:
        if os.path.exists(TEMP_PREVIEW_FILE):
            os.remove(TEMP_PREVIEW_FILE)
    except OSError as e:
        print(f"File temporaneo non rimosso: {e}")


def get_nomenclatura():
    """La nomenclatura scelta nelle impostazioni di Chitabry."""
    return config.impostazioni.get('nomenclatura', 'latino')

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
    """Elenca i file della cartella midi con la durata e chiede quale analizzare.
    La cartella si crea se manca: chi scarica il pacchetto compilato non ce l'ha."""
    try:
        os.makedirs(DEFAULT_MIDI_DIR, exist_ok=True)
    except OSError as e:
        print(f"Impossibile creare la cartella {DEFAULT_MIDI_DIR}: {e}")
        return None
    files = [f for f in os.listdir(DEFAULT_MIDI_DIR) if f.lower().endswith(('.mid', '.midi', '.abc'))]
    if not files:
        print(f"Nessun file musicale trovato in {DEFAULT_MIDI_DIR}. Copia li' i file MIDI o ABC da studiare.")
        return None
    d_files = {}
    for f in files:
        filepath = os.path.join(DEFAULT_MIDI_DIR, f)
        dur_str = "??:??"
        if f.lower().endswith(('.mid', '.midi')):
            try:
                durata = mido.MidiFile(filepath).length
                dur_str = f"{int(durata // 60):02d}:{int(durata % 60):02d}"
            except ERRORI_MIDI:
                dur_str = "durata sconosciuta"
        d_files[f] = dur_str
    scelta = menu(d=d_files, show=True, numbered=False, p="Scegli il file da analizzare [INVIO per annullare]: ")
    if scelta:
        return os.path.join(DEFAULT_MIDI_DIR, scelta)
    return None
def gestisci_tools_abc(filepath):
    """La suite abcMIDI, se l'utente ne ha indicato la cartella."""
    abc_dir = config.impostazioni.get('abc_tools_dir', '')
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

        config.impostazioni['abc_tools_dir'] = abc_dir
        config.salva_modifiche()
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
        print(f"\nStrumenti ABC (cartella {abc_dir}).")
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
                time.sleep(2)
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
        except OSError as e:
            print(f"Strumento non avviato: {e}")

def analizza_tracce(filepath):
    """Carica il MIDI e mostra le opzioni principali del brano."""
    print(f"\nCaricamento di: {os.path.basename(filepath)}...")
    print("Attendere, analisi in corso (richiede music21)...")
    try:
        s = converter.parse(filepath)

        while True:
            bpm, time_sig, key_sig = get_metadata(s)
            print(f"\nAnalisi del brano {os.path.basename(filepath)}.")
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

                print("\nScegli le tracce (selezione multipla).")
                print("Comandi: <num> Seleziona/Deseleziona | 0 Fatto | ? Info | [INVIO] Annulla")
                for i, p in enumerate(parti):
                    nome = p.partName if p.partName else f"Traccia {i}"
                    num_note = len(p.flatten().notes)
                    print(f"  {i+1}: {nome} ({num_note} note)")

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
                            idx_part = next(iter(selected_indices))
                            traccia_finale = parti[idx_part]
                            nome_finale = parti[idx_part].partName if parti[idx_part].partName else f"Traccia {idx_part}"
                        else:
                            traccia_finale = stream.Score()
                            nomi = []
                            for idx in sorted(selected_indices):
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
    except Exception as e:  # noqa: BLE001 - music21 e mido sollevano di tutto su un file scelto dall'utente, e qui si sta solo leggendo
        print(f"Errore durante l'analisi del file: {e}")

def _durata_midi(percorso, part):
    """Durata in secondi del file appena scritto. Se mido non lo legge, per
    esempio per una tonalita' con otto diesis, si stima dalla partitura."""
    try:
        return mido.MidiFile(percorso).length
    except ERRORI_MIDI:
        try:
            bpm_val = float(get_metadata(part)[0])
        except ValueError:
            bpm_val = 120.0
        return float(part.duration.quarterLength) * (60.0 / bpm_val)


def play_preview(part):
    """Salva la parte in un file MIDI temporaneo e lo riproduce con il player MCI di Windows."""
    try:
        part.write('midi', fp=TEMP_PREVIEW_FILE)
    except (Music21Exception, OSError) as e:
        print(f"Impossibile preparare l'anteprima MIDI: {e}")
        return
    durata_sec = _durata_midi(TEMP_PREVIEW_FILE, part)
    print(f"Riproduzione in corso, durata {durata_sec:.1f} secondi. Premi ESC o Q per interrompere.")
    send_mci_command("close preview_player")
    if send_mci_command(f'open "{os.path.abspath(TEMP_PREVIEW_FILE)}" type sequencer alias preview_player') != 0:
        print("Il player MCI di Windows non ha aperto il file: riproduzione non disponibile.")
        return
    send_mci_command('play preview_player')
    start_time = time.time()
    try:
        while True:
            elapsed = time.time() - start_time
            if elapsed >= durata_sec + 0.5:
                break
            perc = min(100.0, (elapsed / durata_sec) * 100.0) if durata_sec > 0 else 0.0
            print(f"\r{int(elapsed // 60):02d}:{int(elapsed % 60):02d} | {perc:.1f}% > {' ' * 5}\r", end="", flush=True)
            k = key(attesa=0.3)
            if k and k.lower() in ('esc', 'q', chr(27)):
                print("\nRiproduzione interrotta.")
                break
    finally:
        send_mci_command("stop preview_player")
        send_mci_command("close preview_player")

def get_duration_concise(q_len):
    """Converte la quarterLength in notazione frazionaria reale (es. /4, 3/8, 5/16)."""
    f = Fraction(q_len / 4.0).limit_denominator(64)
    if f.numerator == 1: return f"/{f.denominator}"
    return f"{f.numerator}/{f.denominator}"

def formatta_evento(el, durata):
    """Restituisce la stringa formattata per Note o Accordi."""
    dur_str = get_duration_concise(durata)
    if isinstance(el, note.Note):
        nome = traduci_nota(el.nameWithOctave)
        return f"{nome} {dur_str}"
    if isinstance(el, chord.Chord):
        pitches = sorted(el.pitches)
        nomi_note = [traduci_nota(p.nameWithOctave) for p in pitches]
        block = "[" + " ".join(nomi_note) + "]"
        return f"{block} {dur_str}"
    if isinstance(el, note.Rest):
        if durata < 0.05: return None
        return f"PAUSA {dur_str}"
    return None

def get_metadata(part):
    """BPM, tempo e tonalita' della parte, come testi; N/A dove mancano."""
    bpm, time_sig, key_sig = "N/A", "4/4", "N/A"
    flat_part = part.flatten()
    ts = flat_part.getElementsByClass(meter.TimeSignature)
    if ts:
        time_sig = ts[0].ratioString
    ks = flat_part.getElementsByClass(m21key.KeySignature)
    if ks:
        try:
            key_sig = ks[0].asKey().name
        except Music21Exception:
            key_sig = f"{ks[0].sharps} accidenti"
    key_sig = key_sig.replace('-', 'b')
    mm = flat_part.getElementsByClass(tempo.MetronomeMark)
    if mm:
        try:
            bpm = str(mm[0].getQuarterBPM())
        except (Music21Exception, TypeError, ValueError):
            bpm = "N/A"
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
    except Exception:  # noqa: BLE001 - la quantizzazione di music21 puo' fallire in molti modi: si mostra la parte com'e'
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
    """Riproduce l'audio di una singola battuta con il suono 1 o 2 di Chitabry."""
    parametri = suoni.parametri_suono(f'suono_{tipo_suono}')
    bpm = float(config.impostazioni.get('default_bpm', 60))
    try:
        m = part.measure(numero_battuta)
        if not m:
            return
        mm = m.flatten().getElementsByClass(tempo.MetronomeMark)
        if mm:
            bpm = mm[0].getQuarterBPM()
        if bpm_override:
            bpm = float(bpm_override)
        renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
        q_dur = 60.0 / bpm
        segmenti = []
        for el in m.flatten().notesAndRests:
            dur_sec = el.duration.quarterLength * q_dur
            if dur_sec <= 0:
                continue
            if isinstance(el, note.Note):
                suoni.configura_renderer(renderer, GBAudio.note_to_freq(el.nameWithOctave), parametri, dur=dur_sec)
                buf = renderer.render()
                if buf.size > 0:
                    segmenti.append(buf)
            elif isinstance(el, chord.Chord):
                chord_buf = np.zeros((int(dur_sec * GBAudio.FS), 2), dtype=np.float32)
                for p in el.pitches:
                    suoni.configura_renderer(renderer, GBAudio.note_to_freq(p.nameWithOctave), parametri, dur=dur_sec)
                    n_buf = renderer.render()
                    if n_buf.size > 0:
                        min_l = min(len(chord_buf), len(n_buf))
                        chord_buf[:min_l] += n_buf[:min_l]
                mx = np.max(np.abs(chord_buf))
                if mx > 1.0:
                    chord_buf /= mx
                segmenti.append(chord_buf)
            elif isinstance(el, note.Rest):
                segmenti.append(np.zeros((int(dur_sec * GBAudio.FS), 2), dtype=np.float32))
        if segmenti:
            sd.play(np.concatenate(segmenti, axis=0), samplerate=GBAudio.FS, blocking=False)
    except Exception as e:  # noqa: BLE001 - music21 solleva di tutto su una battuta malformata, e qui si sta solo ascoltando
        print(f"Errore audio: {e}")

def esegui_trasposizione(part):

    # 1. Trova le note più basse e più alte per evitare out-of-bounds
    min_midi = 127
    max_midi = 0
    for n in part.flatten().notes:
        if isinstance(n, note.Note) and n.pitch.midi is not None:
            min_midi = min(min_midi, n.pitch.midi)
            max_midi = max(max_midi, n.pitch.midi)
        elif isinstance(n, chord.Chord):
            for p in n.pitches:
                if p.midi is not None:
                    min_midi = min(min_midi, p.midi)
                    max_midi = max(max_midi, p.midi)

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

        # A parità di accidenti, preferisce la trasposizione più vicina all'originale
        if accidentals < min_accidentals or (accidentals == min_accidentals and abs(i) < abs(best_interval)):
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

    bpm = float(config.impostazioni.get('default_bpm', 60))

    print("\nComandi: [Z/X] Naviga, [+] [-] [=] BPM, [T] Trasponi, [SPAZIO] Play, [P] Strumento, [INVIO] Continuo, [ESC] Esci")

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
                play_continuo = False

        if not k:
            k = key().lower()

        if k == chr(27) or k == 'q' or k == 'esc': sd.stop(); break
        if k == 'x' or k == 'right' or k == 'down': idx = min(idx + 1, tot_righe - 1)
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
    print(f"BPM: {bpm} | Tempo: {time_sig} | Tonalita': {key_sig}")
    visualizzatore_interattivo(output_lines, part)

def salva_txt(part, label, filepath, idx, tot):
    base_name = os.path.splitext(os.path.basename(filepath))[0]
    out_name = f"{base_name}_{''.join([c for c in label if c.isalnum() or c in (' ','-','_')]).strip()}.txt"
    out_path = os.path.join(DEFAULT_MIDI_DIR, out_name)
    print(f"Esportazione in {out_path}...")
    lines = genera_lista_eventi_per_battute(part)
    bpm, ts, ks = get_metadata(part)
    header = ["MidiStudy (Chitabry Engine)", f"File: {os.path.basename(filepath)}", f"Traccia: {idx}/{tot} - {label}", f"BPM={bpm}, Tempo={ts}, Tonalita': {ks}", f"Nomenclatura: {get_nomenclatura().upper()}", ""]
    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(header + lines + ["", f"Totale Battute: {len(lines)}"]))
        print("Salvato.")
    except OSError as e:
        print(f"Errore: {e}")

def salva_pdf(part, label, filepath):
    import shutil
    # 1. Check if lilypond is in PATH
    lilypond_path = shutil.which("lilypond")
    if not lilypond_path:
        print("\nLilyPond non trovato nel sistema.")
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

    from music21 import metadata

    if not part.metadata:
        part.metadata = metadata.Metadata()

    part.metadata.title = f"Traccia: {label}"
    part.metadata.composer = f"Chitabry v{VERSIONE}"

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

    except Exception as e:  # noqa: BLE001 - music21 e LilyPond falliscono in molti modi diversi
        print(f"Errore durante l'esportazione PDF: {e}")

def salva_menu(part, label, filepath, idx, tot):
    print(f"\nSalva traccia {idx}/{tot}: {label}.")
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
    """Manda un comando al sottosistema multimediale di Windows; zero vuol dire riuscito."""
    buffer_size = 256
    buffer = ctypes.create_unicode_buffer(buffer_size)
    return ctypes.windll.winmm.mciSendStringW(command, buffer, buffer_size, None)

def studia_traccia(part, label, filepath, idx, tot):
    while True:
        print(f"\nTraccia {idx}/{tot}: {label}.")
        opzioni = {
            "Ascolta": "Riproduce la traccia (Player MCI)",
            "Visualizza": "Mostra gli eventi (Battute/Audio)",
            "Trasponi": "Cambia tonalità (-24/+24 semitoni)",
            "Salva": "Esporta traccia (TXT, ABC, PDF)"
        }
        s = menu(d=opzioni, p="Azione [INVIO per Indietro] > ", show=True)
        if not s: cleanup_temp_files(); break
        if s == "Ascolta": play_preview(part)
        elif s == "Visualizza": estrai_e_mostra_note(part, idx, tot, filepath)
        elif s == "Trasponi": esegui_trasposizione(part)
        elif s == "Salva": salva_menu(part, label, filepath, idx, tot)

def check_midi_folder_cleanup():
    """Una volta al mese propone di cancellare dalla cartella midi i file fermi da piu' di un anno."""
    if not os.path.exists(DEFAULT_MIDI_DIR):
        return
    oggi = datetime.datetime.now()
    ultimo_controllo_str = config.impostazioni.get("ultimo_controllo_pulizia_midi")
    if ultimo_controllo_str:
        try:
            ultimo_controllo = datetime.datetime.strptime(ultimo_controllo_str, "%Y-%m-%d")
        except ValueError:
            ultimo_controllo = None
        if ultimo_controllo and (oggi - ultimo_controllo).days < 30:
            return
    un_anno_fa = oggi - datetime.timedelta(days=365)
    file_vecchi = []
    for root, _, files in os.walk(DEFAULT_MIDI_DIR):
        for f in files:
            filepath = os.path.join(root, f)
            try:
                mtime_dt = datetime.datetime.fromtimestamp(os.path.getmtime(filepath))
            except OSError:
                continue
            if mtime_dt < un_anno_fa:
                file_vecchi.append((f, filepath, mtime_dt))
    # Il controllo e' fatto oggi in ogni caso, qualunque sia la risposta
    config.impostazioni["ultimo_controllo_pulizia_midi"] = oggi.strftime("%Y-%m-%d")
    config.salva_modifiche()
    if not file_vecchi:
        return
    print("Attenzione: manutenzione della cartella midi.")
    print(f"Sono stati trovati {len(file_vecchi)} file nella cartella midi non modificati da oltre un anno.")
    if not enter_escape("Desideri fare pulizia e cancellarli definitivamente? [INVIO=Si', ESC=No]"):
        print("Operazione rimandata di 30 giorni.")
        return
    print("Elenco dei file che verranno eliminati definitivamente:")
    for nome, _path, mtime in file_vecchi:
        print(f"- {nome} (ultima modifica: {mtime.strftime('%Y-%m-%d')})")
    if not enter_escape("Sei assolutamente sicuro di voler eliminare questi file? [INVIO=Procedi, ESC=Annulla]"):
        print("Operazione annullata.")
        return
    cancellati = 0
    for _, path, _ in file_vecchi:
        try:
            os.remove(path)
            cancellati += 1
        except OSError as e:
            print(f"Impossibile cancellare {path}: {e}")
    print(f"Pulizia completata. {cancellati} file eliminati.")

def MidiStudyMain():
    _header()
    cleanup_temp_files()
    while True:
        f = seleziona_file_midi()
        if not f:
            cleanup_temp_files()
            break
        analizza_tracce(f)
    print("Ritorno a Chitabry...")
