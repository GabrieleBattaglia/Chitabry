# gioca_suono.py
# Modulo per l'ear training di Chitabry (Gioco delle note e delle frequenze)

from music21 import pitch
from GBUtils import dgt, menu, key, enter_escape
import GBAudio
import time
import random
from datetime import datetime

def avvia_gioco(impostazioni, get_nota, NOTE_LATINE, NOTE_STD, NOTE_ANGLO, on_save_callback):

    print("\n--- Gioca col Suono ---")
    
    # 1. Scelta Tipo Gioco
    scelta_tipo = menu(d={"n": "Note", "f": "Frequenze"}, keyslist=True, show=True, ntf="Scelta non valida", p="Scegli il tipo di gioco: ")
    if not scelta_tipo:
        print("Uscita dal gioco.")
        return

    # 2. Impostazioni gioco
    include_diesis = False
    if scelta_tipo == 'n':
        include_diesis = enter_escape("Includere le note alterate (diesis/bemolli)? [INVIO per SI, ESC per NO]: ")

    # Setup
    num_rounds = 30
    score_totale = 0.0
    start_time = time.time()
    
    # Range C2 - C7
    midi_min = 36 # C2
    midi_max = 96 # C7
    
    suono_attivo_key = 'suono_1'
    
    poly_player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=1)
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    poly_player.start()
    
    if scelta_tipo == 'n':
        print("\nLimiti di gioco: da C2 a C7 (Note)")
    else:
        print("\nLimiti di gioco: da 65 Hz a 2093 Hz (Frequenze)")
        
    print("Comandi: [Qualsiasi tasto] Ascolta | [Invio] Rispondi | [Spazio] Cambia Suono | [ESC] Esci")
    
    try:
        round_idx = 1
        last_result_str = "Nuova partita"
        
        while round_idx <= num_rounds:
            # Genera obiettivo
            if scelta_tipo == 'n':
                if include_diesis:
                    target_midi = random.randint(midi_min, midi_max)
                else:
                    # Solo note naturali (C, D, E, F, G, A, B)
                    natural_pcs = [0, 2, 4, 5, 7, 9, 11]
                    valid_midis = [m for m in range(midi_min, midi_max + 1) if m % 12 in natural_pcs]
                    target_midi = random.choice(valid_midis)
                target_freq = 440.0 * (2.0 ** ((target_midi - 69) / 12.0))
            else: # Frequenze
                target_freq = float(random.randint(65, 2093)) # C2 ~ 65Hz, C7 ~ 2093Hz
            
            # Rendering audio
            def play_target():
                s = impostazioni[suono_attivo_key]
                vol = s.get('volume', 0.35)
                if 'pluck_hardness' in s:
                    dur = s.get('dur_accordi', 9.0)
                    renderer.set_params(target_freq, dur, vol, 0.0, 
                                        pluck_hardness=s.get('pluck_hardness', 0.6), 
                                        damping_factor=s.get('damping_factor', 0.997),
                                        pick_position=s.get('pick_position', 0.15), 
                                        brightness=s.get('brightness', 0.4))
                else:
                    dur = 2.0
                    renderer.set_params(target_freq, dur, vol, 0.0, kind=s.get('kind', 1), adsr_list=s.get('adsr', [0,0,0,0]))
                
                note_audio = renderer.render()
                if note_audio.size > 0:
                    mono_audio = note_audio[:, 0] / renderer.pan_l if renderer.pan_l != 0 else note_audio[:, 0]
                    poly_player.pluck(string_idx=0, audio_mono=mono_audio)

            play_target() # Suona subito all'inizio del round
            
            # Sottociclo per ogni round
            round_completed = False
            while not round_completed:
                prompt_base = f"({round_idx}/{num_rounds})"
                if last_result_str == "Nuova partita":
                    print(f"\r{last_result_str}, {prompt_base} > {' '*5}\r", end="", flush=True)
                else:
                    print(f"\r{last_result_str} {prompt_base} > {' '*5}\r", end="", flush=True)
                
                comando = key()
                
                if comando is None or comando == chr(27): # ESC
                    print("\nEsercizio concluso prematuramente. Il punteggio non sarà salvato.")
                    return
                    
                if comando == ' ':
                    suono_attivo_key = 'suono_2' if suono_attivo_key == 'suono_1' else 'suono_1'
                    print(f"\r[Suono: {impostazioni[suono_attivo_key]['descrizione']}]{' '*20}\r", end="", flush=True)
                elif comando == '\r' or comando == '\n':
                    poly_player.mute(0)
                    print("\n", end="") # Vai a capo per la risposta
                    
                    if scelta_tipo == 'n':
                        ans_str = dgt("Inserisci la nota (es. DO4 o C4): ", kind="s").strip().upper()
                        if not ans_str: continue
                            
                        # Extract octave
                        if not ans_str[-1].isdigit():
                            print("Errore: Includi l'ottava (es. DO4).")
                            continue
                            
                        ottava = ans_str[-1]
                        nota_nome = ans_str[:-1]
                        
                        # Translate to std
                        if impostazioni['nomenclatura'] == 'latino':
                            mappa_inversa = dict(zip(NOTE_LATINE, NOTE_STD))
                        else:
                            mappa_inversa = dict(zip(NOTE_ANGLO, NOTE_STD))
                            
                        if nota_nome not in mappa_inversa:
                            print(f"Nota non valida in {impostazioni['nomenclatura']}.")
                            continue
                            
                        nota_std = mappa_inversa[nota_nome]
                        ans_pitch = pitch.Pitch(nota_std + ottava)
                        ans_midi = ans_pitch.midi
                        
                        # Calcola punteggio
                        diff = abs(target_midi - ans_midi)
                        if diff == 0:
                            punteggio_round = 100.0
                            segno = ""
                        else:
                            punteggio_round = max(0.0, 100.0 - (diff * (100.0 / 24.0)))
                            segno = "+" if ans_midi > target_midi else "-"
                            
                        score_totale += punteggio_round
                        media_score = score_totale / round_idx
                        target_name = get_nota(pitch.Pitch(midi=target_midi).nameWithOctave.replace('-', 'b'))
                        
                        if diff == 0:
                            last_result_str = f"R:{ans_str}, 0, C:{target_name} S:{media_score:.0f}%,"
                        else:
                            last_result_str = f"R:{ans_str}, {segno}{diff}, C:{target_name} S:{media_score:.0f}%,"
                            
                    else: # Frequenze
                        ans_str = dgt("Inserisci la frequenza in Hz: ", kind="f")
                        if ans_str is None: continue
                            
                        diff = abs(target_freq - ans_str)
                        if diff <= 10.0:
                            punteggio_round = 100.0
                        elif diff <= 100.0:
                            punteggio_round = 100.0 - ((diff - 10.0) * (100.0 / 90.0))
                        else:
                            punteggio_round = 0.0
                            
                        score_totale += punteggio_round
                        media_score = score_totale / round_idx
                        segno = "+" if ans_str > target_freq else "-"
                        
                        if diff == 0:
                            last_result_str = f"R:{ans_str:.0f}, 0, C:{target_freq:.0f} S:{media_score:.0f}%,"
                        else:
                            last_result_str = f"R:{ans_str:.0f}, {segno}{diff:.0f}, C:{target_freq:.0f} S:{media_score:.0f}%,"
                            
                    round_completed = True
                    round_idx += 1
                else:
                    play_target()
                    
    finally:
        poly_player.stop()
        
    # --- Fine Gioco: Risultati e Classifica ---
    end_time = time.time()
    durata_sec = end_time - start_time
    minuti = int(durata_sec // 60)
    secondi = int(durata_sec % 60)
    millisecondi = int((durata_sec - int(durata_sec)) * 1000)
    durata_str = f"{minuti:02d}.{secondi:02d}.{millisecondi:03d}"
    
    precisione_finale = score_totale / num_rounds
    
    print("\n==================================")
    print("        GIOCO CONCLUSO!")
    print("==================================")
    print(f"Precisione: {precisione_finale:.2f}%")
    print(f"Tempo: {durata_str}")
    
    # Gestione Classifica
    tipo_classifica = 'classifica_note' if scelta_tipo == 'n' else 'classifica_freq'
    if tipo_classifica not in impostazioni:
        impostazioni[tipo_classifica] = []
        
    classifica = impostazioni[tipo_classifica]
    
    # Verifica se il punteggio entra in classifica
    entra_in_classifica = False
    if len(classifica) < 30:
        entra_in_classifica = True
    else:
        peggior_record = classifica[-1]
        if precisione_finale > peggior_record['precisione'] or (precisione_finale == peggior_record['precisione'] and durata_sec < peggior_record['durata_sec']):
            entra_in_classifica = True

    if entra_in_classifica:
        print("\nComplimenti! Sei entrato nella Top 30 della Hall of Fame!")
        nome_giocatore = dgt("Inserisci il tuo nome (max 20 car): ", kind="s").strip()
        if not nome_giocatore: nome_giocatore = "Anonimo"
        nome_giocatore = nome_giocatore[:20].title()
        
        nuovo_record = {
            'nome': nome_giocatore,
            'precisione': precisione_finale,
            'durata_sec': durata_sec,
            'durata_str': durata_str,
            'data': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        classifica.append(nuovo_record)
        
        # Ordina: decrescente per precisione, crescente per durata
        classifica.sort(key=lambda x: (-x['precisione'], x['durata_sec']))
        
        # Mantieni solo i primi 30
        if len(classifica) > 30:
            classifica = classifica[:30]
            
        impostazioni[tipo_classifica] = classifica
        on_save_callback(impostazioni)
    
    print("\n--- CLASSIFICA ---")
    for i, r in enumerate(classifica):
        print(f"{i+1:2d}. {r['nome'][:20]:<20} | Prec: {r['precisione']:6.2f}% | Tempo: {r['durata_str']} | ({r['data']})")
    
    key("\nPremi un tasto per tornare al menu...")

