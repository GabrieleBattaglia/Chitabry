# Chitabry, prove del Player Generico a tasti tenuti.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5, modalita' auto).
# Nate con la issue 55, il 14 settembre 2026. Non aprono nessun dispositivo e
# non leggono nessuna tastiera: gli eventi arrivano da una finta, e il mixer e'
# un finto che si limita a segnare le chiamate che riceve.

import numpy as np
import pytest

import config
import GBAudio
import player
import suoni


class TastieraFinta:
    """Consegna i giri di eventi che le si danno, poi Esc per far uscire il
    player: senza, il ciclo aspetterebbe per sempre."""

    def __init__(self, giri, tiene=True):
        self.giri = list(giri)
        self.tiene = tiene
        self.chiusa = False
        self.premuti = frozenset()

    def eventi(self, attesa=None):
        if not self.giri:
            return [("\x1b", "giu")]
        return self.giri.pop(0)

    def chiudi(self):
        self.chiusa = True


class PolyFinto:
    """Al posto di PolyphonicPlayer: niente audio, solo il verbale."""

    def __init__(self, fs=None, num_strings=16):
        self.num_strings = num_strings
        self.chiamate = []
        self.occupate = set()
        self.rubate = []
        self.rilasci = []
        self.avviato = False
        self.fermato = False

    def start(self):
        self.avviato = True

    def stop(self):
        self.fermato = True

    def tieni(self, voce, mono, ciclo=None):
        if voce in self.occupate:
            # Una voce presa mentre stava ancora suonando: la nota di prima
            # verrebbe troncata di netto, che e' proprio lo scatto che si vuole
            # evitare.
            self.rubate.append(voce)
        self.chiamate.append(("tieni", voce))
        self.occupate.add(voce)

    def pluck(self, voce, mono):
        self.chiamate.append(("pluck", voce))
        self.occupate.add(voce)

    def lascia(self, voce, secondi=0.06):
        self.chiamate.append(("lascia", voce))
        self.rilasci.append(secondi)
        self.occupate.discard(voce)

    def mute(self, voce=None):
        self.chiamate.append(("mute", voce))

    def sta_suonando(self, voce):
        return voce in self.occupate


class MidiFinto:
    def __init__(self):
        self.chiamate = []

    def note_on(self, nota, velocity=127):
        self.chiamate.append(("on", nota, velocity))

    def note_off(self, nota):
        self.chiamate.append(("off", nota))


@pytest.fixture
def scena(monkeypatch):
    """Il player con tutto il mondo intorno sostituito da finti."""
    poly = PolyFinto()
    midi = MidiFinto()
    # Le impostazioni non sono caricate da nessuno, qui dentro: il player
    # stampa il nome delle note e quello passa dalla nomenclatura scelta.
    monkeypatch.setattr(config, "impostazioni", config.get_impostazioni_default())
    monkeypatch.setattr(GBAudio, "PolyphonicPlayer", lambda fs=None, num_strings=16: poly)
    monkeypatch.setattr(GBAudio, "get_midi_in", lambda: None)
    monkeypatch.setattr(GBAudio, "get_midi_out", lambda: midi)
    monkeypatch.setattr(suoni, "suono_attivo", lambda: "suono_2")
    monkeypatch.setattr(suoni, "descrizione_suono", lambda chiave: chiave)
    monkeypatch.setattr(suoni, "parametri_suono", lambda chiave: {
        'karplus': False, 'dur': 2.0, 'vol': 0.5, 'hardness': 0.6, 'damping': 0.997,
        'pick_pos': 0.15, 'bright': 0.4, 'kind': 1, 'adsr': [2.0, 1.0, 90.0, 2.0]})
    return poly, midi


def gira(monkeypatch, giri, tiene=True):
    """Fa girare il player su una sequenza di eventi e restituisce la tastiera."""
    finta = TastieraFinta(giri, tiene=tiene)
    monkeypatch.setattr(player, "apri_tastiera", lambda: finta)
    player.PlayerGenerico()
    return finta


def test_premere_accende_e_lasciare_spegne(scena, monkeypatch):
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu")], [("z", "su")]])
    assert [c[0] for c in poly.chiamate] == ["tieni", "lascia"]
    # La nota si spegne sulla voce su cui era stata accesa.
    assert poly.chiamate[0][1] == poly.chiamate[1][1]


def test_la_nota_non_si_riaccende_da_sola(scena, monkeypatch):
    # Difesa in piu' oltre a quella della Tastiera: se una seconda pressione
    # arrivasse lo stesso, non deve nascere una nota parallela che nessuno
    # spegnera' mai.
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu")], [("z", "giu")], [("z", "su")]])
    assert [c[0] for c in poly.chiamate] == ["tieni", "lascia"]


def test_due_tasti_insieme_vanno_su_due_voci(scena, monkeypatch):
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu"), ("x", "giu")], [("z", "su"), ("x", "su")]])
    accese = [c[1] for c in poly.chiamate if c[0] == "tieni"]
    assert len(accese) == 2
    assert accese[0] != accese[1]


def test_lasciare_un_tasto_mai_premuto_non_fa_niente(scena, monkeypatch):
    poly, _midi = scena
    gira(monkeypatch, [[("q", "su")]])
    assert poly.chiamate == []


def test_il_cambio_di_suono_spegne_quello_che_stava_suonando(scena, monkeypatch):
    # Senza questo, le note accese col suono di prima resterebbero senza
    # nessuno che le spenga, perche' il rilascio le cerca fra le accese.
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu")], [(" ", "giu")], [("z", "su")]])
    assert [c[0] for c in poly.chiamate] == ["tieni", "lascia"]


def test_uscire_spegne_tutto_e_chiude_la_tastiera(scena, monkeypatch):
    poly, _midi = scena
    finta = gira(monkeypatch, [[("z", "giu")], [("\x1b", "giu")]])
    assert ("lascia", poly.chiamate[0][1]) in poly.chiamate
    assert finta.chiusa
    assert poly.fermato


def test_senza_rilasci_le_note_restano_quelle_di_prima(scena, monkeypatch):
    # Il ripiego di dove la tastiera a eventi non c'e': una pressione, una nota
    # che decade da sola, e nessuno che la spenga a meta'.
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu")], [("x", "giu")]], tiene=False)
    assert [c[0] for c in poly.chiamate] == ["pluck", "pluck"]
    assert "lascia" not in [c[0] for c in poly.chiamate]


def test_col_suono_midi_la_nota_si_tiene_col_note_off(scena, monkeypatch):
    poly, midi = scena
    monkeypatch.setattr(suoni, "suono_attivo", lambda: "midi")
    gira(monkeypatch, [[("z", "giu")], [("z", "su")]])
    assert [c[0] for c in midi.chiamate] == ["on", "off"]
    assert midi.chiamate[0][1] == midi.chiamate[1][1]
    # Il mixer interno non c'entra: la nota la tiene il sintetizzatore.
    assert poly.chiamate == []


def test_i_tasti_funzione_cambiano_ottava_e_non_suonano(scena, monkeypatch):
    poly, _midi = scena
    gira(monkeypatch, [[("f5", "giu")], [("z", "giu")], [("z", "su")]])
    assert [c[0] for c in poly.chiamate] == ["tieni", "lascia"]


def test_la_stessa_nota_da_due_tasti_diversi_si_spegne_giusta(scena, monkeypatch):
    # z e Z sono due tasti diversi che danno due note diverse: il registro sta
    # sul nome del tasto, quindi ognuna si spegne per conto suo.
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu"), ("Z", "giu")], [("z", "su")], [("Z", "su")]])
    ordine = [c[0] for c in poly.chiamate]
    assert ordine == ["tieni", "tieni", "lascia", "lascia"]
    assert poly.chiamate[2][1] == poly.chiamate[0][1]
    assert poly.chiamate[3][1] == poly.chiamate[1][1]


def test_venti_note_in_fila_non_si_rubano_la_voce(scena, monkeypatch):
    # Le voci girano a rotazione anche quando ce ne sarebbero di libere prima,
    # ed e' voluto: la nota appena lasciata ha ancora sessanta millesimi di
    # rilascio da finire, e riprenderle la voce la troncherebbe di netto.
    poly, _midi = scena
    giri = []
    for _volta in range(20):
        giri.append([("z", "giu")])
        giri.append([("z", "su")])
    gira(monkeypatch, giri)
    assert len([c for c in poly.chiamate if c[0] == "tieni"]) == 20
    assert poly.rubate == []


def test_con_tutte_le_voci_occupate_si_prende_la_piu_vecchia(scena, monkeypatch):
    # Diciassette tasti tenuti giu' insieme non capiteranno mai con dieci dita,
    # ma se capitasse la nota nuova deve suonare lo stesso, prendendo la voce di
    # quella che e' giu' da piu' tempo.
    poly, _midi = scena
    tasti = [*"zxcvbnm,.-sdghjl", "q"]
    gira(monkeypatch, [[(tasto, "giu")] for tasto in tasti])
    accese = [c[1] for c in poly.chiamate if c[0] == "tieni"]
    assert len(accese) == 17
    assert len(poly.rubate) == 1
    assert poly.rubate[0] == accese[0]


def test_apri_tastiera_da_sempre_qualcosa_con_cui_suonare():
    # Che sia quella a eventi o il ripiego, chi chiama deve poter andare avanti
    # senza sapere quale delle due ha in mano.
    tastiera = player.apri_tastiera()
    try:
        assert hasattr(tastiera, "eventi")
        assert isinstance(tastiera.tiene, bool)
    finally:
        tastiera.chiudi()


def test_il_mono_della_nota_e_quello_che_il_mixer_si_aspetta():
    # render_tenuta consegna gia' il mono al volume giusto: se tornasse stereo
    # o a volume dimezzato, il mixer suonerebbe piano o storto.
    r = GBAudio.NoteRenderer(fs=GBAudio.FS)
    r.set_params(220.0, 1.0, 0.5, 0.0, kind=1, adsr_list=[2.0, 1.0, 90.0, 2.0])
    mono, _ciclo = r.render_tenuta()
    assert mono.ndim == 1
    assert mono.dtype == np.float32
    assert 0.4 < float(np.max(np.abs(mono))) <= 0.5


def test_il_rilascio_dura_quanto_dice_l_inviluppo(scena, monkeypatch):
    # Sessanta millesimi fissi facevano morire la nota all'improvviso: la
    # chiusura deve durare quanto il quarto valore dell'ADSR dichiara, cioe' il
    # due per cento della durata di riferimento, che qui e' di due secondi.
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu")], [("z", "su")]])
    assert poly.rilasci == [pytest.approx(0.04)], poly.rilasci


def test_un_inviluppo_senza_rilascio_prende_il_minimo():
    # Chiudere di colpo farebbe uno scatto: venti millesimi bastano a evitarlo.
    senza = {'karplus': False, 'dur': 9.0, 'adsr': [0.2, 99.8, 0.0, 0.0]}
    assert suoni.secondi_di_rilascio(senza) == pytest.approx(0.02)


def test_la_corda_pizzicata_si_smorza_in_sessanta_millesimi():
    corda = {'karplus': True, 'dur': 6.0, 'adsr': [0, 0, 0, 0]}
    assert suoni.secondi_di_rilascio(corda) == pytest.approx(0.06)


def test_un_rilascio_lungo_arriva_intero():
    lungo = {'karplus': False, 'dur': 4.0, 'adsr': [2.0, 1.0, 90.0, 25.0]}
    assert suoni.secondi_di_rilascio(lungo) == pytest.approx(1.0)
