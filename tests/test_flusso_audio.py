# Chitabry, prove del dialogo fra callback audio e resto del programma, con un driver finto.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Il driver finto chiama la callback da un thread proprio, come fa quello vero,
# ma non apre nessun dispositivo e non emette nessun suono.

import threading
import time

import numpy as np
import pytest

import clitronomo
import GBAudio

FRAMES = 1024


class FlussoFinto:
    """Al posto di sounddevice.OutputStream: chiama la callback ogni pochi millisecondi."""
    def __init__(self, samplerate, channels, dtype, callback, latency=None):
        self.channels = channels
        self.dtype = dtype
        self.callback = callback
        self._vivo = threading.Event()
        self._thread = None
        self.chiuso = False
        self.blocchi = 0

    def _gira(self):
        while self._vivo.is_set():
            outdata = np.zeros((FRAMES, self.channels), dtype=self.dtype)
            self.callback(outdata, FRAMES, None, None)
            self.blocchi += 1
            time.sleep(0.002)

    def start(self):
        self._vivo.set()
        self._thread = threading.Thread(target=self._gira, daemon=True)
        self._thread.start()

    def stop(self):
        self._vivo.clear()
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def close(self):
        self.chiuso = True


@pytest.fixture
def driver_finto(monkeypatch):
    creati = []

    def fabbrica(**kwargs):
        flusso = FlussoFinto(**kwargs)
        creati.append(flusso)
        return flusso

    monkeypatch.setattr(clitronomo.sd, "OutputStream", fabbrica)
    monkeypatch.setattr(GBAudio.sd, "OutputStream", fabbrica)
    return creati


def test_metronomo_avanza_e_segue_la_rampa(driver_finto, capsys):
    m = clitronomo.Metronome(bpm=600, time_signature="1/4")
    m.program = [{"start_bar": 1, "end_bar": 9, "target_bpm": 1000, "is_audible": True}]
    m.start()
    time.sleep(1.0)
    battute = m.session_measure_count
    bpm = m.bpm
    m.stop()
    assert battute > 10
    assert bpm == 1000
    assert not m.bpm_ramp_active
    assert driver_finto[0].chiuso
    assert m._servizio is None
    uscita = capsys.readouterr().out
    assert "Programma: battute da 1 a 9" in uscita
    assert "fine segmento" in uscita
    assert "Sessione terminata" in uscita


def test_metronomo_riparte_dopo_lo_stop(driver_finto):
    m = clitronomo.Metronome(bpm=600, time_signature="1/4")
    m.start()
    time.sleep(0.3)
    m.stop()
    assert m.session_measure_count > 3
    m.start()
    time.sleep(0.3)
    seconda = m.session_measure_count
    m.stop()
    assert seconda > 3
    assert len(driver_finto) == 2


def test_mixer_polifonico_consuma_i_buffer(driver_finto):
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=2)
    player.start()
    nota = np.ones(FRAMES * 3, dtype=np.float32) * 0.5
    player.pluck(0, nota)
    player.pluck(1, nota[:FRAMES])
    time.sleep(0.2)
    assert player.indices[0] == len(nota)
    assert player.indices[1] == FRAMES
    player.pluck(0, nota)
    assert player.indices[0] == 0
    player.stop()
    assert driver_finto[0].chiuso
    assert player.stream is None
    assert not player.is_running
    assert all(len(b) == 0 for b in player.buses)


def test_mixer_pluck_e_mute_sotto_pressione(driver_finto):
    """Pizzicare e zittire di continuo mentre la callback legge non deve mai
    lasciare un indice oltre la fine del suo buffer."""
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=4)
    player.start()
    nota = np.random.uniform(-0.5, 0.5, FRAMES * 4).astype(np.float32)
    fine = time.time() + 0.5
    errori = []

    def martella():
        while time.time() < fine:
            for i in range(4):
                player.pluck(i, nota)
                player.mute(i)
                player.pluck(i, nota[: FRAMES // 3])

    thread = threading.Thread(target=martella)
    thread.start()
    while time.time() < fine:
        with player._lock:
            for i in range(4):
                if player.indices[i] > len(player.buses[i]):
                    errori.append((i, player.indices[i], len(player.buses[i])))
        time.sleep(0.001)
    thread.join()
    player.stop()
    assert errori == []
