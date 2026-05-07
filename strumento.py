from typing import Dict, List, Tuple

def parse_nota_ottava(nota_ottava: str, note_std: List[str]) -> int:
    """Restituisce l'indice (1-based) della nota nella scala cromatica assoluta."""
    if nota_ottava[-1].isdigit():
        ottava = int(nota_ottava[-1])
        nota = nota_ottava[:-1]
    else:
        raise ValueError(f"Formato nota non valido: {nota_ottava}")
    
    if nota not in note_std:
        raise ValueError(f"Nota {nota} non standard.")
    
    nota_idx = note_std.index(nota) + 1
    return ottava * len(note_std) + nota_idx


def build_fretboard_data(note_std: List[str], accordatura: List[str], num_tasti: int) -> Tuple[Dict[int, str], Dict[int, int], Dict[str, str]]:
    """Costruisce i dizionari che rappresentano il manico dello strumento."""
    scalacromatica_std = {}
    i = 0
    for j in range(0, 8):
        for nota in note_std:
            i += 1
            scalacromatica_std[i] = nota + str(j)

    num_corde = len(accordatura)
    capotasti = {}
    
    # L'accordatura solitamente è data dalla corda più grave (es. 6) alla più acuta (1)
    for idx, nota_str in enumerate(accordatura):
        corda = num_corde - idx
        capotasti[corda] = parse_nota_ottava(nota_str, note_std)

    corde = {}
    for corda in range(num_corde, 0, -1):
        start_idx = capotasti[corda]
        for tasto in range(num_tasti + 1): # da 0 al num_tasti compreso
            idx_cromatico = start_idx + tasto
            corde[f"{corda}.{tasto}"] = scalacromatica_std[idx_cromatico]
            
    return scalacromatica_std, capotasti, corde
