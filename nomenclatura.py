# Chitabry, nomenclatura: i nomi delle note come li vede l'utente, latini o anglosassoni.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.

import re

import config

# Le lettere della nomenclatura latina: servono per le note che la tabella
# di config non ha, come MI#, DOb o SIbb, che le scale producono sulle
# toniche con le alterazioni e che fino alla 9.6 restavano in inglese.
_LETTERE_LATINE = {'C': 'DO', 'D': 'RE', 'E': 'MI', 'F': 'FA', 'G': 'SOL', 'A': 'LA', 'B': 'SI'}


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
    nome = mappa.get(base_name_std)
    if nome is None:
        nome = base_name_std
        trovato = re.fullmatch(r"([A-G])([#b-]*)", base_name_std)
        if trovato and config.impostazioni['nomenclatura'] == 'latino':
            nome = _LETTERE_LATINE[trovato.group(1)] + trovato.group(2).replace('-', 'b')
    return nome + micro_suffix + ottava


def nome_con_grafia(nome_m21, midi):
    """Il nome di una nota con la grafia voluta e l'ottava che suona: un
    SIb resta SIb e non diventa LA#, e un DOb si numera con l'ottava del SI
    che suona. nome_m21 e' il nome di music21 senza ottava, come B- o C#.
    Era dentro l'esercizio delle scale; dalla 9.8 la usano anche gli accordi
    sull'armonica, che scrivevano SOL minore con il LA#."""
    from music21 import pitch
    p = pitch.Pitch(nome_m21)
    p.octave = midi // 12 - 1
    while p.midi > midi:
        p.octave -= 1
    while p.midi < midi:
        p.octave += 1
    return get_nota(p.nameWithOctave.replace('-', 'b'))


def nota_std_da_midi(midi):
    """Da numero MIDI al nome standard con i diesis e l'ottava, per esempio C#4."""
    return f"{config.NOTE_STD[midi % 12]}{midi // 12 - 1}"


def nome_da_midi(midi):
    """Il numero MIDI detto nella nomenclatura dell'utente, con l'ottava."""
    return get_nota(nota_std_da_midi(midi))


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
