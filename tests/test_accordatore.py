# Chitabry, prove dell'accordatore: rilevamento della nota, riga mostrata, scelta della periferica.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nate con la 9.8.2, dopo il collaudo del 7 ottobre 2026. Niente microfono:
# i blocchi sono toni sintetici di frequenza nota, le periferiche finte.

import math

import numpy as np
import pytest

import accordatore

SR = 48000


def tono(frequenza, armoniche=8, debole=False):
    """Un blocco di ancia sintetica: armoniche decrescenti, o con la
    fondamentale debole, che e' il caso che provoca gli errori d'ottava."""
    t = np.arange(accordatore.BLOCK_SIZE) / SR
    pesi = {1: 0.25, 2: 1.0, 3: 0.8, 4: 0.6} if debole else {k: 1 / k for k in range(1, armoniche + 1)}
    y = sum(p * np.sin(2 * np.pi * k * frequenza * t) for k, p in pesi.items() if k * frequenza < SR / 2.2)
    return (0.3 * y / np.max(np.abs(y))).astype(np.float32)


def centesimi(trovata, vera):
    return 1200 * math.log2(trovata / vera)


@pytest.mark.parametrize("midi", [23, 28, 40, 45, 57, 69, 81, 93, 96, 102])
def test_la_nota_si_trova_su_tutta_l_estensione(midi):
    """Dal SI0 del basso a cinque corde al FA#7 di un'armonica acuta, nessun errore d'ottava:
    fino alla 9.6 sopra i 1900 Hz si leggeva un'ottava sotto, e il MI1 e il SI0
    non si leggevano affatto."""
    vera = 440 * 2 ** ((midi - 69) / 12)
    for debole in (False, True):
        trovata = accordatore.rileva_frequenza(tono(vera, debole=debole), SR)
        assert abs(centesimi(trovata, vera)) < 20, (midi, debole, trovata)


def test_nel_registro_centrale_la_precisione_e_sotto_il_centesimo():
    for midi in range(48, 85, 5):
        vera = 440 * 2 ** ((midi - 69) / 12)
        assert abs(centesimi(accordatore.rileva_frequenza(tono(vera), SR), vera)) < 1


def test_il_silenzio_non_ha_nota():
    assert accordatore.rileva_frequenza(np.zeros(accordatore.BLOCK_SIZE, dtype=np.float32), SR) == 0.0


def test_la_media_solo_sulla_stessa_nota():
    """Passando da DO4 a RE4 la riga diceva DO#4 per due secondi."""
    do4, re4 = 261.63, 293.66
    assert accordatore.frequenza_da_mostrare([do4, do4, do4]) == pytest.approx(do4)
    assert accordatore.frequenza_da_mostrare([re4, re4], precedente=do4) == pytest.approx(re4)
    vicina = do4 * 2 ** (10 / 1200)
    attesa = accordatore.EMA_ALPHA * vicina + (1 - accordatore.EMA_ALPHA) * do4
    assert accordatore.frequenza_da_mostrare([vicina], precedente=do4) == pytest.approx(attesa)
    assert accordatore.frequenza_da_mostrare([]) is None
    assert accordatore.frequenza_da_mostrare([20.0]) is None
    # La mediana toglie una lettura sbagliata isolata, come un'ottava
    assert accordatore.frequenza_da_mostrare([do4, do4, 2 * do4, do4]) == pytest.approx(do4)


def test_la_riga_di_ascolto_sta_nei_quaranta_caratteri(monkeypatch):
    monkeypatch.setattr(accordatore.time, "monotonic", lambda: 103.2)
    riga = accordatore._riga_di_ascolto(100.0, {1: 0.02, 2: 0.4})
    assert riga.startswith("\r") and riga.endswith("\r")
    assert riga.strip("\r") == "Ascolto 4/5 s, picco 92 dB"
    assert len(accordatore._riga_di_ascolto(100.0, {1: 1.0}, "Riprovo 12/12:").strip("\r")) <= 40


def test_la_periferica_piu_forte_viene_prima(monkeypatch, capsys):
    livelli = {3: 0.01, 5: 0.2, 7: 0.0001, 9: 0.05}
    monkeypatch.setattr(accordatore, "_misura_rumore", lambda idx, secondi=0, livelli=None: livelli_finti(idx, livelli))

    def livelli_finti(idx, condivisi):
        if condivisi is not None:
            condivisi[idx] = livelli[idx]
        return livelli[idx]

    trovate = accordatore._rileva_dispositivi_attivi({"3": "Micro A", "5": "Micro B", "7": "Muto", "9": "Micro C"})
    assert list(trovate) == ["5", "9", "3"]
    assert trovate["5"] == "Micro B (segnale 86 dB)"
    assert "Ascolto" in capsys.readouterr().out


def test_senza_rilevamento_il_predefinito_viene_prima(monkeypatch):
    monkeypatch.setattr(accordatore.sd, "default", type("Predefiniti", (), {"device": (9, 4)})())
    ordinati = accordatore._predefinito_prima({"3": "Micro A", "9": "Micro C"})
    assert list(ordinati) == ["9", "3"]
    assert ordinati["9"] == "Micro C (predefinito del sistema)"
