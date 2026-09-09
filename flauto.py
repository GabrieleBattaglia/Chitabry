# Chitabry, flauto: la tavola delle diteggiature del flauto traverso e la sua consultazione.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.

from GBUtils import dgt

import config

_FLAUTO_INTRO = """
Benvenuto nel modulo di diteggiatura del Flauto Traverso.
Questo assistente descrive la posizione delle dita per ogni nota.
La nomenclatura usata per le chiavi e' la seguente.
Mano sinistra (MS):
- Pollice: PS-Si (leva grande), PS-Sib (leva piccola)
- Indice: IS-Do (seconda chiave)
- Medio: MS-La (quarta chiave)
- Anulare: AS-Sol (quinta chiave)
- Mignolo: mS-Sol diesis (leva laterale)
Mano destra (MD):
- Indice: ID-Fa (prima chiave principale)
- Medio: MD-Mi (seconda chiave principale)
- Anulare: AD-Re (terza chiave principale)
- Mignolo: mD-Mib (leva grande), mD-Do (leva con rullo), mD-Do diesis (leva piatta)
- Trillo: TR-1 (superiore), TR-2 (inferiore)
Inserisci la nota nel formato: OTTAVA NOTA (es. '2 FA#', '1 SIb', '3 DO').
Il segno # indica diesis, la b bemolle. Le ottave valide sono 1, 2, 3 e 4 (solo per DO e RE).
"""

# Associa ogni codice chiave alla sua mano e al dito principale.
_FLAUTO_NOMENCLATURA = {
    # Mano sinistra
    'PS-Si': {'mano': 'sinistra', 'dito': 'Pollice'},
    'PS-Sib': {'mano': 'sinistra', 'dito': 'Pollice'},
    'IS-Do': {'mano': 'sinistra', 'dito': 'Indice'},
    'MS-La': {'mano': 'sinistra', 'dito': 'Medio'},
    'AS-Sol': {'mano': 'sinistra', 'dito': 'Anulare'},
    'mS-Sol#': {'mano': 'sinistra', 'dito': 'Mignolo'},
    # Mano destra
    'ID-Fa': {'mano': 'destra', 'dito': 'Indice'},
    'MD-Mi': {'mano': 'destra', 'dito': 'Medio'},
    'AD-Re': {'mano': 'destra', 'dito': 'Anulare'},
    'mD-Mib': {'mano': 'destra', 'dito': 'Mignolo'},
    'mD-Do': {'mano': 'destra', 'dito': 'Mignolo'},
    'mD-Do#': {'mano': 'destra', 'dito': 'Mignolo'},
    'TR-1': {'mano': 'destra', 'dito': 'Trillo-1 (Indice/Medio)'},
    'TR-2': {'mano': 'destra', 'dito': 'Trillo-2 (Indice/Medio)'},
}

# Conversione dell'input dell'utente in note standard con i diesis
_FLAUTO_MAPPE_NOTE = {
    "LATINO_STD": {
        'DO': 'C', 'DO#': 'C#', 'REb': 'C#',
        'RE': 'D', 'RE#': 'D#', 'MIb': 'D#',
        'MI': 'E', 'FA': 'F',
        'FA#': 'F#', 'SOLb': 'F#',
        'SOL': 'G', 'SOL#': 'G#', 'LAb': 'G#',
        'LA': 'A', 'LA#': 'A#', 'SIb': 'A#',
        'SI': 'B'
    },
    "ANGLO_STD": {
        'C': 'C', 'C#': 'C#', 'DB': 'C#',
        'D': 'D', 'D#': 'D#', 'EB': 'D#',
        'E': 'E', 'F': 'F',
        'F#': 'F#', 'GB': 'F#',
        'G': 'G', 'G#': 'G#', 'AB': 'G#',
        'A': 'A', 'A#': 'A#', 'BB': 'A#',
        'B': 'B'
    }
}

# La tavola di diteggiatura completa. La chiave e' la nota in formato standard
# di music21; il valore ha le chiavi da premere, i consigli per la terza
# ottava e le alternative.
_DITEGGIATURE_FLAUTO = {
    # Prima ottava (utente '1')
    'C4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Do')},
    'C#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Do#')},
    'D4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re')},
    'D#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Mib')},
    'E4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'mD-Mib')},
    'F4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'mD-Mib')},
    'F#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'AD-Re', 'mD-Mib')},
    'G4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mD-Mib')},
    'G#4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib')},
    'A4': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'mD-Mib')},
    'A#4': {'keys': ('PS-Si', 'IS-Do', 'ID-Fa', 'mD-Mib'),
            'alt': [{'keys': ('PS-Sib', 'IS-Do', 'mD-Mib'), 'desc': 'Diteggiatura alternativa comune (con leva Sib)'}]},
    'B4': {'keys': ('PS-Si', 'IS-Do', 'mD-Mib')},
    # Seconda ottava (utente '2')
    'C5': {'keys': ('IS-Do', 'mD-Mib')},
    'C#5': {'keys': ('mD-Mib',)},  # Nessuna chiave premuta, solo mD-Mib
    'D5': {'keys': ('PS-Si', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re')},
    'D#5': {'keys': ('PS-Si', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Mib')},
    'E5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'mD-Mib')},
    'F5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'ID-Fa', 'mD-Mib')},
    'F#5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'AD-Re', 'mD-Mib')},
    'G5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mD-Mib')},
    'G#5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib')},
    'A5': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'mD-Mib')},
    'A#5': {'keys': ('PS-Si', 'IS-Do', 'ID-Fa', 'mD-Mib'),
            'alt': [{'keys': ('PS-Sib', 'IS-Do', 'mD-Mib'), 'desc': 'Diteggiatura alternativa comune (con leva Sib)'}]},
    'B5': {'keys': ('PS-Si', 'IS-Do', 'mD-Mib')},
    # Terza ottava (utente '3' e '4')
    'C6': {'keys': ('IS-Do', 'mD-Mib')},  # Identica a C5
    'C#6': {'keys': ('MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib'), 'consigli': "Flusso d'aria molto veloce e stretto."},
    'D6': {'keys': ('PS-Si', 'MS-La', 'AS-Sol', 'mD-Mib'), 'consigli': 'Supporto diaframmatico intenso.'},
    'D#6': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'ID-Fa', 'MD-Mi', 'AD-Re', 'mD-Mib'), 'consigli': 'Molto supporto, apertura labiale minima.'},
    'E6': {'keys': ('PS-Si', 'IS-Do', 'MS-La', 'ID-Fa', 'MD-Mi', 'mD-Mib'), 'consigli': "Lo 'Split E' aiuta la stabilita'."},
    'F6': {'keys': ('PS-Si', 'IS-Do', 'AS-Sol', 'ID-Fa', 'mD-Mib'), 'consigli': "Dirigere l'aria leggermente piu' in alto."},
    'F#6': {'keys': ('PS-Si', 'IS-Do', 'AS-Sol', 'AD-Re', 'mD-Mib'), 'consigli': "Non usare il pollice Sib. Flusso d'aria molto rapido."},
    'G6': {'keys': ('IS-Do', 'MS-La', 'AS-Sol', 'mD-Mib'), 'consigli': 'Molto stabile, mantenere il supporto.'},
    'G#6': {'keys': ('MS-La', 'AS-Sol', 'mS-Sol#', 'mD-Mib'), 'consigli': "Tende a essere crescente, rilassare l'imboccatura."},
    'A6': {'keys': ('PS-Si', 'MS-La', 'ID-Fa', 'mD-Mib'), 'consigli': "Flusso d'aria molto focalizzato."},
    'A#6': {'keys': ('PS-Si', 'ID-Fa', 'TR-2'), 'consigli': "Richiede precisione nell'imboccatura."},
    'B6': {'keys': ('PS-Si', 'IS-Do', 'AS-Sol', 'TR-2'), 'consigli': 'Mantenere la gola aperta.'},
    'C7': {'keys': ('IS-Do', 'MS-La', 'AS-Sol', 'mS-Sol#', 'ID-Fa'), 'consigli': 'Supporto massimo.'},
    'C#7': {'keys': ('MS-La', 'mS-Sol#', 'ID-Fa', 'mD-Mib')},
    'D7': {'keys': ('PS-Si', 'AS-Sol', 'ID-Fa', 'MD-Mi', 'mD-Do')},
}


def _formatta_mano_flauto(mano: str, dita: set) -> str:
    """Descrizione a parole di una singola mano: riceve 'sinistra' o 'destra'
    e l'insieme delle dita usate, per esempio {'Pollice', 'Indice'}."""
    ordine_dita = ['Pollice', 'Indice', 'Medio', 'Anulare', 'Mignolo', 'Trillo-1 (Indice/Medio)', 'Trillo-2 (Indice/Medio)']
    dita_ordinate = [d for d in ordine_dita if d in dita]
    if not dita_ordinate:
        return f"Nessun dito della mano {mano}."
    dita_principali_sx = {'Pollice', 'Indice', 'Medio', 'Anulare', 'Mignolo'}
    dita_principali_dx = {'Indice', 'Medio', 'Anulare', 'Mignolo'}
    if mano == 'sinistra' and dita == dita_principali_sx:
        return "Tutte le dita della mano sinistra."
    if mano == 'destra' and dita == dita_principali_dx:
        return "Tutte le dita della mano destra (Indice, Medio, Anulare, Mignolo)."
    desc = f"Mano {mano}: " + ", ".join(dita_ordinate)
    desc = desc.replace("Indice, Medio, Anulare, Mignolo", "tutte le dita (Indice, Medio, Anulare, Mignolo)")
    desc = desc.replace("Indice, Medio, Anulare", "Indice, Medio e Anulare")
    desc = desc.replace("Trillo-1 (Indice/Medio), Trillo-2 (Indice/Medio)", "entrambe le chiavi del trillo")
    return desc + "."


def _genera_descrizione_flauto(keys_tuple: tuple) -> str:
    """Da una tupla di chiavi, per esempio ('PS-Si', 'IS-Do', 'mD-Mib'), alla
    descrizione verbale completa."""
    if not keys_tuple:
        return "Nessuna chiave premuta (richiede un'imboccatura molto precisa)."
    dita_sinistra = set()
    dita_destra = set()
    for key_code in keys_tuple:
        if key_code in _FLAUTO_NOMENCLATURA:
            info = _FLAUTO_NOMENCLATURA[key_code]
            if info['mano'] == 'sinistra':
                dita_sinistra.add(info['dito'])
            else:
                dita_destra.add(info['dito'])
    desc_sinistra = _formatta_mano_flauto('sinistra', dita_sinistra)
    desc_destra = _formatta_mano_flauto('destra', dita_destra)
    # Il caso speciale del Do diesis della seconda ottava, solo mignolo destro
    if keys_tuple == ('mD-Mib',):
        return "Nessun dito della mano sinistra. Solo il Mignolo della mano destra (su Mib)."
    # Le note con tutte le dita (Do, Re diesis della prima ottava e simili)
    tutte_le_dita_sx = {'Pollice', 'Indice', 'Medio', 'Anulare'}
    tutte_le_dita_dx = {'Indice', 'Medio', 'Anulare'}
    if dita_sinistra >= tutte_le_dita_sx and dita_destra >= tutte_le_dita_dx:
        desc_base = "Tutte le dita della mano sinistra e tutte le principali della destra (Indice, Medio, Anulare)"
        mignolo_dx_desc = []
        if 'mD-Do' in keys_tuple:
            mignolo_dx_desc.append("leva Do")
        if 'mD-Do#' in keys_tuple:
            mignolo_dx_desc.append("leva Do#")
        if 'mD-Mib' in keys_tuple:
            mignolo_dx_desc.append("leva Mib")
        if mignolo_dx_desc:
            return desc_base + f", piu' il Mignolo destro (su {', '.join(mignolo_dx_desc)})."
        return desc_base + "."
    return desc_sinistra + "\n" + desc_destra


def GestoreFlauto():
    """Sottomenu del flauto: chiede ottava e nota e stampa la diteggiatura."""
    print(_FLAUTO_INTRO)
    if config.impostazioni['nomenclatura'] == 'latino':
        mappa_note = _FLAUTO_MAPPE_NOTE["LATINO_STD"]
    else:
        mappa_note = _FLAUTO_MAPPE_NOTE["ANGLO_STD"]
    while True:
        input_str = dgt("Ottava e Nota (es. '2 FA#') [Invio per uscire]: ", kind="s").strip().upper()
        if not input_str:
            print("Ritorno al menu principale.")
            break
        parti = input_str.split(None, 1)
        if len(parti) != 2:
            print("Errore: formato non valido. Inserire OTTAVA NOTA (es. '2 FA#').")
            continue
        ottava_str, nota_utente = parti
        if ottava_str not in ('1', '2', '3', '4'):
            print("Errore: L'ottava deve essere 1, 2, 3 o 4.")
            continue
        nota_std = mappa_note.get(nota_utente)
        if nota_std is None:
            print(f"Errore: Nota '{nota_utente}' non riconosciuta.")
            continue
        # L'ottava 1 del flautista e' la quarta di music21
        lookup_key = f"{nota_std}{int(ottava_str) + 3}"
        diteggiatura_info = _DITEGGIATURE_FLAUTO.get(lookup_key)
        nota_display = nota_utente.replace("#", " diesis").title()
        if not diteggiatura_info:
            print(f"Diteggiatura non trovata per {nota_display} (ottava {ottava_str}, chiave {lookup_key}).")
            continue
        print(f"Diteggiatura per {nota_display}, ottava {ottava_str}:")
        print(_genera_descrizione_flauto(diteggiatura_info['keys']))
        if diteggiatura_info.get('consigli'):
            print(f"Consigli: {diteggiatura_info['consigli']}")
        for i, alt in enumerate(diteggiatura_info.get('alt', [])):
            print(f"Alternativa {i + 1} ({alt.get('desc', 'alternativa')}):")
            print(_genera_descrizione_flauto(alt['keys']))
