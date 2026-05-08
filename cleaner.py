import re

with open('Chitabry.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Indici da rimuovere (0-based)
# Barre (1167) a Aggiungiaccordo end (1444)
# E GestoreChordpedia (1854) a 1885
lines_to_keep = []
for i, line in enumerate(lines):
    line_num = i + 1
    if (1167 <= line_num <= 1444) or (1854 <= line_num <= 1885):
        continue
    lines_to_keep.append(line)

content = "".join(lines_to_keep)

# Rimuovi l'opzione Chordpedia dal menu e da main()
content = content.replace('"Accordi": "Gestisci le tue Tablature Accordi (salvate)",\n', '')
content = content.replace('    num_accordi = len(impostazioni.get(\'chordpedia\', {}))\n    print(f"Le tue Tablature Accordi contengono {num_accordi} diteggiature.") \n', '')

main_block = """        if scelta == "Accordi":
            GestoreChordpedia()
        
        elif scelta == "Costruttore Accordi": # <-- NUOVO BLOCCO"""

new_main_block = """        if scelta == "Costruttore Accordi":"""
content = content.replace(main_block, new_main_block)

# Rimuovi salvataggio in CostruttoreAccordi
vecchio_salvataggio = """        azione = dgt("\\nScegli: [S]alva nella Chordpedia | [R]iascolta | [Invio] per tornare alle opzioni: ").strip().lower()
        if azione == 's':
            nome_chordpedia = nome_accordo_display.upper()
            if 'chordpedia' not in impostazioni:
                impostazioni['chordpedia'] = {}
            if nome_chordpedia not in impostazioni['chordpedia']:
                impostazioni['chordpedia'][nome_chordpedia] = []
                
            if tab_selezionata not in impostazioni['chordpedia'][nome_chordpedia]:
                # Aggiungi e salva
                impostazioni['chordpedia'][nome_chordpedia].append(tab_selezionata)
                salva_impostazioni()
                print(f"\\nDiteggiatura aggiunta alla tua Chordpedia sotto '{nome_chordpedia}' e salvata nel file json!")
            else:
                print("\\nQuesta diteggiatura è già presente nella tua Chordpedia.")
            key("Premi un tasto per continuare...")
            
        elif azione == 'r':
            SuonaAccordoTeorico(tuple(note_da_suonare))"""

nuovo_salvataggio = """        azione = dgt("\\nScegli: [R]iascolta | [Invio] per tornare alle opzioni: ").strip().lower()
        if azione == 'r':
            SuonaAccordoTeorico(tuple(note_da_suonare))"""

content = content.replace(vecchio_salvataggio, nuovo_salvataggio)

with open('Chitabry.py', 'w', encoding='utf-8') as f:
    f.write(content)
print("File ripulito.")
