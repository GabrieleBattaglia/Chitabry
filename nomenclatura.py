# Chitabry, nomenclatura: i nomi delle note come li vede l'utente, latini o anglosassoni.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.

import config


def get_nota(nota_std_music21):
    """Converte una nota standard (es. C#4, Eb, G~5, A``) nella notazione
    scelta dall'utente, latina o anglosassone, preservando i simboli
    microtonali in coda e l'eventuale ottava."""
    if not isinstance(nota_std_music21, str):
        return str(nota_std_music21)
    if config.impostazioni['nomenclatura'] == 'latino':
        mappa = config.STD_TO_LATINO
    else:
        mappa = config.STD_TO_ANGLO
    ottava = ""
    micro_suffix = ""
    base_name_std = nota_std_music21
    if base_name_std and base_name_std[-1].isdigit():
        ottava = base_name_std[-1]
        base_name_std = base_name_std[:-1]
    # Dal piu' lungo al piu' corto, per non confondere la doppia tilde con la singola
    for micro in ("~~", "``", "~", "`"):
        if base_name_std.endswith(micro):
            micro_suffix = micro
            base_name_std = base_name_std[:-len(micro)]
            break
    return mappa.get(base_name_std, base_name_std) + micro_suffix + ottava


def mappa_toniche():
    """Le dodici note nella nomenclatura scelta, associate al nome standard:
    e' il dizionario che menu mostra quando chiede una tonica."""
    if config.impostazioni['nomenclatura'] == 'latino':
        return {config.STD_TO_LATINO[std]: std for std in config.NOTE_STD}
    return {std: std for std in config.NOTE_STD}


def nomi_note_utente():
    """I nomi delle dodici note nella nomenclatura scelta, senza ottava."""
    if config.impostazioni['nomenclatura'] == 'latino':
        return config.NOTE_LATINE
    return config.NOTE_ANGLO


def nome_utente_in_std(nome, qualsiasi=False):
    """Da un nome scritto dall'utente, senza ottava, al nome standard con i
    diesis; None se non e' una nota. I bemolli si accettano e si riportano
    al diesis equivalente. Con qualsiasi vero si accettano entrambe le
    nomenclature, non solo quella scelta."""
    nome = nome.strip().upper()
    latino = dict(zip(config.NOTE_LATINE, config.NOTE_STD, strict=True))
    latino.update({'REB': 'C#', 'MIB': 'D#', 'SOLB': 'F#', 'LAB': 'G#', 'SIB': 'A#'})
    anglo = {n: n for n in config.NOTE_STD}
    anglo.update({'DB': 'C#', 'EB': 'D#', 'GB': 'F#', 'AB': 'G#', 'BB': 'A#'})
    if qualsiasi:
        return latino.get(nome) or anglo.get(nome)
    if config.impostazioni['nomenclatura'] == 'latino':
        return latino.get(nome)
    return anglo.get(nome)
