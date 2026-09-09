# Chitabry, prove della conversione dei nomi di nota.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# L'interprete unico di GBAudio deve dare gli stessi numeri delle tre
# funzioni che ha sostituito, su tutta l'estensione utile.

import math
import re

import pytest
from music21 import pitch

import GBAudio


def _vecchia_note_to_freq(note):
    """La note_to_freq di GBAudio fino alla 7.8.3, tenuta qui come riferimento."""
    if isinstance(note, (int, float)):
        return float(note)
    if isinstance(note, str):
        note_lower = note.lower()
        if note_lower == 'p':
            return 0.0
        note_lower = note_lower.replace('-', 'b')
        match_octave = re.search(r"\d+$", note_lower)
        if not match_octave:
            return 0.0
        octave_str = match_octave.group()
        octave = int(octave_str)
        note_base = note_lower[:-len(octave_str)]
        micro_offset = 0.0
        for micro, offset in [("~~", 1.5), ("``", -1.5), ("~", 0.5), ("`", -0.5)]:
            if note_base.endswith(micro):
                micro_offset = offset
                note_base = note_base[:-len(micro)]
                break
        match_std = re.match(r"^([a-g])([#b]?)$", note_base)
        if not match_std:
            return 0.0
        note_letter, accidental = match_std.groups()
        semitone = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}[note_letter]
        if accidental == '#':
            semitone += 1
        elif accidental == 'b':
            semitone -= 1
        midi_num = 12 + semitone + 12 * octave + micro_offset
        return 440.0 * (2.0 ** ((midi_num - 69) / 12.0))
    return 0.0


def _vecchia_note_to_midi(note_str):
    """La note_to_midi di GBAudio fino alla 7.8.3, tenuta qui come riferimento."""
    note_lower = note_str.lower()
    if note_lower == 'p':
        return None
    note_lower = note_lower.replace('-', 'b')
    match_octave = re.search(r"\d+$", note_lower)
    if not match_octave:
        return None
    octave_str = match_octave.group()
    octave = int(octave_str)
    note_base = note_lower[:-len(octave_str)]
    micro_offset = 0
    for micro, offset in [("~~", 1), ("``", -1), ("~", 0), ("`", 0)]:
        if note_base.endswith(micro):
            micro_offset = offset
            note_base = note_base[:-len(micro)]
            break
    match_std = re.match(r"^([a-g])([#b]?)$", note_base)
    if not match_std:
        return None
    note_letter, accidental = match_std.groups()
    semitone = {'c': 0, 'd': 2, 'e': 4, 'f': 5, 'g': 7, 'a': 9, 'b': 11}[note_letter]
    if accidental == '#':
        semitone += 1
    elif accidental == 'b':
        semitone -= 1
    return round(12 + semitone + 12 * octave + micro_offset)


def _tutte_le_note():
    for lettera in "CDEFGAB":
        for alterazione in ("", "#", "b", "-"):
            for micro in ("", "~", "~~", "`", "``"):
                for ottava in range(9):
                    yield f"{lettera}{alterazione}{micro}{ottava}"


def test_note_to_freq_come_prima():
    for nome in _tutte_le_note():
        assert GBAudio.note_to_freq(nome) == pytest.approx(_vecchia_note_to_freq(nome)), nome


def test_note_to_midi_come_prima():
    for nome in _tutte_le_note():
        assert GBAudio.note_to_midi(nome) == _vecchia_note_to_midi(nome), nome


def test_note_standard_concordano_con_music21():
    for lettera in "CDEFGAB":
        for alterazione in ("", "#", "-"):
            for ottava in range(1, 8):
                nome = f"{lettera}{alterazione}{ottava}"
                p = pitch.Pitch(nome)
                assert GBAudio.note_to_midi(nome) == p.midi, nome
                assert GBAudio.note_to_freq(nome) == pytest.approx(p.frequency, rel=1e-6), nome


def test_pause_e_nomi_non_validi():
    assert GBAudio.note_to_freq("p") == 0.0
    assert GBAudio.note_to_midi("p") is None
    assert GBAudio.note_to_freq("H4") == 0.0
    assert GBAudio.note_to_midi("C") is None
    assert GBAudio.scomponi_nota(None) is None
    assert GBAudio.note_to_freq(440) == 440.0
    assert GBAudio.note_to_midi(60.4) == 60


def test_freq_to_midi_torna_indietro():
    for midi in range(24, 108):
        assert GBAudio.freq_to_midi(GBAudio.midi_to_freq(midi)) == midi
    assert GBAudio.freq_to_midi(0) is None
    assert isinstance(GBAudio.freq_to_midi(440.0), int)
    assert math.isclose(GBAudio.midi_to_freq(69), 440.0)
