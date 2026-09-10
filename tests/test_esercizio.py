# Chitabry, prove dell'esercizio delle scale: griglia dei battiti, note sintetizzate in anticipo, click MIDI.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Niente audio e niente attese vere: il mixer e' un registratore, la tastiera
# e' muta salvo copione, la sintesi e' finta, e un orologio finto avanza solo
# quando qualcuno aspetta o sintetizza. Cosi' gli istanti dei pizzichi sulla
# griglia si controllano al millesimo, e il file gira in un attimo.

import time
from types import SimpleNamespace

import numpy as np
import pytest

import config
import esercizio_scale
import GBAudio
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

    def pluck(self, voce, mono):
        self.pizzichi.append((voce, len(mono), self.orologio()))

    def mute(self, voce=None):
        self.muti.append(voce)

    def set_pan(self, voce, pan):
        self.pan[voce] = pan

    def istanti(self, voce):
        return [t for v, _, t in self.pizzichi if v == voce]

    def voci_note(self):
        return [v for v, _, _ in self.pizzichi if v < VOCE_CLICK]


class TastieraMuta:
    """Al posto di key: fa avanzare l'orologio di quanto chiesto e risponde con
    il tasto previsto dal copione alla chiamata indicata, altrimenti con niente."""
    def __init__(self, orologio):
        self.orologio = orologio
        self.chiamate = 0
        self.copione = {}

    def __call__(self, prompt="", attesa=None, alla_scadenza=""):
        self.chiamate += 1
        if attesa:
            self.orologio.avanza(attesa)
        return self.copione.get(self.chiamate, "")


@pytest.fixture
def esercizio(monkeypatch):
    orologio = Orologio()
    monkeypatch.setattr(esercizio_scale, "orologio", orologio)
    monkeypatch.setattr(config, "impostazioni", config.get_impostazioni_default())
    beep = (np.ones(70, dtype=np.float32), np.ones(40, dtype=np.float32))
    monkeypatch.setattr(esercizio_scale.Esercizio, "_beep_metronomo", staticmethod(lambda: beep))
    mixer = MixerFinto(orologio)
    monkeypatch.setattr(GBAudio, "PolyphonicPlayer", lambda **kwargs: mixer)
    resi = []

    def sintesi_finta(renderer):
        resi.append(renderer.pluck_hardness > 0)   # True se Karplus-Strong, cioe' suono_1
        orologio.avanza(SINTESI_LENTA)
        return np.ones(100, dtype=np.float32)

    monkeypatch.setattr(suoni, "mono_da_renderer", sintesi_finta)
    midi = []

    def midi_finto(note_num, duration, velocity=127, canale=0):
        midi.append((note_num, duration, velocity, canale, orologio()))

    monkeypatch.setattr(GBAudio, "play_midi_note_temp", midi_finto)
    controlli = []
    porta = SimpleNamespace(h_midi=1,
                            control_change=lambda cc, valore, canale=0: controlli.append(("cc", cc, valore, canale)),
                            program_change=lambda programma, canale=0: controlli.append(("pc", programma, canale)))
    monkeypatch.setattr(GBAudio, "get_midi_out", lambda: porta)
    tastiera = TastieraMuta(orologio)
    monkeypatch.setattr(esercizio_scale, "key", tastiera)
    scala = SimpleNamespace(frequenze=list(FREQUENZE), testo_note=lambda direzione: "Do Re Mi Fa Sol")
    e = esercizio_scale.Esercizio(scala)
    e._configura_renderer()
    e.bpm = 600   # un decimo di secondo a battito
    e.orologio = orologio
    e.resi = resi
    e.midi = midi
    e.controlli = controlli
    e.porta = porta
    e.tastiera = tastiera
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
    esercizio._cambia_suono()   # a midi: nessuna sintesi
    esercizio._suona_sequenza(False)
    assert len(esercizio.resi) == 11
    assert len(esercizio.midi) == 5


def test_la_tastiera_si_guarda_anche_se_la_sintesi_mangia_il_battito(esercizio):
    esercizio.bpm = 3000   # 20 ms a battito, contro 50 ms di sintesi
    esercizio.tastiera.copione = {3: chr(27)}
    assert esercizio._suona_sequenza(False) == 'interrotto'
    assert len(esercizio.resi) < 5


def test_con_il_suono_midi_anche_il_click_e_midi(esercizio):
    esercizio.suono = 'midi'
    esercizio._configura_renderer()
    esercizio.metronomo = True
    esercizio._suona_sequenza(False)
    assert esercizio.poly.pizzichi == []
    assert esercizio.resi == []
    note = [m for m in esercizio.midi if m[3] == 0]
    click = [m for m in esercizio.midi if m[3] == GBAudio.CANALE_CLICK]
    assert [m[0] for m in note] == [60, 62, 64, 65, 67]
    # La nota si spegne un po' prima del battito seguente, per non spegnere quella nuova
    assert all(m[1] == pytest.approx(0.1 - esercizio_scale.ANTICIPO_NOTE_OFF) for m in note)
    battuta = [esercizio_scale.NOTA_ACCENTO] + [esercizio_scale.NOTA_TICK] * 3
    assert [m[0] for m in click] == battuta * 2
    assert all(m[1] == esercizio_scale.DURATA_CLICK_MIDI for m in click)
    assert click[0][2] == esercizio_scale.VELOCITA_ACCENTO
    assert click[1][2] == esercizio_scale.VELOCITA_TICK
    assert [m[4] for m in click] == pytest.approx([k * 0.1 for k in range(8)])
    assert [m[4] for m in note] == pytest.approx([k * 0.1 for k in range(5)])
    canale = GBAudio.CANALE_CLICK
    assert esercizio.controlli == [("pc", GBAudio.PROGRAMMA_WOODBLOCK, canale), ("cc", GBAudio.CC_PAN, GBAudio.PAN_CENTRO, canale),
                                   ("cc", GBAudio.CC_RIVERBERO, 0, canale), ("cc", GBAudio.CC_CHORUS, 0, canale)]


def test_senza_porta_midi_il_click_resta_sul_mixer(esercizio):
    esercizio.suono = 'midi'
    esercizio.porta.h_midi = None
    esercizio._configura_renderer()
    esercizio.metronomo = True
    esercizio._suona_sequenza(False)
    assert esercizio.controlli == []
    assert [m for m in esercizio.midi if m[3] == GBAudio.CANALE_CLICK] == []
    assert [n for v, n, _ in esercizio.poly.pizzichi if v == VOCE_CLICK] == [70, 40, 40, 40, 70, 40, 40, 40]


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


def test_i_messaggi_midi_portano_il_canale():
    out = GBAudio.WindowsMidiOut.__new__(GBAudio.WindowsMidiOut)
    inviati = []
    out.winmm = SimpleNamespace(midiOutShortMsg=lambda h, msg: inviati.append(msg))
    out.h_midi = 1
    out.active_program = -1
    out.note_on(60, 100)
    out.note_on(81, 127, GBAudio.CANALE_CLICK)
    out.note_off(60)
    out.note_off(81, GBAudio.CANALE_CLICK)
    out.control_change(GBAudio.CC_PAN, GBAudio.PAN_CENTRO, GBAudio.CANALE_CLICK)
    out.program_change(GBAudio.PROGRAMMA_WOODBLOCK, GBAudio.CANALE_CLICK)
    out.select_instrument(24)
    out.select_instrument(24)   # lo stesso strumento non si rimanda
    assert inviati == [(100 << 16) | (60 << 8) | 0x90, (127 << 16) | (81 << 8) | 0x91, (60 << 8) | 0x80, (81 << 8) | 0x81,
                       (64 << 16) | (10 << 8) | 0xB1, (115 << 8) | 0xC1, (24 << 8) | 0xC0]
    out.h_midi = None
    out.note_on(60)
    out.control_change(GBAudio.CC_CHORUS, 0)
    out.program_change(0)
    assert len(inviati) == 7


def test_la_nota_a_tempo_spegne_sul_canale_giusto(monkeypatch):
    messaggi = []
    finto = SimpleNamespace(h_midi=1,
                            note_on=lambda nota, velocity=127, canale=0: messaggi.append(("on", nota, velocity, canale)),
                            note_off=lambda nota, canale=0: messaggi.append(("off", nota, canale)))
    monkeypatch.setattr(GBAudio, "_midi_out", finto)
    GBAudio.play_midi_note_temp(81, 0.01, 100, canale=GBAudio.CANALE_CLICK)
    time.sleep(0.1)
    assert messaggi == [("on", 81, 100, GBAudio.CANALE_CLICK), ("off", 81, GBAudio.CANALE_CLICK)]
