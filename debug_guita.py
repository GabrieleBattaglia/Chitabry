import json
from generatore_accordi import HarmonicParser, InstrumentModel, AccordoSolver

d=json.load(open('chitabry-settings.json','r',encoding='utf-8'))
strum = d.get('strumenti', {}).get('Guitalele')
accordatura = strum.get('accordatura', [])
tasti = strum.get('tasti', 17)
print('Accordatura Guitalele:', accordatura)
model = InstrumentModel(accordatura, tasti)

target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root('Gm')
print('Gm target_pc:', target_pc, 'root:', root_pc)
s = AccordoSolver(model, target_pc, root_pc)
sol = s.solve(max_stretch=4)
sol_10 = [x for x in sol if x['C5']==10 and x['C4']==10]
if sol_10:
    print('Trovata soluzione con 10: ', sol_10[0])
    for c in range(6):
        tasto = sol_10[0][f'C{c}']
        nota = model.manico_pc[c, tasto] if tasto >=0 else -1
        print(f'Corda {c} ({accordatura[c]}), Tasto {tasto} -> PC {nota}')
