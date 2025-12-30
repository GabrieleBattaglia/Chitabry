# MidiStudy.py
# Modulo per l'analisi e lo studio di file MIDI
# Parte del progetto Chitabry
# Autore: Gabriele & Gemini (Stella)
# Data creazione: 30 Dicembre 2025

import os
import sys
from music21 import converter, midi, stream, note, chord
from GBUtils import dgt, menu, key
import time

# Costanti
MIDISTUDY_VERSION = "0.1 (Alpha)"
# La cartella 'midi' si trova nella stessa directory di questo script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_MIDI_DIR = os.path.join(BASE_DIR, "midi")

def _header():
    print("\n" + "="*40)
    print(f"MidiStudy - Analisi Musicale v{MIDISTUDY_VERSION}")
    print("="*40 + "\n")

def seleziona_file_midi():
    """Scansiona la cartella e chiede all'utente di scegliere un file."""
    if not os.path.exists(DEFAULT_MIDI_DIR):
        print(f"Errore: La cartella {DEFAULT_MIDI_DIR} non esiste.")
        return None

    files = [f for f in os.listdir(DEFAULT_MIDI_DIR) if f.lower().endswith(('.mid', '.midi'))]
    
    if not files:
        print(f"Nessun file MIDI trovato in: {DEFAULT_MIDI_DIR}")
        print("Copia i tuoi file .mid in quella cartella e riprova.")
        return None

    # Creiamo un dizionario per il menu {indice: nome_file}
    d_files = {str(i+1): f for i, f in enumerate(files)}
    
    print(f"File trovati in {DEFAULT_MIDI_DIR}:")
    scelta = menu(d=d_files, show=True, numbered=True, p="Scegli il file da analizzare: ")
    
    if scelta:
        return os.path.join(DEFAULT_MIDI_DIR, d_files[scelta])
    return None

def analizza_tracce(filepath):
    """Carica il MIDI e mostra le tracce disponibili."""
    print(f"\nCaricamento di: {os.path.basename(filepath)}...")
    print("Attendere, analisi in corso (richiede music21)...")
    
    try:
        # Carichiamo il file
        s = converter.parse(filepath)
        
        # In music21 le tracce sono 'Parts'
        parti = s.parts
        if not parti:
            # Se non ci sono parti, proviamo a vedere se è un unico stream
            print("Nessuna traccia (Part) distinta trovata. Analizzo lo stream unico.")
            parti = [s]

        d_tracce = {}
        for i, p in enumerate(parti):
            nome = p.partName if p.partName else f"Traccia {i}"
            num_note = len(p.flatten().notes)
            d_tracce[str(i+1)] = f"{nome} ({num_note} note)"

        while True:
            print(f"\n--- Tracce in {os.path.basename(filepath)} ---")
            scelta = menu(d=d_tracce, show=True, numbered=True, p="Scegli la traccia da studiare [INVIO per tornare]: ")
            
            if not scelta:
                break
            
            # Qui andremo alla funzione di studio della traccia specifica
            studia_traccia(parti[int(scelta)-1], d_tracce[scelta], filepath)
            
    except Exception as e:
        print(f"Errore durante l'analisi del file: {e}")

def play_preview(part):
    """
    Salva la parte in un file MIDI temporaneo e lo apre con il player di sistema.
    """
    temp_file = os.path.join(DEFAULT_MIDI_DIR, "preview_temp.mid")
    print(f"Generazione anteprima in {temp_file}...")
    try:
        part.write('midi', fp=temp_file)
        print("Avvio riproduzione (chiudi il player per continuare)...")
        os.startfile(temp_file)
    except Exception as e:
        print(f"Errore durante la riproduzione: {e}")

def salva_su_file(part, label, filename_midi):
    """Esporta la lista delle note su un file di testo."""
    # Costruzione nome file output
    base_name = os.path.splitext(os.path.basename(filename_midi))[0]
    safe_label = "".join([c for c in label if c.isalnum() or c in (' ', '-', '_')]).strip()
    out_name = f"{base_name}_{safe_label}.txt"
    out_path = os.path.join(DEFAULT_MIDI_DIR, out_name)
    
    print(f"Esportazione in {out_path}...")
    
    # Riutilizziamo la logica di estrazione (un po' duplicata, ma per ora va bene per non rifattorizzare tutto)
    # TODO: Rifattorizzare estrazione in una funzione che restituisce una lista, usata sia da display che da save.
    
    elementi = part.flatten().notesAndRests
    output_lines = []
    nota_corrente = None
    durata_accumulata = 0.0
    
    output_lines.append(f"Analisi Traccia: {label}")
    output_lines.append(f"File Origine: {filename_midi}")
    output_lines.append("-" * 30)

    for el in elementi:
        if isinstance(el, note.Note):
            tie = el.tie
            if tie is None or tie.type == 'start':
                if nota_corrente:
                     txt_dur = get_duration_text(durata_accumulata)
                     output_lines.append(f"{nota_corrente} ({txt_dur})")
                nome = el.nameWithOctave.replace('-', 'b')
                nota_corrente = nome
                durata_accumulata = el.duration.quarterLength
                if tie is None:
                    txt_dur = get_duration_text(durata_accumulata)
                    output_lines.append(f"{nota_corrente} ({txt_dur})")
                    nota_corrente = None
                    durata_accumulata = 0.0
            elif tie.type == 'continue' or tie.type == 'stop':
                if nota_corrente: durata_accumulata += el.duration.quarterLength
                if tie.type == 'stop':
                    txt_dur = get_duration_text(durata_accumulata)
                    output_lines.append(f"{nota_corrente} ({txt_dur})")
                    nota_corrente = None
                    durata_accumulata = 0.0
        elif isinstance(el, chord.Chord):
            nome = el.root().nameWithOctave.replace('-', 'b') + " (Accordo)"
            dur = el.duration.quarterLength
            output_lines.append(f"{nome} ({get_duration_text(dur)})")
        elif isinstance(el, note.Rest):
            dur = el.duration.quarterLength
            if dur > 0.1:
                output_lines.append(f"PAUSA ({get_duration_text(dur)})")

    try:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write("\n".join(output_lines))
        print("Salvataggio completato.")
    except Exception as e:
        print(f"Errore salvataggio file: {e}")

def studia_traccia(part, label, filepath):
    """Logica per analizzare una singola traccia."""
    while True:
        print(f"\n--- Studio Traccia: {label} ---")
        scelta = menu(d={
            "a": "Ascolta anteprima (Player di sistema)",
            "e": "Estrai note (Testo a schermo)",
            "s": "Salva analisi su file TXT",
            "x": "Torna alla lista tracce"
        }, p="Azione > ", show=True)

        if scelta == "x" or scelta is None:
            break
        
        elif scelta == "a":
            play_preview(part)
            
        elif scelta == "e":
            estrai_e_mostra_note(part)
            
        elif scelta == "s":
            salva_su_file(part, label, filepath)

def get_duration_text(q_len):
    """Converte la quarterLength (float) in testo frazionario."""
    # Tolleranza per ritmi imperfetti (quantizzazione leggera)
    def is_close(a, b, tol=0.05):
        return abs(a - b) < tol

    if is_close(q_len, 4.0): return "1/1 (Intero)"
    if is_close(q_len, 3.0): return "3/4 (Metà puntata)"
    if is_close(q_len, 2.0): return "1/2 (Metà)"
    if is_close(q_len, 1.5): return "3/8 (Quarto puntato)"
    if is_close(q_len, 1.0): return "1/4 (Quarto)"
    if is_close(q_len, 0.75): return "3/16 (Ottavo puntato)"
    if is_close(q_len, 0.5): return "1/8 (Ottavo)"
    if is_close(q_len, 0.25): return "1/16 (Sedicesimo)"
    
    # Terzine (approssimate)
    if is_close(q_len, 1.0/3.0): return "1/12 (Terzina di 1/8)"
    if is_close(q_len, 2.0/3.0): return "1/6 (Terzina di 1/4)"
    
    # Fallback numerico formattato
    return f"{q_len:.2f} QL"

def estrai_e_mostra_note(part):
    """
    Estrae note e pause dalla traccia, gestisce le legature
    e presenta una lista leggibile.
    """
    print("\nElaborazione melodia...")
    
    # Appiattisce la struttura (rimuove misure)
    # notesAndRests recupera sia Note che Pause
    elementi = part.flatten().notesAndRests
    
    # Lista output finale
    output_lines = []
    
    # Variabili per gestire le note legate (Tie)
    nota_corrente = None
    durata_accumulata = 0.0
    
    for el in elementi:
        # --- GESTIONE NOTE ---
        if isinstance(el, note.Note):
            # Controllo Legature (Tie)
            tie = el.tie
            
            # Caso 1: Inizio di una nota (o nota singola)
            if tie is None or tie.type == 'start':
                # Se c'era una nota precedente in sospeso (errore nel MIDI?), chiudiamola
                if nota_corrente:
                     txt_dur = get_duration_text(durata_accumulata)
                     output_lines.append(f"{nota_corrente} ({txt_dur})")
                
                # Nuova nota
                # Usa notazione latina se preferito (per ora uso standard music21 + replace)
                nome = el.nameWithOctave.replace('-', 'b')
                # Mappatura rapida Inglese -> Latino (base) se necessario
                # Per ora mantengo C4, D#5 come richiesto standard, ma posso convertire
                
                nota_corrente = nome
                durata_accumulata = el.duration.quarterLength
                
                if tie is None: # Nota singola, finita subito
                    txt_dur = get_duration_text(durata_accumulata)
                    output_lines.append(f"{nota_corrente} ({txt_dur})")
                    nota_corrente = None
                    durata_accumulata = 0.0
            
            # Caso 2: Continuazione o Fine legatura
            elif tie.type == 'continue' or tie.type == 'stop':
                if nota_corrente: # Dovrebbe essere la stessa nota
                    durata_accumulata += el.duration.quarterLength
                
                if tie.type == 'stop':
                    # Fine legatura, scriviamo
                    txt_dur = get_duration_text(durata_accumulata)
                    output_lines.append(f"{nota_corrente} ({txt_dur})")
                    nota_corrente = None
                    durata_accumulata = 0.0

        # --- GESTIONE ACCORDI (Chord) ---
        elif isinstance(el, chord.Chord):
            # Per ora prendiamo solo la nota più acuta (melodia)
            # O indichiamo che è un accordo
            nome = el.root().nameWithOctave.replace('-', 'b') + " (Accordo)"
            dur = el.duration.quarterLength
            output_lines.append(f"{nome} ({get_duration_text(dur)})")

        # --- GESTIONE PAUSE (Rest) ---
        elif isinstance(el, note.Rest):
            # Anche le pause possono essere legate, ma è raro nei MIDI semplici.
            # Semplifichiamo trattandole singolarmente
            dur = el.duration.quarterLength
            # Ignoriamo pause piccolissime (spesso rumore di quantizzazione)
            if dur > 0.1:
                output_lines.append(f"PAUSA ({get_duration_text(dur)})")

    # --- PRESENTAZIONE RISULTATO ---
    if not output_lines:
        print("Nessuna nota trovata in questa traccia.")
        return

    print(f"\nTrovati {len(output_lines)} eventi melodici.")
    
    # Costruiamo il dizionario per menu()
    # Chiave: numero progressivo (stringa), Valore: linea di testo
    d_note = {str(i+1): linea for i, linea in enumerate(output_lines)}
    
    # Usiamo menu() come visualizzatore paginato
    # ntf (Not Found) è vuoto perché non ci aspettiamo input reali se non per navigare
    menu(d=d_note, show=True, numbered=True, pager=20, 
         p="Visualizzazione note (scrivi numero per dettaglio o INVIO per uscire): ", 
         ntf="")
    
    print("\nFine lettura.")

def MidiStudyMain():
    """
    Punto di ingresso principale per il modulo MidiStudy.
    """
    _header()
    
    while True:
        scelta = menu(d={"1": "Seleziona un file MIDI", "x": "Torna a Chitabry"}, 
                      p="MidiStudy > ", show=True)
        
        # Esce se preme 'x', ESC (None) o se preme INVIO a vuoto (None)
        if scelta == "x" or scelta is None:
            break
        
        elif scelta == "1":
            file_scelto = seleziona_file_midi()
            if file_scelto:
                analizza_tracce(file_scelto)
    
    print("\n[MidiStudy] Chiusura modulo e ritorno a Chitabry...")
    return
