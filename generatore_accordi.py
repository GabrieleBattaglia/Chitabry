import numpy as np
from constraint import Problem
from music21 import harmony, pitch

class HarmonicParser:
    """Modulo 1: Analizza l'accordo e restituisce le pitch classes necessarie."""
    @staticmethod
    def get_pitch_classes_and_root(chord_name: str) -> tuple[set, int]:
        c = harmony.ChordSymbol(chord_name)
        target_pc = {p.pitchClass for p in c.pitches}
        root_pc = c.root().pitchClass
        return target_pc, root_pc

class InstrumentModel:
    """Modulo 2: Crea la matrice delle note (pitch classes) sul manico."""
    def __init__(self, accordatura: list[str], num_tasti: int):
        self.num_corde = len(accordatura)
        self.num_tasti = num_tasti
        
        self.accordatura_midi = [pitch.Pitch(nota).midi for nota in accordatura]
        
        self.manico_pc = np.zeros((self.num_corde, self.num_tasti + 1), dtype=int)
        for c in range(self.num_corde):
            for t in range(self.num_tasti + 1):
                self.manico_pc[c, t] = (self.accordatura_midi[c] + t) % 12

class AccordoSolver:
    """Modulo 3: Il cuore dell'algoritmo CSP."""
    def __init__(self, model: InstrumentModel, target_pitch_classes: set, root_pitch_class: int):
        self.model = model
        self.target = target_pitch_classes
        self.root = root_pitch_class

    def solve(self, max_stretch=4, tasto_min=0, tasto_max=12):
        prob = Problem()
        
        # Filtra i tasti in base alla posizione richiesta, mantenendo sempre la possibilità
        # di suonare la corda muta (-1). Le corde a vuoto (0) sono incluse SOLO se il 
        # range di ricerca parte esplicitamente da 0.
        tasti_possibili = [t for t in range(self.model.num_tasti + 1) if tasto_min <= t <= tasto_max]
        if tasto_min == 0 and 0 not in tasti_possibili:
            tasti_possibili.append(0)
        tasti_possibili.append(-1)
        
        variabili = [f"C{i}" for i in range(self.model.num_corde)]
        
        for var in variabili:
            prob.addVariable(var, tasti_possibili)
            
        def has_root(*tasti):
            for c, t in enumerate(tasti):
                if t != -1:
                    if self.model.manico_pc[c, t] == self.root:
                        return True
            return False
            
        def has_all_notes(*tasti):
            note_suonate = set()
            for c, t in enumerate(tasti):
                if t != -1:
                    note_suonate.add(self.model.manico_pc[c, t])
            return self.target.issubset(note_suonate)
            
        def max_stretch_constraint(*tasti):
            tasti_premuti = [t for t in tasti if t > 0]
            if not tasti_premuti:
                return True
            # Se abbiamo note a vuoto (0) e note premute, lo stretch effettivo 
            # parte dal tasto minimo premuto. L'utente specifica che da 3 a 6 c'è stretch 4.
            # Se un dito preme, lo stretch si calcola solo sui tasti premuti.
            stretch = max(tasti_premuti) - min(tasti_premuti)
            # Se la mano è molto vicina al capotasto, possiamo essere più permissivi 
            # ma il limite biomeccanico si riferisce alla distanza tra indice e mignolo.
            return stretch <= max_stretch

        def max_fingers_constraint(*tasti):
            tasti_premuti_idx = [i for i, t in enumerate(tasti) if t > 0]
            if len(tasti_premuti_idx) <= 4:
                return True
                
            min_tasto = min([tasti[i] for i in tasti_premuti_idx])
            rimanenti_idx = [i for i in tasti_premuti_idx if tasti[i] > min_tasto]
            
            if not rimanenti_idx:
                return True
                
            dita_usate = 0
            i = 0
            while i < len(rimanenti_idx):
                dita_usate += 1
                curr_idx = rimanenti_idx[i]
                curr_tasto = tasti[curr_idx]
                
                j = i + 1
                while j < len(rimanenti_idx):
                    next_idx = rimanenti_idx[j]
                    if tasti[next_idx] != curr_tasto:
                        break
                        
                    ostacolo = False
                    for k in range(curr_idx + 1, next_idx):
                        if tasti[k] > 0 and tasti[k] != curr_tasto:
                            ostacolo = True
                            break
                    if ostacolo:
                        break
                        
                    j += 1
                i = j
                
            return dita_usate <= 3

        def no_wrong_notes(*tasti):
            for c, t in enumerate(tasti):
                if t != -1:
                    if self.model.manico_pc[c, t] not in self.target:
                        return False
            return True
            
        prob.addConstraint(has_root, variabili)
        prob.addConstraint(has_all_notes, variabili)
        prob.addConstraint(max_stretch_constraint, variabili)
        prob.addConstraint(max_fingers_constraint, variabili)
        prob.addConstraint(no_wrong_notes, variabili)
        
        soluzioni = prob.getSolutions()
        return soluzioni

    def score_solution(self, soluzione: dict) -> int:
        """
        Calcola un punteggio per una soluzione. Più alto è il punteggio, migliore è la diteggiatura.
        """
        score = 1000 # Partiamo da un punteggio base alto
        tasti = [soluzione[f"C{i}"] for i in range(self.model.num_corde)]
        
        tasti_premuti = [t for t in tasti if t > 0]
        
        # 1. Premio per le corde a vuoto
        corde_vuote = tasti.count(0)
        score += corde_vuote * 30  # Aumentato drasticamente per premiare le posizioni con corde aperte
        
        # 2. Penalità per le corde mute (-1) e corde a vuoto impossibili (barré spezzato)
        suonanti_idx = [i for i, t in enumerate(tasti) if t != -1]
        if suonanti_idx:
            min_idx = min(suonanti_idx)
            max_idx = max(suonanti_idx)
            for i, t in enumerate(tasti):
                if t == -1:
                    if i < min_idx or i > max_idx:
                        # Corda muta ai bordi (es. x x 0 2 3 2): lieve penalità o nessuna
                        score -= 2
                    else:
                        # Corda muta in mezzo (es. 1 x 2...): usata in ottave o power chords estesi, penalità ridotta
                        score -= 15
        
        # 3. Penalità per lo stretch (più largo = più difficile)
        if tasti_premuti:
            stretch = max(tasti_premuti) - min(tasti_premuti)
            score -= stretch * 20
            
            # Penalità per suonare troppo in alto sul manico senza motivo (MOLTO severa per favorire il capotasto)
            score -= min(tasti_premuti) * 20
            
            # Penalità severa per i barré (richiedono molta forza fisica!)
            if len(tasti_premuti) > 4:
                min_tasto = min(tasti_premuti)
                if min_tasto > 0:
                    corde_min_tasto = [i for i, t in enumerate(tasti) if t == min_tasto]
                    if len(corde_min_tasto) >= 2:
                        score -= 80 # Faticoso!
                        
                        primo_barre = min(corde_min_tasto)
                        for i in range(primo_barre, self.model.num_corde):
                            if tasti[i] == 0:
                                score -= 150 # Impossibile mantenere corda a vuoto sotto un barré obbligatorio
                
                # 3.6 Premio per le Forme a Barrè Standard (solo un piccolo rimborso sulla faticaccia)
                if len(corde_min_tasto) >= 3:
                    score += 20
            
        # 4. Premio se la nota più bassa suonata è la fondamentale (Root position)
        if suonanti_idx:
            lowest_string = suonanti_idx[0] # La corda con indice minore è la più grave
            lowest_fret = tasti[lowest_string]
            if self.model.manico_pc[lowest_string, lowest_fret] == self.root:
                score += 50
                
                # 4.5 Bonus Struttura "Basso-Quinta"
                if len(suonanti_idx) > 1:
                    next_string = suonanti_idx[1]
                    next_fret = tasti[next_string]
                    nota_basso = self.model.manico_pc[lowest_string, lowest_fret]
                    nota_successiva = self.model.manico_pc[next_string, next_fret]
                    if (nota_successiva - nota_basso) % 12 == 7: # Quinta giusta
                        score += 10
        
        # 5. Penalità se si usano poche corde (preferiamo accordi pieni, ma senza esagerare)
        score += len(suonanti_idx) * 10
        
        return score

    def analizza_difficolta_e_diteggiatura(self, soluzione: dict, score: int) -> dict:
        tasti = [soluzione[f"C{i}"] for i in range(self.model.num_corde)]
        tasti_premuti_idx = [i for i, t in enumerate(tasti) if t > 0]
        
        diteggiatura_raw = {}
        barre_fret = None
        has_barre = False
        
        if tasti_premuti_idx:
            corde_per_tasto = {}
            for i in tasti_premuti_idx:
                t = tasti[i]
                if t not in corde_per_tasto:
                    corde_per_tasto[t] = []
                corde_per_tasto[t].append(i)
                
            min_tasto = min(corde_per_tasto.keys())
            dito_corrente = 1
            
            for t in sorted(corde_per_tasto.keys()):
                corde = sorted(corde_per_tasto[t])
                
                # Check barré sul tasto minimo (solo se ci sono > 4 corde premute, che rende il barré obbligatorio)
                if t == min_tasto and len(corde) >= 2 and len(tasti_premuti_idx) > 4:
                    has_barre = True
                    barre_fret = t
                    for c in corde:
                        diteggiatura_raw[f"C{c}"] = f"Dito {dito_corrente} (Barré al tasto {t})"
                    dito_corrente += 1
                
                # Check piccolo barré su tasti superiori (deve partire dal cantino, index 5)
                elif 5 in corde and len(tasti_premuti_idx) > 4:
                    mini_barre_corde = []
                    for c in range(5, -1, -1):
                        if c in corde:
                            mini_barre_corde.append(c)
                        else:
                            break
                            
                    if len(mini_barre_corde) >= 2:
                        for c in reversed(mini_barre_corde):
                            diteggiatura_raw[f"C{c}"] = f"Dito {dito_corrente} (Piccolo barré al tasto {t})"
                        dito_corrente += 1
                        
                        for c in corde:
                            if c not in mini_barre_corde:
                                diteggiatura_raw[f"C{c}"] = f"Dito {dito_corrente} al tasto {t}"
                                dito_corrente += 1
                    else:
                        for c in corde:
                            diteggiatura_raw[f"C{c}"] = f"Dito {dito_corrente} al tasto {t}"
                            dito_corrente += 1
                    
                # Dita separate
                else:
                    for c in corde:
                        diteggiatura_raw[f"C{c}"] = f"Dito {dito_corrente} al tasto {t}"
                        dito_corrente += 1

        # Aggreghiamo le descrizioni
        dita_desc = {}
        for i in range(self.model.num_corde):
            if tasti[i] == -1:
                desc = "Muta"
            elif tasti[i] == 0:
                desc = "A vuoto"
            else:
                desc = diteggiatura_raw.get(f"C{i}", "Ignoto")
                
            if desc not in dita_desc:
                dita_desc[desc] = []
            corda_std = str(6 - i) # Convertiamo 0..5 in 6..1 (Standard)
            dita_desc[desc].append(corda_std)
            
        diteggiatura_formattata = []
        for desc, corde in dita_desc.items():
            if desc in ["Muta", "A vuoto"]:
                diteggiatura_formattata.append(f"Corde {', '.join(corde)}: {desc}")
            else:
                if "Barré" in desc or "Piccolo barré" in desc:
                    diteggiatura_formattata.append(f"{desc} sulle Corde {', '.join(corde)}")
                else:
                    diteggiatura_formattata.append(f"{desc} sulla Corda {corde[0]}")

        # Mappatura empirica: 1250 = 0% diff, 850 = 100% diff
        diff_punteggio = ((1250 - score) / 400.0) * 100
        diff_punteggio = max(0, min(100, int(diff_punteggio)))
        
        stretch_val = 0
        diff_stretch = 0
        if tasti_premuti_idx:
            tasti_premuti_vals = [tasti[i] for i in tasti_premuti_idx]
            stretch_val = max(tasti_premuti_vals) - min(tasti_premuti_vals) + 1 # estensione effettiva in tasti
            mappa_stretch = {1: 0, 2: 10, 3: 30, 4: 60, 5: 100}
            diff_stretch = mappa_stretch.get(stretch_val, 100)
            
        return {
            "diteggiatura": diteggiatura_formattata,
            "has_barre": has_barre,
            "barre_fret": barre_fret,
            "difficolta_score_perc": diff_punteggio,
            "difficolta_stretch_perc": diff_stretch,
            "stretch_tasti": stretch_val
        }

def test_generatore():
    print("--- Test Motore Generazione Accordi CSP ---")
    
    accordi_da_testare = ["A", "D", "G", "C", "Am", "Dm", "F"]
    accordatura_chitarra = ["E2", "A2", "D3", "G3", "B3", "E4"]
    num_tasti_chitarra = 12
    
    model = InstrumentModel(accordatura_chitarra, num_tasti_chitarra)
    
    for accordo in accordi_da_testare:
        target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root(accordo)
        print(f"\nCerco '{accordo}' (Note necessarie: {target_pc}, Root: {root_pc})")
        
        solver = AccordoSolver(model, target_pc, root_pc)
        sols = solver.solve(max_stretch=4)
        
        # Classifichiamo le soluzioni
        scored_sols = []
        for s in sols:
            score = solver.score_solution(s)
            scored_sols.append((score, s))
            
        # Ordiniamo per punteggio decrescente
        scored_sols.sort(key=lambda x: x[0], reverse=True)
        
        if scored_sols:
            print("--- TOP 3 DITEGGIATURE ---")
            for i, (score, s) in enumerate(scored_sols[:3]):
                tab = [s[f"C{j}"] for j in range(model.num_corde)]
                tab_str = ["X" if t == -1 else str(t) for t in tab]
                meta = solver.analizza_difficolta_e_diteggiatura(s, score)
                
                print(f" {i+1}) Tab: {' '.join(tab_str)} | Diff: {meta['difficolta_score_perc']}% | Stretch: {meta['difficolta_stretch_perc']}% ({meta['stretch_tasti']} tasti)")
                print(f"    {'; '.join(meta['diteggiatura'])}")
        else:
            print("Nessuna soluzione trovata.")

if __name__ == "__main__":
    test_generatore()
