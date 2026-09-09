# Chitabry, prove del metronomo senza aprire nessun dispositivo audio.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# I preset vivono in una cartella temporanea; il programma e le rampe si
# provano facendo avanzare le battute a mano, come farebbe la callback.

import json
import os

import numpy as np

import clitronomo


def _avanza_battuta(m):
    """Cio' che fa la callback a fine battuta, senza audio: mette in
    riproduzione il nastro in attesa e conta la battuta."""
    if m.pending_buffer is not None:
        m.active_buffer = m.pending_buffer
        m.pending_buffer = None
    m.session_measure_count += 1
    m.playback_index = 0
    m._annuncia()
    m._prepara_prossima_battuta()


def test_lunghezza_battuta_arrotondata():
    m = clitronomo.Metronome(bpm=130, time_signature="4/4")
    buffer = m._generate_measure_buffer()
    campioni_battito = round(60.0 / 130 * clitronomo.SAMPLE_RATE)
    assert campioni_battito == 20354
    assert len(buffer) == campioni_battito * 4
    assert buffer.dtype == np.int16
    assert np.abs(buffer).max() > 0
    silenzio = m._generate_measure_buffer(is_silent=True)
    assert len(silenzio) == len(buffer)
    assert not silenzio.any()


def test_rampa_del_programma(capsys):
    m = clitronomo.Metronome(bpm=100, time_signature="4/4")
    m.program = [{"start_bar": 1, "end_bar": 5, "target_bpm": 140, "is_audible": True}]
    m.active_buffer = m._generate_measure_buffer()
    m._prepara_prossima_battuta()  # battuta 1: parte la rampa
    bpm_visti = [m.bpm]
    for _ in range(6):
        _avanza_battuta(m)
        bpm_visti.append(m.bpm)
    assert bpm_visti == [100, 110, 120, 130, 140, 140, 140]
    assert not m.bpm_ramp_active
    uscita = capsys.readouterr().out
    assert "Programma: battute da 1 a 5, target 140 BPM, suono attivo." in uscita
    assert "fine segmento" in uscita


def test_segmento_muto_produce_silenzio():
    m = clitronomo.Metronome(bpm=120, time_signature="2/4")
    m.program = [{"start_bar": 1, "end_bar": 3, "target_bpm": 120, "is_audible": False}]
    m.active_buffer = m._generate_measure_buffer()
    m._prepara_prossima_battuta()
    assert m.is_muted_by_program
    assert m.pending_buffer is not None
    assert not m.pending_buffer.any()
    for _ in range(3):
        _avanza_battuta(m)
    assert not m.is_muted_by_program
    assert m.pending_buffer.any()


def test_battute_fantasma_cicliche():
    m = clitronomo.Metronome(bpm=200, time_signature="1/4")
    m.ghost_mode = "cyclic"
    m.ghost_cyclic_audible = 2
    m.ghost_cyclic_silent = 1
    m.active_buffer = m._generate_measure_buffer()
    m._prepara_prossima_battuta()
    stati = [m.is_muted_by_ghost]
    for _ in range(6):
        _avanza_battuta(m)
        stati.append(m.is_muted_by_ghost)
    # Battute 1 e 2 suonano, la 3 e' muta, e cosi' via
    assert stati == [False, False, True, False, False, True, False]


def test_preset_salvati_e_riletti(tmp_path):
    percorso = str(tmp_path / "presets.json")
    pm = clitronomo.PresetManager(filename=percorso, silenzioso=True)
    assert not os.path.exists(percorso)
    m = clitronomo.Metronome(bpm=90)
    pid = pm.save_preset("Esercizio veloce con accento è", m.get_state())
    assert pid == "1"
    assert os.path.exists(percorso)
    pm.save_preset("Secondo", m.get_state())
    assert os.path.exists(percorso + ".bak")
    assert not os.path.exists(percorso + ".tmp")
    pm.set_last_used("2")
    pm2 = clitronomo.PresetManager(filename=percorso, silenzioso=True)
    assert sorted(pm2.data["presets"]) == ["1", "2"]
    assert pm2.data["presets"]["1"]["name"] == "ID1 Esercizio veloce con accento è"
    last_id, stato = pm2.get_last_used_preset()
    assert last_id == "2"
    assert stato["bpm"] == 90


def test_preset_illeggibile_messo_da_parte(tmp_path, capsys):
    percorso = str(tmp_path / "presets.json")
    with open(percorso, "w", encoding="utf-8") as f:
        f.write("{ rotto")
    pm = clitronomo.PresetManager(filename=percorso)
    assert pm.data == {"last_preset_id": None, "presets": {}}
    assert not os.path.exists(percorso)
    messi_da_parte = [n for n in os.listdir(tmp_path) if n.startswith("presets.json.illeggibile-")]
    assert len(messi_da_parte) == 1
    with open(tmp_path / messi_da_parte[0], encoding="utf-8") as f:
        assert f.read() == "{ rotto"
    assert "messo da parte" in capsys.readouterr().out


def test_preset_senza_struttura_non_viene_sovrascritto(tmp_path):
    percorso = str(tmp_path / "presets.json")
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump([1, 2, 3], f)
    clitronomo.PresetManager(filename=percorso, silenzioso=True)
    assert not os.path.exists(percorso)
    assert any(n.startswith("presets.json.illeggibile-") for n in os.listdir(tmp_path))
