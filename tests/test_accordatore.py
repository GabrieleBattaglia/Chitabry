# Chitabry, prove dell'accordatore: rilevamento della nota, riga mostrata, scelta della periferica.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nate con la 9.8.2, dopo il collaudo del 7 ottobre 2026. Niente microfono:
# i blocchi sono toni sintetici di frequenza nota, le periferiche finte.

import math

import numpy as np
import pytest

import accordatore

SR = 48000


def tono(frequenza, armoniche=8, debole=False, sr=SR, campioni=None):
    """Un blocco di ancia sintetica: armoniche decrescenti, o con la
    fondamentale debole, che e' il caso che provoca gli errori d'ottava."""
    t = np.arange(campioni or accordatore.BLOCK_SIZE) / sr
    pesi = {1: 0.25, 2: 1.0, 3: 0.8, 4: 0.6} if debole else {k: 1 / k for k in range(1, armoniche + 1)}
    y = sum(p * np.sin(2 * np.pi * k * frequenza * t) for k, p in pesi.items() if k * frequenza < sr / 2.2)
    return (0.3 * y / np.max(np.abs(y))).astype(np.float32)


def centesimi(trovata, vera):
    return 1200 * math.log2(trovata / vera)


@pytest.mark.parametrize("midi", [21, 23, 28, 40, 45, 57, 69, 81, 93, 96, 102, 105, 108])
def test_la_nota_si_trova_su_tutta_l_estensione(midi):
    """Dal LA0 del pianoforte al DO8, nessun errore d'ottava: fino alla 9.6
    sopra i 1900 Hz si leggeva un'ottava sotto, e il MI1 e il SI0 non si
    leggevano affatto; fino alla 9.10.0 il LA7 e il DO8 con la fondamentale
    debole risultavano un'ottava sotto."""
    vera = 440 * 2 ** ((midi - 69) / 12)
    for sr in (44100, 48000):
        for debole in (False, True):
            trovata = accordatore.rileva_frequenza(tono(vera, debole=debole, sr=sr), sr)
            assert abs(centesimi(trovata, vera)) < 20, (midi, sr, debole, trovata)


def test_il_la0_calante_si_legge():
    """Il LA0 sta sul limite basso: calante, o con le letture appena sotto i
    27,5 Hz, la riga restava sulla nota di prima."""
    calante = 27.5 * 2 ** (-12 / 1200)
    trovata = accordatore.rileva_frequenza(tono(calante), SR)
    assert abs(centesimi(trovata, calante)) < 5
    assert accordatore.frequenza_da_mostrare([27.4841] * 11) == pytest.approx(27.4841)
    assert accordatore.frequenza_da_mostrare([27.4999996] * 3) is not None


@pytest.mark.parametrize("sr", [88200, 96000, 192000])
def test_le_note_gravi_ad_alta_frequenza_di_campionamento(sr):
    """Sopra i 56 kHz il blocco di 4096 campioni non teneva il periodo delle
    note gravi, e il MI1 del basso usciva FA#1: adesso il blocco cresce con
    la frequenza di campionamento, e una valle che esce dal blocco non da'
    una nota sbagliata ma nessuna."""
    blocco = accordatore.dimensione_del_blocco(sr)
    assert 0.08 < blocco / sr < 0.1
    for vera in (30.87, 41.2, 82.41):
        trovata = accordatore.rileva_frequenza(tono(vera, sr=sr, campioni=blocco), sr)
        assert abs(centesimi(trovata, vera)) < 5, (sr, vera, trovata)
        corta = accordatore.rileva_frequenza(tono(vera, sr=sr, campioni=accordatore.BLOCK_SIZE), sr)
        assert corta == 0.0 or abs(centesimi(corta, vera)) < 5, (sr, vera, corta)
    assert accordatore.dimensione_del_blocco(44100) == accordatore.dimensione_del_blocco(48000) == accordatore.BLOCK_SIZE


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


def test_la_riga_di_ascolto_ogni_mezzo_secondo(monkeypatch, capsys):
    """Con molte periferiche che falliscono subito, la riga si riscriveva
    ogni decimo di secondo invece che ogni mezzo."""
    import time

    def misura(idx, secondi=0, livelli=None):
        if idx < 8:
            raise OSError("non si apre")
        time.sleep(1.0)
        return 0.0

    monkeypatch.setattr(accordatore, "_misura_rumore", misura)
    accordatore._rileva_dispositivi_attivi({str(i): f"Micro {i}" for i in range(10)})
    assert capsys.readouterr().out.count("Ascolto") <= 4


def finta_scelta(monkeypatch, dispositivi, ricerca, predefinito):
    """Accordatore fino alla scelta della periferica: il flusso audio non si
    apre, e cio' che il menu riceve resta in viste."""
    monkeypatch.setattr(accordatore, "_dispositivi_di_ingresso", lambda: dispositivi)
    monkeypatch.setattr(accordatore, "_rileva_dispositivi_attivi", lambda d: d)
    monkeypatch.setattr(accordatore, "enter_escape", lambda *_a: ricerca)
    monkeypatch.setattr(accordatore.sd, "default", type("Predefiniti", (), {"device": (predefinito, 4)})())
    monkeypatch.setattr(accordatore.sd, "query_devices", lambda *_a, **_k: {"default_samplerate": 48000})

    def flusso(*_a, **_k):
        raise accordatore.sd.PortAudioError("finto")

    monkeypatch.setattr(accordatore.sd, "InputStream", flusso)
    monkeypatch.setattr(accordatore, "key", lambda *_a, **_k: "")
    viste = {}

    def menu_finto(**opzioni):
        viste.update(opzioni)

    monkeypatch.setattr(accordatore, "menu", menu_finto)
    accordatore.Accordatore()
    return viste


def test_senza_segnale_il_predefinito_viene_prima(monkeypatch):
    """Se la ricerca non sente niente l'elenco e' quello di sempre: il
    prompt diceva che il primo era il piu' forte, ed era solo il primo
    indice, spesso il Mapper di MME."""
    viste = finta_scelta(monkeypatch, {"0": "Mapper", "2": "Microfono USB"}, True, 2)
    assert list(viste["d"]) == ["2", "0"]
    assert "Invio per il primo)" in viste["p"]
    assert viste["empty_enter"] == "2"


def test_con_una_periferica_sola_se_ne_legge_il_nome(monkeypatch, capsys):
    """Con una voce il menu sceglie da solo, e dopo il titolo non si leggeva
    niente: adesso la riga dice quale periferica ascolta."""
    viste = finta_scelta(monkeypatch, {"4": "Microfono [WASAPI]"}, False, 4)
    assert viste == {}
    uscita = capsys.readouterr().out
    assert "Dispositivo di input: Microfono [WASAPI] (predefinito del sistema)" in uscita
    assert "disponibili" not in uscita
