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


class InstrumentModel:
    """Modello unificato dello strumento che descrive corde, tasti, accordatura e Pitch Classes sul manico."""
    def __init__(self, accordatura: List[str] = None, num_tasti: int = 22, tuning_midi: List[int] = None, num_frets: int = None):
        if tuning_midi is not None:
            self.tuning_midi = tuning_midi
            self.accordatura_midi = tuning_midi
            self.num_corde = len(tuning_midi)
            self.num_strings = self.num_corde
            self.num_tasti = num_frets if num_frets is not None else num_tasti
            self.num_frets = self.num_tasti
        else:
            if accordatura is None:
                # Accordatura standard chitarra di default
                self.tuning_midi = [40, 45, 50, 55, 59, 64]
                self.accordatura_midi = self.tuning_midi
                self.num_corde = len(self.tuning_midi)
                self.num_strings = self.num_corde
                self.num_tasti = num_frets if num_frets is not None else num_tasti
                self.num_frets = self.num_tasti
            else:
                self.accordatura = accordatura
                self.num_corde = len(accordatura)
                self.num_strings = self.num_corde
                self.num_tasti = num_tasti if num_tasti is not None else (num_frets if num_frets is not None else 22)
                self.num_frets = self.num_tasti
                
                from music21 import pitch
                self.tuning_midi = [pitch.Pitch(nota).midi for nota in accordatura]
                self.accordatura_midi = self.tuning_midi
        
        import numpy as np
        self.manico_pc = np.zeros((self.num_corde, self.num_tasti + 1), dtype=int)
        for c in range(self.num_corde):
            for t in range(self.num_tasti + 1):
                self.manico_pc[c, t] = (self.tuning_midi[c] + t) % 12

