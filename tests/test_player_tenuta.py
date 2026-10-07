# Chitabry, prove del Player Generico a tasti tenuti.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5, modalita' auto).
# Nate con la issue 55, il 14 settembre 2026. Non aprono nessun dispositivo e
# non leggono nessuna tastiera: gli eventi arrivano da una finta, e il mixer e'
# un finto che si limita a segnare le chiamate che riceve.

from typing import ClassVar

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

    def set_pan(self, voce, pan):
        pass

    def sta_suonando(self, voce):
        return voce in self.occupate


@pytest.fixture
def scena(monkeypatch):
    """Il player con tutto il mondo intorno sostituito da finti."""
    poly = PolyFinto()
    # Le impostazioni non sono caricate da nessuno, qui dentro: il player
    # stampa il nome delle note e quello passa dalla nomenclatura scelta.
    monkeypatch.setattr(config, "impostazioni", config.get_impostazioni_default())
    monkeypatch.setattr(GBAudio, "PolyphonicPlayer", lambda fs=None, num_strings=16: poly)
    monkeypatch.setattr(GBAudio, "get_midi_in", lambda: None)
    monkeypatch.setattr(suoni, "suono_attivo", lambda: "suono_2")
    monkeypatch.setattr(suoni, "descrizione_suono", lambda chiave: chiave)
    monkeypatch.setattr(suoni, "parametri_suono", lambda chiave: {
        'karplus': False, 'dur': 2.0, 'vol': 0.5, 'hardness': 0.6, 'damping': 0.997,
        'pick_pos': 0.15, 'bright': 0.4, 'kind': 1, 'adsr': [10.0, 60.0, 70.0, 120.0]})
    return poly, None


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


class TastieraACoppie:
    """La tastiera di GBUtils come la riceveva Gabriele tenendo lo Shift:
    ogni ripetizione arriva come rilascio e subito dopo pressione. Ogni
    chiamata a eventi consegna il giro dopo e fa passare il tempo dato."""

    def __init__(self, giri, orologio):
        self.giri = list(giri)
        self.orologio = orologio
        self.chiusa = False
        self.premuti = frozenset()

    def eventi(self, attesa=None):
        if not self.giri:
            self.orologio[0] += attesa or 0.0
            return []
        passo, eventi = self.giri.pop(0)
        self.orologio[0] += passo
        return eventi

    def chiudi(self):
        self.chiusa = True


def test_le_righe_della_tastiera_coprono_quelle_di_prima(scena, monkeypatch, capsys):
    """Le descrizioni del banco sono lunghe: la riga Ultima nota, piu'
    corta della riga di stato, ne lasciava i pezzi sulla barra braille."""
    monkeypatch.setattr(suoni, "descrizione_suono", lambda chiave: "Banco GeneralUser-GS.sf2, strumento dell'attivo (Harmonica)")
    gira(monkeypatch, [[("z", "giu")], [("z", "su")]])
    pezzi = [p for p in capsys.readouterr().out.split("\r") if p.strip()]
    stato = next(p for p in pezzi if p.startswith("[Suono:"))
    nota = next(p for p in pezzi if p.startswith("Ultima nota:"))
    assert len(nota) >= len(stato) and nota.rstrip() != nota


def test_una_nota_tenuta_oltre_il_suo_suono_non_perde_la_voce(scena, monkeypatch):
    """Una nota tenuta piu' a lungo del suo suono ha finito il buffer, ma la
    voce e' ancora sua: data alla nota dopo, il rilascio della prima
    chiudeva la seconda."""
    poly, _midi = scena
    finta = TastieraFinta([[("z", "giu")]] + [[(tasto, "giu"), (tasto, "su")] for tasto in "xcvbnm,.-sdghjlqw"] + [[("z", "su")]])
    poly_finto_tieni = poly.tieni

    def tieni_e_finisci(voce, mono, ciclo=None):
        poly_finto_tieni(voce, mono, ciclo)
        if not poly.chiamate[:-1]:
            # La prima nota, quella della z, finisce subito il suo buffer
            poly.occupate.discard(voce)

    monkeypatch.setattr(poly, "tieni", tieni_e_finisci)
    monkeypatch.setattr(player, "apri_tastiera", lambda: finta)
    player.PlayerGenerico()
    prima = poly.chiamate[0][1]
    altre = [voce for azione, voce in poly.chiamate[1:] if azione == "tieni"]
    assert prima not in altre


def test_ascolto_delle_corde_tenute_e_modificatori(scena, monkeypatch, capsys):
    """Le corde suonano finche' il tasto e' giu', la pennata pure; Ctrl e
    Shift premuti da soli non dicono Comando non valido."""
    poly, _midi = scena
    monkeypatch.setattr(config, "impostazioni", config.get_impostazioni_default())
    config.aggiorna_manico()
    monkeypatch.setattr(player, "aspetta", lambda _s: None)
    finta = TastieraFinta([[("ctrl", "giu")], [("ctrl", "su"), ("1", "giu")], [("1", "su")], [("shift", "giu"), ("Q", "giu")],
                           [("Q", "su"), ("shift", "su")]])
    monkeypatch.setattr(player, "apri_tastiera", lambda: finta)
    player.Suona(["0", "2", "2", "1", "0", "0"])
    azioni = [azione for azione, _voce in poly.chiamate]
    assert azioni == ["tieni", "lascia"] + ["tieni"] * 6 + ["lascia"] * 6
    assert "Comando non valido" not in capsys.readouterr().out
    assert finta.chiusa and poly.fermato


def test_la_tastiera_esterna_tiene_le_sue_voci(monkeypatch):
    """Fuori dalla Tastiera le note della tastiera MIDI esterna suonano su un
    mixer loro: una nota tenuta oltre il suo suono non cede la voce, una nota
    accesa due volte chiude la prima, e quando un ascolto si prende la
    tastiera le note accese si chiudono."""
    poly = PolyFinto()
    monkeypatch.setattr(GBAudio, "PolyphonicPlayer", lambda fs=None, num_strings=16: poly)
    monkeypatch.setattr(suoni, "_ESTERNA", {})
    monkeypatch.setattr(suoni, "_forse_chiudi_dopo", lambda: None)
    monkeypatch.setattr(suoni, "suono_attivo", lambda: "suono_2")
    monkeypatch.setattr(suoni, "parametri_suono", lambda chiave: {'karplus': False, 'adsr': [0, 0, 100, 120]})
    monkeypatch.setattr(suoni, "tieni_nota", lambda mixer, voce, *_a, **_k: mixer.tieni(voce, None) or True)
    suoni.nota_esterna_giu(36)
    poly.occupate.discard(0)        # il basso tenuto ha finito il suo buffer
    suoni.nota_esterna_giu(72)
    assert poly.chiamate == [("tieni", 0), ("tieni", 1)]
    suoni.nota_esterna_su(36)
    assert poly.chiamate[-1] == ("lascia", 0) and poly.occupate == {1}
    # La stessa nota due volte, come da una tastiera che manda due canali
    suoni.nota_esterna_giu(72)
    assert poly.chiamate[-2:] == [("lascia", 1), ("tieni", 0)]
    suoni.chiudi_note_esterne()
    assert poly.chiamate[-1] == ("lascia", 0) and suoni._ESTERNA["accese"] == {}
    # Quando tace, il mixer si chiude e la prossima nota lo riapre
    suoni._chiudi_se_tace()
    assert poly.fermato and suoni._ESTERNA == {}


def test_le_ripetizioni_a_coppie_non_spezzano_la_nota(monkeypatch):
    """Shift+Z tenuto: le coppie rilascio e pressione, a trentatre millesimi
    l'una dall'altra, non arrivano piu' a chi suona; il rilascio vero si',
    passata la grazia."""
    orologio = [0.0]
    monkeypatch.setattr(player.time, "monotonic", lambda: orologio[0])
    sotto = TastieraACoppie([(0.0, [("Z", "giu")])]
                            + [(0.033, [("Z", "su"), ("Z", "giu")])] * 5
                            + [(0.033, [("Z", "su")])], orologio)
    tenuta = player.TastieraTenuta(sotto, grazia=0.06)
    visti = []
    for _giro in range(12):
        visti.extend(tenuta.eventi(0.05))
    assert visti == [("Z", "giu"), ("Z", "su")]
    tenuta.chiudi()
    assert sotto.chiusa


def test_la_grazia_segue_la_ripetizione_di_windows():
    assert player.grazia_del_rilascio() >= player.GRAZIA_MINIMA


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
    # chiusura deve durare quanto il quarto valore dell'ADSR dichiara, che dal
    # formato 2 e' scritto in millesimi di secondo.
    poly, _midi = scena
    gira(monkeypatch, [[("z", "giu")], [("z", "su")]])
    assert poly.rilasci == [pytest.approx(0.12)], poly.rilasci


def test_un_inviluppo_senza_rilascio_prende_il_minimo():
    # Chiudere di colpo farebbe uno scatto: venti millesimi bastano a evitarlo.
    senza = {'karplus': False, 'dur': 9.0, 'adsr': [1.0, 900.0, 0.0, 0.0]}
    assert suoni.secondi_di_rilascio(senza) == pytest.approx(0.02)


def test_la_corda_pizzicata_si_smorza_in_sessanta_millesimi():
    corda = {'karplus': True, 'dur': 6.0, 'adsr': [0, 0, 0, 0]}
    assert suoni.secondi_di_rilascio(corda) == pytest.approx(0.06)


def test_un_rilascio_lungo_arriva_intero():
    lungo = {'karplus': False, 'dur': 4.0, 'adsr': [10.0, 60.0, 70.0, 1000.0]}
    assert suoni.secondi_di_rilascio(lungo) == pytest.approx(1.0)


def test_il_rilascio_non_dipende_piu_dalla_durata():
    # Era il difetto: gli stessi valori davano tempi diversi a seconda di
    # quanto durava la nota di riferimento.
    corta = {'karplus': False, 'dur': 1.0, 'adsr': [10.0, 60.0, 70.0, 120.0]}
    lunga = {'karplus': False, 'dur': 20.0, 'adsr': [10.0, 60.0, 70.0, 120.0]}
    assert suoni.secondi_di_rilascio(corta) == suoni.secondi_di_rilascio(lunga)


class FlussoDiCarta:
    """Al posto di sd.OutputStream: segna con che argomenti e' stato aperto."""

    aperture: ClassVar[list] = []

    def __init__(self, **argomenti):
        FlussoDiCarta.aperture.append(argomenti)
        if argomenti.get("device") == "non apre":
            raise RuntimeError("questa interfaccia non regge il formato")

    def start(self):
        pass


@pytest.fixture
def flusso(monkeypatch):
    FlussoDiCarta.aperture = []
    monkeypatch.setattr(GBAudio.sd, "OutputStream", FlussoDiCarta)
    return FlussoDiCarta


def test_il_flusso_si_apre_sul_dispositivo_scelto_da_gbutils(flusso, monkeypatch):
    import GBUtils
    monkeypatch.setattr(GBUtils, "scegli_dispositivo_audio", lambda **_: (7, "Windows WASAPI"))
    GBAudio.apri_flusso_uscita(44100, 2, "float32", callback=None)
    assert len(flusso.aperture) == 1
    assert flusso.aperture[0]["device"] == 7


def test_se_quella_interfaccia_non_apre_si_ripiega(flusso, monkeypatch):
    # Un ritardo si sopporta, restare muti no.
    import GBUtils
    monkeypatch.setattr(GBUtils, "scegli_dispositivo_audio", lambda **_: ("non apre", "Fantasia"))
    GBAudio.apri_flusso_uscita(44100, 2, "float32", callback=None)
    assert len(flusso.aperture) == 2
    assert "device" not in flusso.aperture[1]


def test_se_la_scelta_fallisce_si_lascia_fare_al_sistema(flusso, monkeypatch):
    import GBUtils

    def rotta(**_chiavi):
        raise OSError("nessun dispositivo")

    monkeypatch.setattr(GBUtils, "scegli_dispositivo_audio", rotta)
    GBAudio.apri_flusso_uscita(44100, 2, "float32", callback=None)
    assert len(flusso.aperture) == 1
    assert "device" not in flusso.aperture[0]


def test_senza_niente_da_scegliere_si_apre_come_prima(flusso, monkeypatch):
    import GBUtils
    monkeypatch.setattr(GBUtils, "scegli_dispositivo_audio", lambda **_: (None, None))
    GBAudio.apri_flusso_uscita(44100, 2, "float32", callback=None)
    assert "device" not in flusso.aperture[0]


def test_chitabry_dichiara_di_aprire_col_callback(flusso, monkeypatch):
    # Se lo chiedesse a scrittura, GBUtils scarterebbe le interfacce che solo
    # il callback sa aprire, e ne sceglierebbe una piu' lenta.
    import GBUtils
    chiesto = {}

    def finta(modo="scrittura", **_chiavi):
        chiesto["modo"] = modo
        return None, None

    monkeypatch.setattr(GBUtils, "scegli_dispositivo_audio", finta)
    GBAudio.apri_flusso_uscita(44100, 2, "float32", callback=lambda *_: None)
    assert chiesto["modo"] == "callback"
