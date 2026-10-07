# Chitabry, prove dei banchi di suoni: riconoscimento dei soundfont General MIDI, ricerca, suono banco.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nate con la 9.10.0. I soundfont delle prove sul formato sono finti, fatti
# di sola intestazione; le prove che suonano davvero usano il FluidSynth e il
# banco che MeTeOra ha gia' scaricato sul computer di Gabriele, e altrove si
# saltano.

import math
import os
import struct

import numpy as np
import pytest

import accordatore
import banchi
import config
import GBAudio
import suoni

FLUIDSYNTH_DI_METEORA = "E:/git/mine/MeTeOra/fluidsynth"
BANCO_SGM = r"E:\VstPlugins\SF2 Instruments\SGM-V2.01.sf2"
CI_SONO = os.path.isfile(os.path.join(FLUIDSYNTH_DI_METEORA, banchi.FLUIDSYNTH_DLL[0])) and os.path.isfile(BANCO_SGM)


def soundfont_finto(percorso, programmi=128, batteria=True):
    """Un sf2 di sola intestazione: RIFF sfbk, una lista pdta con il phdr."""
    record = [struct.pack("<20sHHH", b"preset", p, 0, 0) + b"\0" * 12 for p in range(programmi)]
    if batteria:
        record.append(struct.pack("<20sHHH", b"drum", 0, 128, 0) + b"\0" * 12)
    record.append(struct.pack("<20sHHH", b"EOP", 0, 0, 0) + b"\0" * 12)
    phdr = b"".join(record)
    pdta = b"pdta" + b"phdr" + struct.pack("<I", len(phdr)) + phdr
    lista = b"LIST" + struct.pack("<I", len(pdta)) + pdta
    corpo = b"sfbk" + lista
    with open(percorso, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(corpo)) + corpo)


def test_si_riconoscono_i_banchi_general_midi(tmp_path):
    gm = tmp_path / "completo.sf2"
    soundfont_finto(gm)
    pochi = tmp_path / "pochi.sf2"
    soundfont_finto(pochi, programmi=12)
    senza = tmp_path / "senza_batteria.sf2"
    soundfont_finto(senza, batteria=False)
    falso = tmp_path / "falso.sf2"
    falso.write_bytes(b"non sono un soundfont")
    assert banchi.e_un_banco(gm) and banchi.general_midi(gm)
    assert banchi.e_un_banco(pochi) and not banchi.general_midi(pochi)
    assert not banchi.general_midi(senza)
    assert not banchi.e_un_banco(falso) and not banchi.general_midi(falso)


def test_la_ricerca_tiene_solo_i_general_midi(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "node_modules").mkdir()
    soundfont_finto(tmp_path / "a" / "Bello.sf2")
    soundfont_finto(tmp_path / "a" / "Piccolo.sf2", programmi=5)
    soundfont_finto(tmp_path / "node_modules" / "Saltato.sf2")
    trovati = banchi.cerca_banchi([str(tmp_path)])
    assert [os.path.basename(p) for p, _ in trovati] == ["Bello.sf2"]
    assert banchi.cerca_banchi([str(tmp_path)], fermo=lambda: True) == []
    assert banchi.dimensione_da_leggere(148398306) == "148 MB"
    assert banchi.dimensione_da_leggere(2_500_000) == "2.5 MB"


def test_il_banco_si_salta_finche_non_e_pronto(monkeypatch):
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": ""}, "midi_strumento": 0})
    assert suoni.prossimo_suono("midi") == "suono_1"
    monkeypatch.setattr(suoni, "banco_pronto", lambda: True)
    assert suoni.prossimo_suono("midi") == "banco"
    assert suoni.prossimo_suono("banco") == "suono_1"
    assert suoni.sigla_suono("banco") == "BAN"


def test_le_note_del_banco_passano_dal_renderer(monkeypatch):
    """Chi suona non sa quale suono sta suonando: configura e chiede il mono."""
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "x.sf2", "volume": 0.5, "dur": 2.0}, "midi_strumento": 22})
    chiamate = []

    def rendi_finta(banco, programma, frequenza, secondi, fs, velocita=100, coda=banchi.CODA):
        chiamate.append((banco, programma, round(frequenza, 2), secondi, coda))
        return np.ones(10, dtype=np.float32)

    monkeypatch.setattr(banchi, "rendi_nota", rendi_finta)
    monkeypatch.setattr(banchi, "fattore_dello_strumento", lambda *_a: 1.0)
    parametri = suoni.parametri_suono("banco")
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    suoni.configura_renderer(renderer, 440.0, parametri)
    mono = suoni.mono_da_renderer(renderer)
    assert mono.tolist() == [0.5] * 10
    tenuta, ciclo = suoni.tenuta_da_renderer(renderer)
    assert ciclo is None and len(tenuta) == 10
    assert chiamate == [("x.sf2", 22, 440.0, 2.0, banchi.CODA), ("x.sf2", 22, 440.0, banchi.SECONDI_TENUTA, 0.0)]
    # Lo stesso renderer, riconfigurato per un sintetico, torna sintetico
    suoni.configura_renderer(renderer, 440.0, {**parametri, "banco": False, "kind": 1})
    assert renderer.nota_del_banco is None


def test_un_banco_che_non_suona_si_dice_una_volta(monkeypatch, capsys):
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "manca.sf2"}, "midi_strumento": 0})
    monkeypatch.setattr(suoni, "_BANCO_AVVISATO", [])

    def rotto(*_a, **_k):
        raise OSError("il banco di suoni manca.sf2 non si carica")

    monkeypatch.setattr(banchi, "rendi_nota", rotto)
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    suoni.configura_renderer(renderer, 440.0, suoni.parametri_suono("banco"))
    assert suoni.mono_da_renderer(renderer) is None
    assert suoni.mono_da_renderer(renderer) is None
    assert capsys.readouterr().out.count("non suona") == 1


@pytest.mark.skipif(not CI_SONO, reason="FluidSynth di MeTeOra o banco SGM assenti")
def test_il_banco_vero_suona_intonato(monkeypatch):
    """Con FluidSynth e il banco SGM: la nota ha la frequenza chiesta, anche
    fuori dal temperamento grazie al pitch bend, e un'armonica senza vibrato."""
    monkeypatch.setattr(banchi, "cartella_fluidsynth", lambda: FLUIDSYNTH_DI_METEORA)
    banchi.chiudi()
    try:
        for frequenza in (440.0, 446.0, 261.63):
            mono = banchi.rendi_nota(BANCO_SGM, GBAudio.PROGRAMMA_ARMONICA, frequenza, 1.0, 48000)
            assert len(mono) == int(1.0 * 48000) + int(banchi.CODA * 48000)
            letture = [accordatore.rileva_frequenza(mono[i:i + 4096], 48000) for i in range(9600, 40000, 4096)]
            centesimi = [1200 * math.log2(f / frequenza) for f in letture if f > 0]
            assert centesimi and max(abs(c) for c in centesimi) < 8, (frequenza, centesimi)
        assert float(np.abs(mono).max()) > 0.05
    finally:
        banchi.chiudi()


@pytest.mark.skipif(not CI_SONO, reason="FluidSynth di MeTeOra o banco SGM assenti")
def test_gli_strumenti_del_banco_hanno_lo_stesso_livello(monkeypatch):
    """Il DO centrale di ogni strumento arriva al picco di riferimento:
    l'armonica e la chitarra del banco SGM partivano da 0,09 e 0,45."""
    monkeypatch.setattr(banchi, "cartella_fluidsynth", lambda: FLUIDSYNTH_DI_METEORA)
    banchi.chiudi()
    try:
        for programma in (GBAudio.PROGRAMMA_ARMONICA, 24, 0):
            renderer = banchi.RendererBanco(BANCO_SGM, programma, 48000)
            renderer.set_params(261.63, 0.5, 1.0)
            picco = float(np.abs(renderer.render()).max())
            assert picco == pytest.approx(banchi.PICCO_DI_RIFERIMENTO, rel=0.1), programma
    finally:
        banchi.chiudi()


def test_scegliere_un_banco_dalle_impostazioni(monkeypatch, tmp_path):
    """Il percorso a copione: FluidSynth gia' presente, un banco trovato sui
    dischi, scelto, con il volume, e usato come suono attivo."""
    import gestore_impostazioni
    trovato = str(tmp_path / "Bello.sf2")
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "", "volume": 0.8}, "tipo_suono": "suono_1"})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(banchi, "fluidsynth_presente", lambda: True)
    monkeypatch.setattr(banchi, "cerca_banchi", lambda **_k: [(trovato, 30_000_000)])
    monkeypatch.setattr(gestore_impostazioni, "enter_escape", lambda *_a: True)
    viste = []

    def menu_finto(**opzioni):
        viste.append(opzioni["d"])
        return trovato

    monkeypatch.setattr(gestore_impostazioni, "menu", menu_finto)
    risposte = iter([0.6, "s"])
    monkeypatch.setattr(gestore_impostazioni, "dgt", lambda *_a, **_k: next(risposte))
    monkeypatch.setattr(gestore_impostazioni, "key", lambda *_a, **_k: "")
    gestore_impostazioni._configura_banco()
    assert config.impostazioni["banco"] == {"percorso": trovato, "volume": 0.6}
    assert config.impostazioni["tipo_suono"] == "banco"
    assert list(viste[0]) == [trovato, "scarica"]
    assert viste[0][trovato].startswith("Bello.sf2, 30 MB, in ")
