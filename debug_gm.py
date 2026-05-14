from generatore_accordi import HarmonicParser, InstrumentModel, AccordoSolver
model = InstrumentModel(['E2', 'A2', 'D3', 'G3', 'B3', 'E4'], 21)
target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root('Gm')
print('Gm target_pc:', target_pc, 'root:', root_pc)
s = AccordoSolver(model, target_pc, root_pc)
sol = s.solve(max_stretch=4)
scored = [(s.score_solution(x), x) for x in sol]
scored.sort(key=lambda x: x[0], reverse=True)
for i in range(10):
    score, tab = scored[i]
    tab_list = [str(tab[f'C{j}']) if tab[f'C{j}'] != -1 else 'x' for j in range(5, -1, -1)]
    print(f'Opzione {i+1}: {"-".join(tab_list)} score: {score}')
