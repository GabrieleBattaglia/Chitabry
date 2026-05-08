import json
from generatore_accordi import HarmonicParser, InstrumentModel, AccordoSolver

def it_to_en(nome_it):
    # Radici
    roots = {
        'DO': 'C', 'RE': 'D', 'MI': 'E', 'FA': 'F', 'SOL': 'G', 'LA': 'A', 'SI': 'B',
        'DO DIESIS': 'C#', 'RE DIESIS': 'D#', 'FA DIESIS': 'F#', 'SOL DIESIS': 'G#', 'LA DIESIS': 'A#'
    }
    
    root_en = ""
    # Ordina per lunghezza decrescente per far matchare prima 'DO DIESIS' di 'DO'
    for r_it in sorted(roots.keys(), key=len, reverse=True):
        if nome_it.startswith(r_it):
            root_en = roots[r_it]
            nome_it = nome_it[len(r_it):].strip()
            break
    
    if not root_en:
        return None
        
    # Suffissi (adattati per music21)
    suffixes = {
        '>': '',
        '': '',
        '<': 'm',
        'DIM': 'dim',
        '4': 'sus4',
        '4<': 'm', # Semplificato per music21, originariamente m(add4) ma music21 non lo digerisce. Lo testiamo come m base.
        '5 AUM': 'aug',
        '6': '6',
        '6<': 'm6',
        '7': '7',
        '7 AUM': '7#5',
        '7/4': '7sus4',
        '7<': 'm7',
        '7/4<': 'm7', # Semplificato
        '7< AUM': 'm7#5',
        '9': '9',
        '9 DIM': '7b9' # Spesso inteso così
    }
    
    if nome_it in suffixes:
        return root_en + suffixes[nome_it]
    
    return None

def run_test():
    with open('chitabry-settings.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    chordpedia = data.get('chordpedia', {})
    
    accordatura_chitarra = ["E2", "A2", "D3", "G3", "B3", "E4"]
    model = InstrumentModel(accordatura_chitarra, 12) # Tasti standard per i test base
    
    out_lines = ["--- REPORT DIVERGENZE CHORDPEDIA VS MOTORE CSP ---\n"]
    
    total_accordi = len(chordpedia)
    for idx, (nome_it, tablature_cp) in enumerate(chordpedia.items()):
        print(f"Progresso: {(idx + 1) / total_accordi * 100:.1f}% ({idx + 1}/{total_accordi}) - Analizzo: {nome_it}".ljust(60), end='\r')
        
        nome_en = it_to_en(nome_it)
        if not nome_en:
            out_lines.append(f"SKIPPED (Nome non parsato): {nome_it}")
            continue
            
        try:
            target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root(nome_en)
        except Exception as e:
            out_lines.append(f"SKIPPED (Errore music21 '{nome_en}'): {nome_it} - {str(e)}")
            continue
            
        solver = AccordoSolver(model, target_pc, root_pc)
        sols = solver.solve(max_stretch=4)
        
        scored_sols = []
        for s in sols:
            score = solver.score_solution(s)
            scored_sols.append((score, s))
            
        scored_sols.sort(key=lambda x: x[0], reverse=True)
        
        # Prendi le prime 3 del motore
        top_motore = []
        for _, s in scored_sols[:3]:
            tab = [s[f"C{j}"] for j in range(model.num_corde)]
            tab_str = ["X" if t == -1 else str(t) for t in tab]
            top_motore.append(tab_str)
            
        # Prendi le prime 3 della chordpedia
        top_cp = []
        for t in tablature_cp[:3]:
            tab_normalizzata = [str(x).upper() for x in t] # Normalizza "x" in "X"
            
            # Costruisci il dizionario 'soluzione' fittizio per calcolare lo score
            sol_fittizia = {}
            for j in range(model.num_corde):
                val = tab_normalizzata[j]
                if val == 'X':
                    sol_fittizia[f"C{j}"] = -1
                else:
                    sol_fittizia[f"C{j}"] = int(val)
                    
            # Calcola lo score (potrebbe essere basso o violare vincoli, ma ci dà un'idea)
            score_cp = solver.score_solution(sol_fittizia)
            top_cp.append((tab_normalizzata, score_cp))
            
        # Confronto
        divergence = False
        # Consideriamo divergente se la prima scelta del motore non è tra le prime 3 della chordpedia
        if top_cp and top_motore:
            tablature_cp_solo_stringhe = [t[0] for t in top_cp]
            if top_motore[0] not in tablature_cp_solo_stringhe:
                divergence = True
        
        if divergence:
            out_lines.append(f"\nDIVERGENZA: {nome_it} (music21: {nome_en})")
            out_lines.append(f"  Note necessarie: {target_pc}, Root: {root_pc}")
            out_lines.append("  [Chordpedia] (Prime 3):")
            for t, score_cp in top_cp:
                out_lines.append(f"    {' '.join(t)} (Score: {score_cp})")
            out_lines.append("  [Motore CSP] (Prime 3):")
            for i, (score, s) in enumerate(scored_sols[:3]):
                tab_motore = top_motore[i]
                meta = solver.analizza_difficolta_e_diteggiatura(s, score)
                out_lines.append(f"    {' '.join(tab_motore)} (Score: {score}, Diff: {meta['difficolta_score_perc']}%, Stretch: {meta['difficolta_stretch_perc']}%)")
                out_lines.append(f"      {'; '.join(meta['diteggiatura'])}")
                
    print() # Nuova riga per uscire dal carriage return
    with open('divergenze.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(out_lines))
        
    print(f"Test completato. Generato file divergenze.txt con {len(out_lines)} righe.")

if __name__ == "__main__":
    run_test()
