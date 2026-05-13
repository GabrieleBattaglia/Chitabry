
# MIDI notes per accordatura standard (0 = E2 grave, 5 = E4 cantino)
DEFAULT_TUNING_MIDI = [40, 45, 50, 55, 59, 64] 

class InstrumentModel:
    def __init__(self, tuning_midi=None, num_frets=22):
        self.tuning_midi = tuning_midi if tuning_midi else DEFAULT_TUNING_MIDI
        self.num_strings = len(self.tuning_midi)
        self.num_frets = num_frets

class ScalePathfinder:
    def __init__(self, model, target_pc_list, root_pc):
        """
        model: InstrumentModel
        target_pc_list: list di interi (Pitch Class, 0=C, 1=C#...)
        root_pc: int (Pitch Class della tonica)
        """
        self.model = model
        self.target_pc_set = set(target_pc_list)
        self.root_pc = root_pc

    def _get_valid_positions(self, min_fret, max_fret):
        """Restituisce tutte le posizioni valide per le note della scala nei limiti."""
        positions = []
        for s in range(self.model.num_strings):
            for f in range(self.model.num_frets + 1):
                # Se la corda è a vuoto, va bene solo se min_fret <= 0
                if f == 0 and min_fret > 0:
                    continue
                # Se è premuta, deve essere nel range
                if f > 0 and not (min_fret <= f <= max_fret):
                    continue
                
                midi_note = self.model.tuning_midi[s] + f
                pc = midi_note % 12
                
                if pc in self.target_pc_set:
                    positions.append({
                        'string': s, 
                        'fret': f, 
                        'midi': midi_note, 
                        'pc': pc
                    })
        return positions

    def find_paths(self, min_fret, max_fret, priorita_caged=True):
        positions = self._get_valid_positions(min_fret, max_fret)
        if not positions:
            return []

        # Raggruppa posizioni per nota MIDI
        pos_by_midi = {}
        for p in positions:
            m = p['midi']
            if m not in pos_by_midi:
                pos_by_midi[m] = []
            pos_by_midi[m].append(p)
            
        unique_midis = sorted(list(pos_by_midi.keys()))
        
        paths = []
        
        def dfs(midi_idx, current_path):
            if midi_idx == len(unique_midis):
                paths.append(list(current_path))
                return
                
            next_midi = unique_midis[midi_idx]
            candidates = pos_by_midi[next_midi]
            
            for cand in candidates:
                if not current_path:
                    current_path.append(cand)
                    dfs(midi_idx + 1, current_path)
                    current_path.pop()
                else:
                    last_pos = current_path[-1]
                    # Vincolo fisico: per salire di pitch, 
                    # la corda deve essere uguale o più acuta (indice maggiore o uguale)
                    if cand['string'] >= last_pos['string']:
                        # Se cambia corda, non dovrebbe saltare corde se non necessario,
                        # ma le scale normali non lo fanno. Accettiamo string >= last_string
                        current_path.append(cand)
                        dfs(midi_idx + 1, current_path)
                        current_path.pop()

        dfs(0, [])
        
        scored_paths = []
        for path in paths:
            score, meta = self._score_and_finger_path(path, min_fret, max_fret, priorita_caged)
            scored_paths.append({'path': path, 'score': score, 'meta': meta})
            
        scored_paths.sort(key=lambda x: x['score'], reverse=True)
        return scored_paths

    def _score_and_finger_path(self, path, min_fret, max_fret, priorita_caged):
        score = 1000
        
        notes_per_string = {s: 0 for s in range(self.model.num_strings)}
        open_strings = 0
        
        # Calcolo note per corda
        for p in path:
            notes_per_string[p['string']] += 1
            if p['fret'] == 0:
                open_strings += 1
                
        # Bonus corde a vuoto
        if min_fret == 0:
            score += open_strings * 50
            
        # Penalità o bonus per note per corda
        nps_counts = [count for count in notes_per_string.values() if count > 0]
        
        if priorita_caged:
            # Forma CAGED: idealmente 2 o 3 note per corda.
            for count in nps_counts:
                if count < 2 or count > 3:
                    score -= 100 # Penalizza 1 o 4+ note per corda
        else:
            # Stile moderno / legato: preferisce strettamente 3 note per corda o pattern costanti
            threes = sum(1 for count in nps_counts if count == 3)
            score += threes * 20
            
            # Penalizza pattern misti se vogliamo strict 3NPS, ma spesso ai bordi ci sono 2 note.
            for count in nps_counts:
                if count > 4:
                    score -= 200

        # Calcolo diteggiatura base e stretch
        # Trova il tasto minimo premuto (ignorando le corde a vuoto)
        frets_pressed = [p['fret'] for p in path if p['fret'] > 0]
        if frets_pressed:
            actual_min_fret = min(frets_pressed)
            actual_max_fret = max(frets_pressed)
            stretch = actual_max_fret - actual_min_fret
            
            if stretch > 4:
                score -= (stretch - 4) * 150 # Forte penalità per stretch eccessivi
                
            # Assegnazione dita semplice
            fingering = []
            for p in path:
                if p['fret'] == 0:
                    fingering.append(0)
                else:
                    # Dito base = tasto - tasto_minimo + 1
                    finger = p['fret'] - actual_min_fret + 1
                    # Se lo stretch è > 3 (4 tasti totali, dita 1 2 3 4), il dito potrebbe essere > 4
                    if finger > 4: finger = 4 # Comprime sul mignolo
                    fingering.append(finger)
        else:
            stretch = 0
            fingering = [0] * len(path)
            
        # Calcolo difficoltà in percentuale
        # Diciamo che uno score di 1200+ è "0% difficoltà", e <= 0 è "100% difficoltà"
        difficolta_score_perc = max(0, min(100, int(100 - (score / 1200.0 * 100))))
        
        # Stretch percentuale: 4 tasti = 100% stretch accettabile (normale per 4 dita). > 4 è over-stretch.
        difficolta_stretch_perc = min(100, int((stretch / 4.0) * 100)) if stretch > 0 else 0
        if stretch > 4:
            difficolta_stretch_perc = 100 + (stretch - 4) * 25 # Va oltre il 100% se si sforza troppo

        meta = {
            'nps': notes_per_string,
            'stretch_tasti': stretch,
            'fingering': fingering,
            'difficolta_score_perc': difficolta_score_perc,
            'difficolta_stretch_perc': difficolta_stretch_perc
        }
        
        return score, meta
