from generatore_accordi import HarmonicParser, InstrumentModel, AccordoSolver

def run_position_test():
    accordatura_chitarra = ["E2", "A2", "D3", "G3", "B3", "E4"]
    model = InstrumentModel(accordatura_chitarra, 12)
    
    accordi_da_testare = [("FA", "F"), ("SI", "B")]
    posizioni = [
        ("Posizione 1 (0-4)", 0, 4),
        ("Posizione 2 (5-8)", 5, 8),
        ("Posizione 3 (9-12)", 9, 12)
    ]
    
    for nome_it, nome_en in accordi_da_testare:
        print("\n======================================")
        print(f" TEST ACCORDO: {nome_it} ({nome_en})")
        print("======================================")
        
        target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root(nome_en)
        
        for nome_pos, t_min, t_max in posizioni:
            print(f"\n--- {nome_pos} ---")
            solver = AccordoSolver(model, target_pc, root_pc)
            
            sols = solver.solve(max_stretch=4, tasto_min=t_min, tasto_max=t_max)
            
            scored_sols = []
            for s in sols:
                score = solver.score_solution(s)
                scored_sols.append((score, s))
                
            scored_sols.sort(key=lambda x: x[0], reverse=True)
            
            if scored_sols:
                for i, (score, s) in enumerate(scored_sols[:3]):
                    tab = [s[f"C{j}"] for j in range(model.num_corde)]
                    tab_str = ["X" if t == -1 else str(t) for t in tab]
                    meta = solver.analizza_difficolta_e_diteggiatura(s, score)
                    
                    print(f" {i+1}) Tab: {' '.join(tab_str)} | Score: {score} | Diff: {meta['difficolta_score_perc']}% | Stretch: {meta['difficolta_stretch_perc']}% ({meta['stretch_tasti']} tasti)")
                    print(f"    {'; '.join(meta['diteggiatura'])}")
            else:
                print(" Nessuna diteggiatura matematicamente/fisicamente possibile trovata in questa posizione con 4 dita.")

if __name__ == "__main__":
    run_position_test()
