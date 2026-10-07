# Chitabry, prove della nomenclatura e dei motori di diteggiatura.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).

import pytest

import config
import nomenclatura
from generatore_accordi import AccordoSolver, HarmonicParser
from strumento import InstrumentModel


@pytest.fixture
def latino(monkeypatch):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})


@pytest.fixture
def anglo(monkeypatch):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "anglosassone"})


def test_get_nota_latino(latino):
    assert nomenclatura.get_nota("C#4") == "DO#4"
    assert nomenclatura.get_nota("Eb") == "MIb"
    assert nomenclatura.get_nota("G~5") == "SOL~5"
    assert nomenclatura.get_nota("A``3") == "LA``3"
    assert nomenclatura.get_nota(60) == "60"


def test_get_nota_anglo(anglo):
    assert nomenclatura.get_nota("C#4") == "C#4"
    assert nomenclatura.get_nota("Bb2") == "Bb2"


def test_mappa_toniche(latino, anglo):
    config.impostazioni["nomenclatura"] = "latino"
    toniche = nomenclatura.mappa_toniche()
    assert list(toniche) == config.NOTE_LATINE
    assert toniche["SOL#"] == "G#"
    config.impostazioni["nomenclatura"] = "anglosassone"
    assert nomenclatura.mappa_toniche() == {n: n for n in config.NOTE_STD}


def test_nome_utente_in_std(latino):
    assert nomenclatura.nome_utente_in_std("do#") == "C#"
    assert nomenclatura.nome_utente_in_std("SIb") == "A#"
    assert nomenclatura.nome_utente_in_std("C") is None
    assert nomenclatura.nome_utente_in_std("C", qualsiasi=True) == "C"
    assert nomenclatura.nome_utente_in_std("EB", qualsiasi=True) == "D#"
    assert nomenclatura.nome_utente_in_std("H") is None


def test_diteggiatura_numera_le_corde_dello_strumento():
    """Su un ukulele le corde sono quattro: fino alla 7.8.3 il codice contava da sei."""
    model = InstrumentModel(["G4", "C4", "E4", "A4"], 12)
    target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root("C")
    solver = AccordoSolver(model, target_pc, root_pc)
    soluzioni = solver.solve(max_stretch=4)
    assert soluzioni
    migliore = max(soluzioni, key=solver.score_solution)
    meta = solver.analizza_difficolta_e_diteggiatura(migliore, solver.score_solution(migliore))
    testo = " ".join(meta["diteggiatura"])
    assert "Corda 5" not in testo and "Corda 6" not in testo
    assert "Corde 4" in testo or "Corda 4" in testo or "Corda 1" in testo or "Corde 1" in testo


def test_accordo_di_do_sulla_chitarra():
    model = InstrumentModel(config.ACCORDATURA_CHITARRA, 12)
    target_pc, root_pc = HarmonicParser.get_pitch_classes_and_root("C")
    solver = AccordoSolver(model, target_pc, root_pc)
    soluzioni = solver.solve(max_stretch=4)
    tab = [max(soluzioni, key=solver.score_solution)[f"C{i}"] for i in range(6)]
    # La forma aperta classica: x 3 2 0 1 0
    assert tab == [-1, 3, 2, 0, 1, 0]



def test_get_nota_traduce_ogni_alterazione(latino):
    assert nomenclatura.get_nota("E#4") == "MI#4"
    assert nomenclatura.get_nota("B#") == "SI#"
    assert nomenclatura.get_nota("Cb5") == "DOb5"
    assert nomenclatura.get_nota("Fb") == "FAb"
    assert nomenclatura.get_nota("C##5") == "DO##5"
    assert nomenclatura.get_nota("Bbb") == "SIbb"
    assert nomenclatura.get_nota("E-") == "MIb"
    assert nomenclatura.get_nota("G~5") == "SOL~5"


def test_get_nota_anglo_resta_com_e(anglo):
    assert nomenclatura.get_nota("E#4") == "E#4"
    assert nomenclatura.get_nota("Bbb") == "Bbb"


def test_il_manico_ritrova_ogni_alterazione():
    import manico
    assert [manico.nome_sul_manico(n) for n in ("E#", "B#", "Cb", "Fb", "C##", "Bbb", "Bb", "B-", "C#", "G")] == \
        ["F", "C", "B", "E", "D", "A", "A#", "A#", "C#", "G"]


def test_le_sigle_minori_non_scelgono_i_maggiori(monkeypatch):
    """Il menu non distingue le maiuscole: m9 sceglieva M9, il maggiore nona."""
    import costruttore_accordi
    import scale_catalog
    monkeypatch.setattr(scale_catalog, "USER_CHORD_DICT", scale_catalog.get_user_chord_dictionary())
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    viste = []
    risposte = iter(["DO", "m9", "DO", "maj9"])

    def menu_finto(**opzioni):
        viste.append(opzioni["d"])
        return next(risposte)

    monkeypatch.setattr(costruttore_accordi, "menu", menu_finto)
    assert costruttore_accordi._scegli_accordo() == ("C", "m9")
    assert costruttore_accordi._scegli_accordo() == ("C", "M9")
    chiavi = [k.lower() for k in viste[1]]
    assert len(chiavi) == len(set(chiavi))
