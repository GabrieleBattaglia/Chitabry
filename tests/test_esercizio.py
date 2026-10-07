# Chitabry, prove dell'esercizio delle scale: griglia dei battiti, note sintetizzate in anticipo, note tenute.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Niente audio e niente attese vere: il mixer e' un registratore, la tastiera
# e' muta salvo copione, la sintesi e' finta, e un orologio finto avanza solo
# quando qualcuno aspetta o sintetizza. Cosi' gli istanti dei pizzichi sulla
# griglia si controllano al millesimo, e il file gira in un attimo.

from types import SimpleNamespace

import numpy as np
import pytest

import clitronomo
import config
import esercizio_scale
import GBAudio
import player
import suoni

SINTESI_LENTA = 0.05
FREQUENZE = [261.6, 293.7, 329.6, 349.2, 392.0]
VOCE_CLICK = len(FREQUENZE)


class Orologio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def avanza(self, secondi):
        self.t += secondi


class MixerFinto:
    def __init__(self, orologio):
        self.orologio = orologio
        self.pizzichi = []   # terne (voce, campioni, istante)
        self.muti = []       # la voce zittita, None per tutte
        self.pan = {}
        self.tenute = []     # (voce, campioni) delle note dei tasti
        self.lasciate = []
        self.avviato = self.fermato = False

    def start(self):
        self.avviato = True

    def stop(self):
        self.fermato = True

    def pluck(self, voce, mono):
        self.pizzichi.append((voce, len(mono), self.orologio()))

    def tieni(self, voce, mono, ciclo=None):
        self.tenute.append((voce, len(mono)))

    def lascia(self, voce, secondi=0.06):
        self.lasciate.append(voce)

    def mute(self, voce=None):
        self.muti.append(voce)

    def set_pan(self, voce, pan):
        self.pan[voce] = pan

    def istanti(self, voce):
        return [t for v, _, t in self.pizzichi if v == voce]

    def voci_note(self):
        return [v for v, _, _ in self.pizzichi if v < VOCE_CLICK]


class TastieraMuta:
    """Al posto della tastiera a eventi: fa avanzare l'orologio di quanto
    chiesto e consegna gli eventi previsti dal copione alla chiamata
    indicata, un tasto come pressione o una lista di eventi, altrimenti
    niente; senza attesa e a copione finito, Esc."""
    tiene = True

    def __init__(self, orologio):
        self.orologio = orologio
        self.chiamate = 0
        self.copione = {}
        self.chiusa = False

    def eventi(self, attesa=None):
        self.chiamate += 1
        if attesa:
            self.orologio.avanza(attesa)
        voce = self.copione.get(self.chiamate)
        if voce is None:
            return [(chr(27), "giu")] if attesa is None else []
        return [(voce, "giu")] if isinstance(voce, str) else list(voce)

    def chiudi(self):
        self.chiusa = True


@pytest.fixture
def esercizio(monkeypatch):
    orologio = Orologio()
    monkeypatch.setattr(esercizio_scale, "orologio", orologio)
    monkeypatch.setattr(config, "impostazioni", config.get_impostazioni_default())
    beep = (np.ones(70, dtype=np.float32), np.ones(40, dtype=np.float32))
    monkeypatch.setattr(esercizio_scale.Esercizio, "_preset_metronomo",
                        staticmethod(lambda: (clitronomo.CONFIG_ACCENTO, clitronomo.CONFIG_TICK)))
    monkeypatch.setattr(esercizio_scale.Esercizio, "_beep_metronomo", staticmethod(lambda accento, tick: beep))
    mixer = MixerFinto(orologio)
    monkeypatch.setattr(GBAudio, "PolyphonicPlayer", lambda **kwargs: mixer)
    resi = []

    def sintesi_finta(renderer):
        resi.append(renderer.pluck_hardness > 0)   # True se Karplus-Strong, cioe' suono_1
        orologio.avanza(SINTESI_LENTA)
        return np.ones(100, dtype=np.float32)

    monkeypatch.setattr(suoni, "mono_da_renderer", sintesi_finta)
    monkeypatch.setattr(suoni, "tenuta_da_renderer", lambda renderer: (np.ones(300, dtype=np.float32), None))
    tastiera = TastieraMuta(orologio)
    monkeypatch.setattr(player, "apri_tastiera", lambda: tastiera)
    scala = SimpleNamespace(frequenze=list(FREQUENZE), testo_note=lambda direzione: "Do Re Mi Fa Sol")
    e = esercizio_scale.Esercizio(scala)
    e._configura_renderer()
    e.bpm = 600   # un decimo di secondo a battito
    e.orologio = orologio
    e.resi = resi
    e.tastiera = tastiera
    e.tasti = tastiera
    return e


def test_le_voci_del_mixer_hanno_il_click_al_centro(esercizio):
    assert esercizio.poly.pan[VOCE_CLICK] == 0.0
    assert esercizio.poly.pan[0] == pytest.approx(-0.8)
    assert esercizio.poly.pan[4] == pytest.approx(0.8)


def test_con_il_metronomo_la_battuta_si_completa(esercizio):
    esercizio.metronomo = True
    assert esercizio._suona_sequenza(False) is None
    assert esercizio.poly.voci_note() == [0, 1, 2, 3, 4]
    click = [n for v, n, _ in esercizio.poly.pizzichi if v == VOCE_CLICK]
    assert click == [70, 40, 40, 40, 70, 40, 40, 40]   # accento sul primo e sul quinto battito
    assert esercizio.poly.muti == [0, 1, 2, 3, 4]
    assert esercizio.ultima_voce is None


def test_senza_metronomo_l_ultima_nota_resta(esercizio):
    esercizio.direzione = 'd'
    assert esercizio._suona_sequenza(False) is None
    assert esercizio.poly.voci_note() == [4, 3, 2, 1, 0]
    assert esercizio.poly.muti == [4, 3, 2, 1]
    assert esercizio.ultima_voce == 0


def test_i_battiti_cadono_sulla_griglia_nonostante_la_sintesi(esercizio):
    """La prima nota si prepara prima di fissare la griglia; le altre durante
    l'attesa del battito precedente. I pizzichi, note e click, cadono a un
    decimo esatto l'uno dall'altro: contando la sintesi a ogni battito, come
    si faceva prima, i primi cinque intervalli sarebbero di 0.15."""
    esercizio.metronomo = True
    esercizio._suona_sequenza(False)
    origine = SINTESI_LENTA   # la prima nota e' pronta quando la griglia parte
    attesi = [origine + k * 0.1 for k in range(8)]
    assert esercizio.poly.istanti(VOCE_CLICK) == pytest.approx(attesi)
    note = [t for v, _, t in esercizio.poly.pizzichi if v < VOCE_CLICK]
    assert note == pytest.approx(attesi[:5])
    assert esercizio.orologio() == pytest.approx(origine + 0.8)


def test_in_loop_la_griglia_continua(esercizio):
    assert esercizio._suona_sequenza(True) is None
    griglia = esercizio.griglia
    assert griglia == pytest.approx(SINTESI_LENTA + 0.5)
    # Fra un giro e l'altro passa un po' di tempo, per la riga di stato: il
    # giro dopo resta sulla griglia di prima invece di ripartire da adesso
    esercizio.orologio.avanza(0.02)
    assert esercizio._suona_sequenza(True) is None
    assert esercizio.poly.istanti(0)[1] == pytest.approx(griglia + 0.02)   # in ritardo di poco, si riassorbe
    assert esercizio.poly.istanti(1)[1] == pytest.approx(griglia + 0.1)    # gia' di nuovo sulla griglia
    assert esercizio.griglia == pytest.approx(griglia + 0.5)
    esercizio._suona_sequenza(False)
    assert esercizio.griglia is None


def test_un_ritardo_piccolo_si_riassorbe_uno_grosso_fa_ripartire_la_griglia(esercizio):
    esercizio._prepara(0)
    adesso = esercizio.orologio()
    esercizio.griglia = adesso - 0.03   # meno di mezzo battito: il battito dopo arriva prima
    esercizio._suona_sequenza(True)
    assert esercizio.poly.istanti(0) == pytest.approx([adesso])
    assert esercizio.poly.istanti(1) == pytest.approx([adesso + 0.07])
    adesso = esercizio.orologio()
    esercizio.griglia = adesso - 1.0   # troppo indietro: si riparte da qui, senza raffica
    esercizio._suona_sequenza(True)
    assert esercizio.poly.istanti(0)[1] == pytest.approx(adesso)
    assert esercizio.poly.istanti(1)[1] == pytest.approx(adesso + 0.1)
    assert esercizio.poly.istanti(4)[1] == pytest.approx(adesso + 0.4)


def test_ogni_pizzico_ha_la_sua_sintesi_fatta_in_anticipo(esercizio):
    esercizio._suona_sequenza(False)
    # Cinque note suonate piu' la prima del giro dopo, gia' pronta: nient'altro in memoria
    assert len(esercizio.resi) == 6
    assert list(esercizio.note_pronte) == [0]
    esercizio._suona_sequenza(False)
    assert len(esercizio.resi) == 11   # come una corda vera, ogni pizzico e' nuovo
    esercizio._cambia_suono()   # da suono_1 a suono_2: la scorta si butta
    assert esercizio.note_pronte == {}
    esercizio._suona_sequenza(False)
    assert len(esercizio.resi) == 17


def test_la_tastiera_si_guarda_anche_se_la_sintesi_mangia_il_battito(esercizio):
    esercizio.bpm = 3000   # 20 ms a battito, contro 50 ms di sintesi
    esercizio.tastiera.copione = {3: chr(27)}
    assert esercizio._suona_sequenza(False) == 'interrotto'
    assert len(esercizio.resi) < 5


def test_esc_e_l_fermano_l_ascolto(esercizio):
    esercizio.tastiera.copione = {2: chr(27)}
    assert esercizio._suona_sequenza(False) == 'interrotto'
    assert esercizio.poly.muti[-1] is None
    assert esercizio.ultima_voce is None
    esercizio.tastiera.copione = {esercizio.tastiera.chiamate + 1: 'l'}
    assert esercizio._suona_sequenza(True) == 'fermato'
    assert esercizio.griglia is None
    esercizio.tastiera.copione = {esercizio.tastiera.chiamate + 1: chr(27)}
    assert esercizio._suona_sequenza(True) == 'esci'


def test_lo_spazio_cambia_suono_e_riprepara_la_nota(esercizio):
    esercizio.tastiera.copione = {1: ' '}
    esercizio._suona_sequenza(False)
    assert esercizio.suono == 'suono_2'
    # La prima e la seconda nota col suono 1, poi la seconda rifatta subito
    # dopo il cambio e le altre col suono 2, compresa la prima per il giro dopo
    assert esercizio.resi == [True, True, False, False, False, False, False]


def test_il_click_e_sempre_il_beep_del_preset(esercizio):
    """Dalla 10.0.0 non c'e' piu' il wood block del MIDI di Windows: con
    qualunque suono il battito e' il beep del preset, sul mixer con le note."""
    esercizio.suono = 'suono_2'
    esercizio._configura_renderer()
    esercizio.metronomo = True
    esercizio._suona_sequenza(False)
    assert [n for v, n, _ in esercizio.poly.pizzichi if v == VOCE_CLICK] == [70, 40, 40, 40, 70, 40, 40, 40]


def test_i_tasti_delle_note_suonano_finche_sono_giu(esercizio, monkeypatch, capsys):
    """Collaudo di Gabriele del 7 ottobre 2026: come nella Tastiera, la nota
    di un tasto dura finche' il tasto e' giu', e lasciarlo la chiude. Il loop
    della scala tiene le sue durate."""
    monkeypatch.setattr(esercizio_scale.Esercizio, "_riga_stato", lambda self, in_loop: None)
    esercizio.tastiera.copione = {1: [("1", "giu")], 2: [("3", "giu"), ("1", "su")], 3: [("3", "su")]}
    esercizio.avvia()
    assert esercizio.poly.tenute == [(0, 300), (2, 300)]
    assert esercizio.poly.lasciate == [0, 2]
    assert esercizio.poly.pizzichi == []
    assert esercizio.tastiera.chiusa and esercizio.poly.fermato


def test_le_note_tenute_si_chiudono_prima_dell_ascolto_e_dei_bpm(esercizio, monkeypatch):
    """Durante l'ascolto a tempo i rilasci non si guardano, e i BPM chiudono
    la tastiera con i suoi rilasci in attesa: la nota di un tasto restava
    accesa sotto la scala, o per sempre."""
    monkeypatch.setattr(esercizio_scale.Esercizio, "_riga_stato", lambda self, in_loop: None)
    esercizio.tastiera.copione = {1: [("1", "giu")], 2: [("d", "giu")]}
    esercizio.avvia()
    assert esercizio.poly.lasciate == [0]
    assert esercizio.poly.voci_note() == [4, 3, 2, 1, 0]


def test_i_bpm_chiudono_le_note_tenute(esercizio, monkeypatch):
    monkeypatch.setattr(esercizio_scale.Esercizio, "_riga_stato", lambda self, in_loop: None)
    monkeypatch.setattr(esercizio_scale, "dgt", lambda *_a, **_k: 90)
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    prima = esercizio.tastiera
    prima.copione = {1: [("2", "giu")], 2: [("b", "giu")]}
    # La tastiera riaperta dopo la domanda non ha copione: Esc
    dopo = TastieraMuta(esercizio.orologio)
    monkeypatch.setattr(player, "apri_tastiera", lambda: prima if not prima.chiamate else dopo)
    esercizio.avvia()
    assert esercizio.poly.lasciate == [1]
    assert esercizio.bpm == 90 and prima.chiusa


def test_i_bpm_si_chiedono_a_tastiera_chiusa(esercizio, monkeypatch):
    """dgt legge la console: la tastiera a eventi si chiude prima della
    domanda e se ne apre una nuova dopo."""
    aperte = []
    monkeypatch.setattr(player, "apri_tastiera", lambda: aperte.append(TastieraMuta(esercizio.orologio)) or aperte[-1])
    monkeypatch.setattr(esercizio_scale, "dgt", lambda *_a, **_k: 120)
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    esercizio._imposta_bpm()
    assert esercizio.tastiera.chiusa
    assert esercizio.tasti is aperte[0]
    assert esercizio.bpm == 120
