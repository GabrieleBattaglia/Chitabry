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

    def solve(self, max_stretch=4):
        prob = Problem()
        
        tasti_possibili = list(range(self.model.num_tasti + 1)) + [-1]
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

        def no_wrong_notes(*tasti):
            for c, t in enumerate(tasti):
                if t != -1:
                    if self.model.manico_pc[c, t] not in self.target:
                        return False
            return True
            
        prob.addConstraint(has_root, variabili)
        prob.addConstraint(has_all_notes, variabili)
        prob.addConstraint(max_stretch_constraint, variabili)
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
        score += corde_vuote * 20
        
        # 2. Penalità per le corde mute (-1, che sarebbe 'X')
        corde_mute = tasti.count(-1)
        score -= corde_mute * 30
        
        # Penalità grave se c'è una corda muta IN MEZZO a corde che suonano
        suonanti_idx = [i for i, t in enumerate(tasti) if t != -1]
        if suonanti_idx:
            min_idx = min(suonanti_idx)
            max_idx = max(suonanti_idx)
            for i in range(min_idx, max_idx):
                if tasti[i] == -1:
                    score -= 100 # Molto scomodo per lo strumming
                    
        # 3. Penalità per lo stretch (più largo = più difficile)
        if tasti_premuti:
            stretch = max(tasti_premuti) - min(tasti_premuti)
            score -= stretch * 25
            
            # Penalità per suonare troppo in alto sul manico senza motivo (preferiamo i primi tasti)
            score -= min(tasti_premuti) * 5
            
        # 4. Premio se la nota più bassa suonata è la fondamentale (Root position)
        if suonanti_idx:
            lowest_string = suonanti_idx[0] # La corda con indice minore è la più grave
            lowest_fret = tasti[lowest_string]
            if self.model.manico_pc[lowest_string, lowest_fret] == self.root:
                score += 50
        
        # 5. Penalità se si usano poche corde (preferiamo accordi pieni)
        score += len(suonanti_idx) * 10
        
        return score

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
                print(f" {i+1}) Tab: {' '.join(tab_str)} | Punteggio: {score}")
        else:
            print("Nessuna soluzione trovata.")

if __name__ == "__main__":
    test_generatore()
