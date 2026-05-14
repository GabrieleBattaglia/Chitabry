from generatore_accordi import HarmonicParser, InstrumentModel, AccordoSolver

def max_fingers_constraint(*tasti):
    tasti_premuti_idx = [i for i, t in enumerate(tasti) if t > 0]
    if len(tasti_premuti_idx) <= 4:
        return True
    min_tasto = min([tasti[i] for i in tasti_premuti_idx])
    rimanenti_idx = [i for i in tasti_premuti_idx if tasti[i] > min_tasto]
    if len(rimanenti_idx) <= 3:
        return True
    if 5 in rimanenti_idx:
        tasto_cantino = tasti[5]
        corde_in_mini_barre = 0
        for c in range(5, -1, -1):
            if c in rimanenti_idx and tasti[c] == tasto_cantino:
                corde_in_mini_barre += 1
            else:
                break
        if corde_in_mini_barre >= 2:
            dita_rimanenti = len(rimanenti_idx) - corde_in_mini_barre
            dita_usate = 1 + dita_rimanenti
            if dita_usate <= 3:
                return True
    return False

print('Local test 3,3,3,0,1,3:', max_fingers_constraint(3,3,3,0,1,3))
print('Local test 3,1,0,3,3,3:', max_fingers_constraint(3,1,0,3,3,3))

model = InstrumentModel(['E2', 'A2', 'D3', 'G3', 'B3', 'E4'], 21)
target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root('Gm')
solver = AccordoSolver(model, target_pc, root_pc)
sols = solver.solve(max_stretch=4)
for s in sols:
    tab = [s[f"C{j}"] for j in range(6)]
    if tab == [3, 3, 3, 0, 1, 3]:
        print("FOUND [3, 3, 3, 0, 1, 3] IN ACTUAL SOLS!")
    if tab == [3, 1, 0, 3, 3, 3]:
        print("FOUND [3, 1, 0, 3, 3, 3] IN ACTUAL SOLS!")

