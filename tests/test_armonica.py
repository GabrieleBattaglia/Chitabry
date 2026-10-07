# Chitabry, prove dell'armonica: ance, bending, overbend, notazione, posizioni, accordi e archivio.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nate con la 9.0.0, issue 58. Le tabelle di confronto sono quelle dei
# metodi e dei costruttori: l'armonica in DO comincia dal DO centrale.

import json

import numpy as np
import pytest

import armonica
import armonica_vista
import config
import esercizio_scale

NOMI = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']


def nome(midi):
    return f"{NOMI[midi % 12]}{midi // 12 - 1}"


def simboli(modello):
    """Il simbolo di ogni tecnica con la nota che suona."""
    return {t.simbolo: nome(t.midi) for t in modello.tecniche}


@pytest.fixture
def richter():
    return armonica.HarmonicaModel("C", "richter")


def test_le_ance_della_richter_in_do(richter):
    assert [nome(m) for m in richter.soffiati] == ["C4", "E4", "G4", "C5", "E5", "G5", "C6", "E6", "G6", "C7"]
    assert [nome(m) for m in richter.aspirati] == ["D4", "G4", "B4", "D5", "F5", "A5", "B5", "D6", "F6", "A6"]


def test_bending_e_overbend_della_richter(richter):
    tab = simboli(richter)
    attesi = {"-1/": "C#4", "-2/": "F#4", "-2//": "F4", "-3/": "A#4", "-3//": "A4", "-3///": "G#4",
              "-4/": "C#5", "-6/": "G#5", "+8/": "D#6", "+9/": "F#6", "+10/": "B6", "+10//": "A#6",
              "+1*": "D#4", "+4*": "D#5", "+5*": "F#5", "+6*": "A#5", "-7*": "C#6", "-9*": "G#6", "-10*": "C#7"}
    for simbolo, nota in attesi.items():
        assert tab[simbolo] == nota, simbolo
    # Il foro 5 ha le ance a un semitono, il 7 anche: nessun bending
    assert "-5/" not in tab
    assert "+7/" not in tab
    assert "-7/" not in tab


def test_la_richter_e_cromatica_da_do4_a_do_diesis_7(richter):
    grave, acuta = richter.estensione()
    assert (nome(grave), nome(acuta)) == ("C4", "C#7")
    assert all(richter.migliore(m) is not None for m in range(grave, acuta + 1))


def test_la_tecnica_piu_comoda_viene_prima(richter):
    sol4 = richter.tecniche_per_nota(67)
    assert [t.simbolo for t in sol4] == ["-2", "+3"]
    assert [t.simbolo for t in richter.tecniche_per_nota(77)] == ["-5"]
    assert [t.simbolo for t in richter.tecniche_per_nota(89)] == ["-9", "-8*"]
    assert richter.migliore(30) is None


def test_le_altre_accordature_diatoniche():
    assert simboli(armonica.HarmonicaModel("C", "country"))["-5"] == "F#5"
    assert simboli(armonica.HarmonicaModel("C", "country"))["-5/"] == "F5"
    assert simboli(armonica.HarmonicaModel("C", "paddy_richter"))["+3"] == "A4"
    minore = armonica.HarmonicaModel("C", "natural_minor")
    assert [nome(m)[:-1] for m in minore.soffiati] == ["C", "D#", "G"] * 3 + ["C"]
    assert [nome(m)[:-1] for m in minore.aspirati] == ["D", "G", "A#", "D", "F", "A", "A#", "D", "F", "A"]
    armonica_minore = armonica.HarmonicaModel("C", "harmonic_minor")
    assert [nome(m)[:-1] for m in armonica_minore.aspirati] == ["D", "G", "B", "D", "F", "G#", "B", "D", "F", "G#"]
    melody = armonica.HarmonicaModel("C", "melody_maker")
    assert nome(melody.soffiati[2]) == "A4"
    assert [nome(melody.aspirati[i]) for i in (4, 8)] == ["F#5", "F#6"]


def test_le_ottave_seguono_i_costruttori():
    # Da DO a FA# sopra il DO centrale, da SOL a SI sotto
    assert nome(armonica.midi_foro_1("C")) == "C4"
    assert nome(armonica.midi_foro_1("F#")) == "F#4"
    assert nome(armonica.midi_foro_1("G")) == "G3"
    assert nome(armonica.midi_foro_1("Bb")) == "A#3"
    assert nome(armonica.HarmonicaModel("A").soffiati[0]) == "A3"


def test_la_cromatica_solo_ha_il_cursore_e_niente_bending():
    cromatica = armonica.HarmonicaModel("C", "solo", 12)
    assert [nome(m) for m in cromatica.soffiati[:5]] == ["C4", "E4", "G4", "C5", "C5"]
    assert [nome(m) for m in cromatica.aspirati[:4]] == ["D4", "F4", "A4", "B4"]
    tab = simboli(cromatica)
    assert tab["+1<"] == "C#4"
    assert tab["-4<"] == "C5"
    assert not any("/" in s or "*" in s for s in tab)
    assert [nome(m) for m in cromatica.estensione()] == ["C4", "D7"]
    sedici = armonica.HarmonicaModel("C", "solo", 16)
    assert nome(sedici.soffiati[0]) == "C3"
    assert len(sedici.soffiati) == 16


def test_la_bebop_scambia_le_ance_dei_fori_4_8_e_12():
    bebop = armonica.HarmonicaModel("C", "bebop", 12)
    assert [nome(bebop.soffiati[i]) for i in (3, 7, 11)] == ["B4", "B5", "B6"]
    assert [nome(bebop.aspirati[i]) for i in (3, 7, 11)] == ["C5", "C6", "C7"]
    assert all(s < a for s, a in zip(bebop.soffiati, bebop.aspirati, strict=True))


def test_fori_e_accordature_che_non_tornano():
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("C", "richter", 12)
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("C", "solo", 14)
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("C", "bebop", 10)
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("C", "richter", 12, famiglia="cromatica")
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("C", "country", famiglia="cromatica")
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("C", registro="altissimo")
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("C", "sconosciuta")
    with pytest.raises(ValueError):
        armonica.HarmonicaModel("H")


def test_i_nomi_delle_tonalita():
    assert armonica.normalizza_tonalita("bb") == "Bb"
    assert armonica.normalizza_tonalita("A#") == "Bb"
    assert armonica.normalizza_tonalita("gb") == "F#"
    assert armonica.normalizza_tonalita(" c ") == "C"


def test_simboli_e_descrizioni(richter):
    assert richter.da_simbolo("-3//").descrizione() == "Foro 3 aspirato, bending di un tono"
    assert richter.da_simbolo("-4/").descrizione() == "Foro 4 aspirato, bending di mezzo tono"
    assert richter.da_simbolo("-3///").descrizione() == "Foro 3 aspirato, bending di un tono e mezzo"
    assert richter.da_simbolo("+10//").descrizione() == "Foro 10 soffiato, bending di un tono"
    assert richter.da_simbolo("+4*").descrizione() == "Foro 4 overblow"
    assert richter.da_simbolo("-7*").descrizione() == "Foro 7 overdraw"
    assert richter.da_simbolo(" +1 ").descrizione() == "Foro 1 soffiato"
    cromatica = armonica.HarmonicaModel("C", "solo")
    for cursore in ("<", "^", "~"):
        tecnica = cromatica.da_simbolo("+4" + cursore)
        assert tecnica.simbolo == "+4<"
        assert tecnica.descrizione() == "Foro 4 soffiato con il cursore premuto"


def test_i_simboli_sbagliati_si_spiegano(richter):
    casi = {
        "-5/": "un semitono solo",
        "+7/": "un semitono solo",
        "+3/": "si piega aspirando",
        "-9/": "si piega soffiando",
        "-4//": "al massimo di un semitono, -4/",
        "-2///": "al massimo di 2 semitoni",
        # Le ance a un semitono non si piegano in nessun verso: prima si
        # suggeriva l'altro verso, con un simbolo che non esiste
        "+5/": "un semitono solo",
        "-7/": "un semitono solo",
        "-2*": "+2*",
        "+8*": "-8*",
        "+11": "da 1 a 10",
        "-4<": "solo sulle cromatiche",
        "x": "non e' un simbolo",
        "-3////": "non e' un simbolo",
    }
    for simbolo, spiegazione in casi.items():
        with pytest.raises(ValueError, match=spiegazione.replace("+", r"\+").replace("*", r"\*")):
            richter.da_simbolo(simbolo)
    with pytest.raises(ValueError, match="valvole"):
        armonica.HarmonicaModel("C", "solo").da_simbolo("-3/")


def test_le_posizioni():
    do = 0
    attese = {"C": 1, "G": 2, "D": 3, "A": 4, "E": 5, "B": 6, "F#": 7, "F": 12}
    for tonica, numero in attese.items():
        assert armonica.posizione("C", NOMI.index(tonica)) == numero, tonica
    assert armonica.posizione("G", NOMI.index("D")) == 2
    assert armonica.posizione("A", do) == 10   # DO sull'armonica in LA: tre quinte sotto
    assert armonica.descrivi_posizione(1) == "prima posizione (straight harp), la tonica e' quella dell'armonica"
    assert armonica.descrivi_posizione(2) == "seconda posizione (cross harp), la tonica sta una quinta sopra quella dell'armonica"
    assert armonica.descrivi_posizione(12) == "dodicesima posizione, la tonica sta una quinta sotto quella dell'armonica"


def test_gli_accordi_sui_fori_vicini(richter):
    sol7 = richter.accordi({7, 11, 2, 5})
    assert [f.simboli for f in sol7] == ["-2 -3 -4 -5"]
    assert sol7[0].completo
    do = richter.accordi({0, 4, 7})
    assert len(do) == 8
    assert do[0].simboli == "+1 +2 +3"
    re_minore = richter.accordi({2, 5, 9})
    assert [f.simboli for f in re_minore] == ["-4 -5 -6", "-8 -9 -10"]
    # Il LA minore non sta in tre fori: restano i pezzi, con la nota che manca
    la_minore = richter.accordi({9, 0, 4})
    assert [f.simboli for f in la_minore] == ["+1 +2", "+4 +5", "+7 +8"]
    assert all(f.mancanti == {9} and not f.completo for f in la_minore)


def test_gli_accordi_sulla_cromatica_usano_anche_il_cursore():
    cromatica = armonica.HarmonicaModel("C", "solo")
    do_diesis = cromatica.accordi({1, 5, 8})
    assert do_diesis[0].simboli == "+1< +2< +3<"
    assert all(f.cursore for f in do_diesis)


def test_conteggi_e_fatica(richter):
    tecniche = [richter.da_simbolo(s) for s in ("-2", "-3/", "+4", "-4/", "-4", "-5", "+6")] + [None]
    assert armonica.conta_tecniche(tecniche) == {"naturale": 5, "bending di mezzo tono": 2, "fuori dall'armonica": 1}
    assert armonica.fatica(tecniche) == 12


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    percorso = str(tmp_path / "chitabry-settings.json")
    monkeypatch.setattr(config, "FILE_IMPOSTAZIONI", percorso)
    monkeypatch.setattr(config, "impostazioni", {})
    monkeypatch.setattr(config, "archivio_modificato", False)
    monkeypatch.setattr(config, "ARMONICA", None)
    return percorso


def test_il_formato_3_dice_il_tipo_degli_strumenti(archivio):
    with open(archivio, "w", encoding="utf-8") as f:
        json.dump({"versione_formato": 2, "strumenti": {"Basso": {"accordatura": ["E1", "A1", "D2", "G2"], "tasti": 20}},
                   "strumento_attivo": "Basso"}, f)
    config.carica_impostazioni()
    assert config.impostazioni["strumenti"]["Basso"]["tipo"] == config.TIPO_CORDE
    assert config.impostazioni["versione_formato"] == 3
    assert config.get_impostazioni_default()["strumenti"][config.STRUMENTO_PREDEFINITO]["tipo"] == config.TIPO_CORDE


def test_l_armonica_attiva_svuota_il_manico(archivio):
    config.impostazioni = config.get_impostazioni_default()
    config.impostazioni["strumenti"]["Special 20"] = {"tipo": "armonica", "famiglia": "diatonica", "tonalita": "G",
                                                       "accordatura": "richter", "fori": 10}
    config.impostazioni["strumento_attivo"] = "Special 20"
    config.aggiorna_manico()
    assert config.ARMONICA is not None
    assert config.ARMONICA.tonalita == "G"
    assert (config.NUM_CORDE, config.NUM_TASTI, config.CORDE) == (0, 0, {})
    config.impostazioni["strumento_attivo"] = config.STRUMENTO_PREDEFINITO
    config.aggiorna_manico()
    assert config.ARMONICA is None
    assert config.NUM_CORDE == 6


def test_un_armonica_ritoccata_male_si_suona_lo_stesso(archivio, capsys):
    config.impostazioni = config.get_impostazioni_default()
    voce = {"tipo": "armonica", "famiglia": "diatonica", "tonalita": "Z", "accordatura": "richter", "fori": 10}
    config.impostazioni["strumenti"]["Rotta"] = voce
    config.impostazioni["strumento_attivo"] = "Rotta"
    config.aggiorna_manico()
    assert config.ARMONICA.tonalita == "C"
    assert "non tornano" in capsys.readouterr().out
    assert config.impostazioni["strumenti"]["Rotta"]["tonalita"] == "Z"


def test_lo_schema_dei_fori(monkeypatch, richter):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    righe = armonica_vista.righe_schema(richter)
    assert len({len(r) for r in righe}) == 1   # colonne allineate
    assert righe[0].startswith("Foro|1    |2    |")
    assert righe[1].startswith("+   |DO4  |MI4  |SOL4 |DO5  |")
    etichette = [r.split("|")[0].strip() for r in righe[1:]]
    assert etichette == ["+", "-", "-/", "-//", "-///", "+/", "+//", "+*", "-*"]
    cromatica = armonica_vista.righe_schema(armonica.HarmonicaModel("C", "solo"))
    assert [r.split("|")[0].strip() for r in cromatica[1:]] == ["+", "+<", "-", "-<"]


def test_la_scala_di_do_sull_ottava_centrale(monkeypatch, richter):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    s = esercizio_scale._costruisci_scala("C", "concrete:MajorScale", 5, richter)
    assert s.testo_note('a') == "+4 -4 +5 -5 +6 -6 -7 +7"
    assert s.testo_note('d') == "+7 -7 -6 +6 -5 +5 -4 +4"
    assert s.estremi() == ("DO5", "DO6")
    bassa = esercizio_scale._costruisci_scala("C", "concrete:MajorScale", 4, richter)
    assert bassa.testo_note('a') == "+1 -1 +2 -2// -2 -3// -3 +4"


def test_l_ottava_piu_comoda_e_quella_proposta(monkeypatch, richter):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    proposte = []

    def dgt_finto(prompt="", **opzioni):
        proposte.append(opzioni["default"])
        return opzioni["default"]

    monkeypatch.setattr(esercizio_scale, "dgt", dgt_finto)
    scelta = esercizio_scale._scegli_ottava("C", "concrete:MajorScale", richter)
    assert proposte == [2]
    assert scelta.estremi() == ("DO5", "DO6")


def test_le_note_vicine_al_temperamento_contano(monkeypatch):
    from music21 import pitch
    quasi = pitch.Pitch("A4")
    quasi.microtone = 4      # la terza naturale e simili: pochi centesimi
    assert esercizio_scale.midi_temperato(quasi) == 69
    settima = pitch.Pitch("B-4")
    settima.microtone = -31   # la settima naturale 7/4 sopra il DO, 969 centesimi
    assert esercizio_scale.midi_temperato(settima) == 70
    lontana = pitch.Pitch("C#4")
    lontana.microtone = 33    # come il DO#~ della Bohlen-Pierce
    assert esercizio_scale.midi_temperato(lontana) is None
    quarto = pitch.Pitch("A4")
    quarto.microtone = 50
    assert esercizio_scale.midi_temperato(quarto) is None
    assert esercizio_scale.midi_temperato("non un'altezza") is None


def test_la_solo_a_dieci_fori_come_la_trochilus():
    """Issue di Gabriele del 7 ottobre 2026: la JDR Trochilus Solo, dieci
    fori e niente valvole, che si piega anche con il cursore premuto."""
    trochilus = armonica.HarmonicaModel("C", "solo", 10, valvole=False)
    assert [nome(m) for m in trochilus.soffiati] == ["C4", "E4", "G4", "C5", "C5", "E5", "G5", "C6", "C6", "E6"]
    assert [nome(m) for m in trochilus.aspirati] == ["D4", "F4", "A4", "B4", "D5", "F5", "A5", "B5", "D6", "F6"]
    tab = simboli(trochilus)
    assert tab["-1/"] == "C#4"
    assert tab["-1/<"] == "D4"
    assert tab["+1*"] == "D#4"
    assert tab["-4*"] == "C#5"
    assert tab["+10*<"] == "G6"
    assert trochilus.da_simbolo("-3/<").descrizione() == "Foro 3 aspirato con il cursore premuto, bending di mezzo tono"
    assert trochilus.da_simbolo("+1*<").descrizione() == "Foro 1 overblow con il cursore premuto"
    assert "senza valvole" in trochilus.descrizione()
    # La stessa nota viene prima senza tecniche, anche se serve il cursore
    assert [t.simbolo for t in trochilus.tecniche_per_nota(61)][:2] == ["+1<", "-1/"]


def test_con_le_valvole_la_cromatica_non_si_piega():
    valvolata = armonica.HarmonicaModel("C", "solo", 10)
    assert valvolata.valvole
    assert not any(t.bend or t.overbend for t in valvolata.tecniche)
    with pytest.raises(ValueError, match="valvole"):
        valvolata.da_simbolo("-1/")
    assert "con le valvole" in valvolata.descrizione()
    # La bebop di solito non ne ha, la diatonica mai
    assert not armonica.HarmonicaModel("C", "bebop").valvole
    assert not armonica.HarmonicaModel("C", "richter", valvole=True).valvole


def test_la_richter_a_cursore_come_la_trochilus_blues():
    blues = armonica.HarmonicaModel("C", "richter", famiglia="cromatica")
    assert blues.fori == 10 and not blues.valvole
    tab = simboli(blues)
    assert tab["-3//"] == "A4"
    assert tab["-3//<"] == "A#4"
    assert tab["+1<"] == "C#4"
    pop = armonica.HarmonicaModel("C", "paddy_richter", famiglia="cromatica")
    assert simboli(pop)["+3<"] == "A#4"
    assert armonica.accordature_per_famiglia("cromatica") == ["richter", "paddy_richter", "solo", "bebop"]


def test_il_registro_basso_scende_di_un_ottava():
    assert nome(armonica.HarmonicaModel("F", registro="basso").soffiati[0]) == "F3"
    assert nome(armonica.HarmonicaModel("D", registro="basso").soffiati[0]) == "D3"
    assert "registro basso" in armonica.HarmonicaModel("F", registro="basso").descrizione()


def test_l_archivio_porta_valvole_e_registro(archivio):
    voce = {"tipo": "armonica", "famiglia": "cromatica", "tonalita": "C", "accordatura": "solo", "fori": 10,
            "valvole": False, "registro": "basso"}
    modello = config.modello_armonica(voce)
    assert (modello.fori, modello.valvole, modello.registro) == (10, False, "basso")
    assert nome(modello.soffiati[0]) == "C3"
    # Una voce della 9.0.0, senza valvole e registro, resta com'era
    vecchia = config.modello_armonica({"tipo": "armonica", "famiglia": "cromatica", "tonalita": "C", "accordatura": "solo", "fori": 12})
    assert vecchia.valvole and vecchia.registro == "normale"


def test_lo_schema_della_cromatica_senza_valvole(monkeypatch):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    righe = armonica_vista.righe_schema(armonica.HarmonicaModel("C", "solo", 10, valvole=False))
    etichette = [r.split("|")[0].strip() for r in righe[1:]]
    assert etichette[:2] == ["+", "-"]
    assert "-/<" in etichette and "+*<" in etichette
    assert etichette.index("+<") > etichette.index("-*")
    assert len({len(r) for r in righe}) == 1


def test_aggiungere_la_trochilus_dal_gestore(monkeypatch):
    import gestore_impostazioni
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    risposte = iter(["2", "DO", "3", "10", "2", "1"])
    monkeypatch.setattr(gestore_impostazioni, "menu", lambda **_k: next(risposte))
    monkeypatch.setattr(gestore_impostazioni, "dgt", lambda _p="", **k: k["default"])
    nome_strumento, voce = gestore_impostazioni._nuova_armonica({})
    assert nome_strumento == "Armonica cromatica DO Solo 10 fori senza valvole"
    assert voce == {"tipo": "armonica", "famiglia": "cromatica", "tonalita": "C", "accordatura": "solo", "fori": 10,
                    "valvole": False, "registro": "normale"}


def test_l_armonica_che_serve_per_una_tonica():
    sol = NOMI.index("G")
    assert armonica.tonalita_per(sol, 1) == "G"
    assert armonica.tonalita_per(sol, 2) == "C"
    assert armonica.tonalita_per(sol, 3) == "F"
    assert armonica.tonalita_per(sol, 12) == "D"


def test_la_tabella_delle_posizioni(richter):
    """La scala maggiore nelle dodici posizioni dell'armonica in DO: in prima
    non chiede tecniche, e la fatica cresce allontanandosi sul circolo."""
    maggiore = (0, 2, 4, 5, 7, 9, 11)
    righe = armonica.tabella_posizioni(richter, maggiore)
    assert [r[0] for r in righe] == list(range(1, 13))
    assert [NOMI[r[1]] for r in righe[:3]] == ["C", "G", "D"]
    prima = righe[0]
    assert nome(prima[3][0]) == "C5"
    assert [t.simbolo for t in prima[3][1]] == ["+4", "-4", "+5", "-5", "+6", "-6", "-7", "+7"]
    assert armonica.piu_comode(righe)[0] == 1
    # La pentatonica minore di LA ha le note del DO: quarta posizione, tutta naturale
    penta = armonica.tabella_posizioni(richter, (0, 3, 5, 7, 10))
    assert armonica.piu_comode(penta)[0] == 4
    assert armonica.fatica(penta[3][3][1]) == 0


def test_l_ottava_comoda_del_sol_blues(richter):
    tonica, tecniche = armonica.ottava_comoda(richter, NOMI.index("G"), (0, 3, 5, 6, 7, 10))
    assert nome(tonica) == "G4"
    assert [t.simbolo for t in tecniche] == ["-2", "-3/", "+4", "-4/", "-4", "-5", "+6"]
    # Sulla cromatica con le valvole il cursore non pesa: il SOL maggiore ha
    # un'ottava senza fatica, con il FA# preso dal cursore
    cromatica = armonica.HarmonicaModel("C", "solo", 10)
    tonica, tecniche = armonica.ottava_comoda(cromatica, NOMI.index("G"), (0, 2, 4, 5, 7, 9, 11))
    assert armonica.fatica(tecniche) == armonica.FATICA_CURSORE
    assert [t.cursore for t in tecniche].count(True) == 1


def test_la_tabella_a_schermo(monkeypatch, capsys, richter):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    s = esercizio_scale._costruisci_scala("G", "comune:blues", 4, richter)
    esercizio_scale._tabella_posizioni(s, richter, 2)
    righe = capsys.readouterr().out.splitlines()
    assert righe[0].startswith("Le dodici posizioni della scala blues")
    assert righe[2] == ("Seconda posizione (cross harp): quella scelta, SOL blues su questa armonica. "
                        "Ottava piu' comoda dalla tonica SOL4, naturale 5, bending di mezzo tono 2.")
    assert righe[3].startswith("Terza posizione (slant harp): RE blues su questa armonica, oppure SOL blues sull'armonica in FA.")
    assert righe[-1].startswith("Le piu' comode")
    assert len(righe) == 14


def test_tipi_sbagliati_nell_archivio_diventano_valueerror(archivio, capsys):
    """Un'armonica ritoccata a mano con i tipi sbagliati: prima era un crash
    all'avvio, adesso e' il ripiego sulla diatonica in DO."""
    for voce in ({"tipo": "armonica", "accordatura": ["E2", "A2"], "tasti": 21},
                 {"tipo": "armonica", "famiglia": "cromatica", "accordatura": "solo", "fori": 12.0},
                 {"tipo": "armonica", "accordatura": "richter", "fori": 10.0}):
        with pytest.raises(ValueError):
            config.modello_armonica(voce)
        config.impostazioni = config.get_impostazioni_default()
        config.impostazioni["strumenti"]["Rotta"] = voce
        config.impostazioni["strumento_attivo"] = "Rotta"
        config.aggiorna_manico()
        assert config.ARMONICA.descrizione() == "diatonica, accordatura Richter, 10 fori"
    assert "non tornano" in capsys.readouterr().out


def test_sulla_cromatica_la_classifica_conta_il_cursore():
    """Senza peso per il cursore ogni posizione di una cromatica valeva zero."""
    solo = armonica.HarmonicaModel("C", "solo", 12)
    righe = armonica.tabella_posizioni(solo, (0, 2, 4, 5, 7, 9, 11))
    assert armonica.piu_comode(righe)[0] == 1
    assert armonica.fatica(righe[0][3][1]) == 0
    assert armonica.fatica(righe[1][3][1]) == armonica.FATICA_CURSORE


def test_lo_schema_della_harmonic_minor_ha_il_foro_10_piegato_di_un_tono_e_mezzo(monkeypatch):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    minore = armonica.HarmonicaModel("C", "harmonic_minor")
    assert simboli(minore)["+10///"] == "A6"
    etichette = [r.split("|")[0].strip() for r in armonica_vista.righe_schema(minore)[1:]]
    assert "+///" in etichette


class MixerFinto:
    """Il mixer polifonico senza flusso audio: ricorda le voci suonate."""

    def __init__(self, num_strings, **_k):
        self.voci = num_strings
        self.suonate = []
        self.lasciate = []
        self.aperto = False

    def start(self):
        self.aperto = True

    def stop(self):
        self.aperto = False

    def pluck(self, voce, mono):
        self.suonate.append((voce, mono))

    def lascia(self, voce, secondi=0.06):
        self.lasciate.append(voce)


def ascolto_finto(monkeypatch, tasti, suono="suono_1", bpm=90):
    """Prepara l'ascolto dei gruppi di fori con i tasti dati, senza audio:
    restituisce la lista dei mixer aperti e quella delle note rese, con la
    loro durata."""
    mixer = []
    rese = []
    monkeypatch.setattr(armonica_vista.GBAudio, "PolyphonicPlayer", lambda **k: mixer.append(MixerFinto(**k)) or mixer[-1])
    monkeypatch.setattr(armonica_vista.suoni, "mono_delle_note",
                        lambda note, _parametri, dur=None: rese.append((tuple(note), dur)) or np.ones(4, dtype=np.float32))
    monkeypatch.setattr(armonica_vista.suoni, "suono_attivo", lambda: suono)
    monkeypatch.setattr(armonica_vista.suoni, "parametri_armonica", lambda chiave: {"chiave": chiave})
    monkeypatch.setattr(armonica_vista, "tempo_del_metronomo", lambda: bpm)
    sequenza = iter(tasti)
    monkeypatch.setattr(armonica_vista, "key", lambda *_a, **_k: next(sequenza))
    return mixer, rese


def test_un_solo_gruppo_di_fori_si_ascolta_nota_per_nota(monkeypatch, capsys, richter):
    """Con un gruppo solo menu non aspetta un tasto: il SOL7 ripartiva
    all'infinito, poi si sentiva una volta e si poteva solo uscire. Adesso,
    come per la chitarra, un tasto per nota e A o Q per l'accordo intero,
    che dura due quarti al tempo del metronomo (collaudo del 7 ottobre 2026)."""
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumento_attivo": "Special 20"})
    monkeypatch.setattr(config, "ARMONICA", richter)
    monkeypatch.setattr(armonica_vista, "menu", lambda **_k: pytest.fail("con un gruppo solo il menu non serve"))
    mixer, rese = ascolto_finto(monkeypatch, ["2", "q", "x", "9", "a", chr(27)])
    armonica_vista.accordi({7, 11, 2, 5}, {7: "G", 11: "B", 2: "D", 5: "F"}, "SOL7")
    accordo = (67, 71, 74, 77)
    durata = 120 / 90
    assert rese == [(accordo, durata), ((71,), durata), (accordo, durata), (accordo, durata)]
    # Una voce per nota e l'ultima per l'accordo; prima di ogni suono le
    # altre voci si chiudono con la rampa, un fiato alla volta, e il mixer
    # non satura sommando una nota all'accordo
    assert [voce for voce, _ in mixer[0].suonate] == [4, 1, 4, 4]
    assert mixer[0].lasciate[:4] == [0, 1, 2, 3] and mixer[0].lasciate[4:8] == [0, 2, 3, 4]
    assert not mixer[0].aperto
    uscita = capsys.readouterr().out
    assert "-2 -3 -4 -5: SOL4 SI4 RE5 FA5." in uscita
    assert "Note: SOL4 - SI4 - RE5 - FA5 (1-4, A, Q, SPAZIO, ESC)" in uscita
    assert "90 BPM" in uscita and "Comando non valido" in uscita


def test_col_suono_midi_il_gruppo_suona_sul_canale_dell_armonica(monkeypatch, richter):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumento_attivo": "Special 20"})
    monkeypatch.setattr(config, "ARMONICA", richter)
    mixer, rese = ascolto_finto(monkeypatch, ["1", chr(27)], suono="midi", bpm=120)
    monkeypatch.setattr(armonica_vista.suoni, "prepara_canale_armonica", lambda: 2)
    midi = []
    monkeypatch.setattr(armonica_vista.GBAudio, "play_midi_note_temp", lambda n, d, canale=0: midi.append((n, d, canale)))
    armonica_vista.accordi({7, 11, 2, 5}, {7: "G", 11: "B", 2: "D", 5: "F"}, "SOL7")
    assert midi == [(67, 1.0, 2), (71, 1.0, 2), (74, 1.0, 2), (77, 1.0, 2), (67, 1.0, 2)]
    assert rese == [] and mixer[0].suonate == []


def test_la_nota_midi_ribattuta_dura_quanto_deve(monkeypatch):
    """Il timer della nota vecchia spegneva quella ribattuta: con l'accordo
    appena partito, la nota del tasto 1 durava meno di due quarti."""
    import time
    eventi = []

    class Porta:
        h_midi = 1

        def note_on(self, numero, _velocita, _canale):
            eventi.append(("on", numero))

        def note_off(self, numero, _canale):
            eventi.append(("off", numero))

    gb = armonica_vista.GBAudio
    monkeypatch.setattr(gb, "get_midi_out", lambda: Porta())
    monkeypatch.setattr(gb, "_NOTE_ACCESE", {})
    gb.play_midi_note_temp(67, 0.2, canale=2)
    time.sleep(0.05)
    # La ribattuta spegne prima la nota che suona, poi la riaccende
    gb.play_midi_note_temp(67, 0.4, canale=2)
    time.sleep(0.25)
    assert eventi == [("on", 67), ("off", 67), ("on", 67)]
    time.sleep(0.35)
    assert eventi == [("on", 67), ("off", 67), ("on", 67), ("off", 67)]


def test_la_corda_tagliata_a_due_quarti_si_chiude_con_la_rampa(monkeypatch):
    """La corda pizzicata resa per due quarti finiva con uno scatto: adesso
    gli ultimi sessanta millesimi scendono a zero."""
    import suoni
    monkeypatch.setattr(config, "impostazioni", config.get_impostazioni_default())
    mono = suoni.mono_delle_note([60, 64, 67], suoni.parametri_suono("suono_1"), dur=0.5)
    assert abs(float(mono[-1])) < 1e-6
    assert float(np.abs(mono[-50:]).max()) < 0.05 * float(np.abs(mono).max())


def test_il_tempo_e_quello_del_metronomo_attivo(monkeypatch):
    """I BPM vengono dall'ultimo preset del metronomo; senza preset, o con un
    valore che non e' un tempo, quelli con cui il metronomo parte."""
    for stato, atteso in (({"bpm": 90}, 90), (None, 120), ({"bpm": "veloce"}, 120), ({"bpm": 0}, 120)):
        finto = type("Preset", (), {"get_last_used_preset": lambda self, s=stato: ("1", s)})
        monkeypatch.setattr(armonica_vista.clitronomo, "PresetManager", lambda silenzioso=False, f=finto: f())
        assert armonica_vista.tempo_del_metronomo() == atteso
    assert armonica_vista.durata_due_quarti(60) == 2.0


def test_i_gradi_dei_modi_plagali_partono_dalla_tonica(monkeypatch, capsys, richter):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    s = esercizio_scale._costruisci_scala("D", "concrete:HypodorianScale", 4, richter)
    esercizio_scale._tablatura_completa(s, richter)
    righe = capsys.readouterr().out.splitlines()
    assert next(r for r in righe if r.startswith("Grado 1")).startswith("Grado 1, RE:")


def test_l_ottava_dell_esercizio_comincia_sull_armonica(monkeypatch, richter):
    """La Hypodorian di RE comincia dal LA3, sotto il DO4 dell'armonica."""
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    monkeypatch.setattr(esercizio_scale, "dgt", lambda _p="", **k: k["default"])
    scelta = esercizio_scale._scegli_ottava("D", "concrete:HypodorianScale", richter)
    assert scelta.tecniche[0] is not None


def test_le_scale_che_non_si_ripetono_all_ottava(monkeypatch, capsys, richter):
    """La Bohlen-Pierce si ripete alla dodicesima: niente classi inventate."""
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    s = esercizio_scale._costruisci_scala("C", "scala:bohlen-p", 4, richter)
    assert not esercizio_scale._si_ripete_all_ottava(s)
    note, gradi = esercizio_scale._note_su_estensione(s, richter)
    assert gradi == {}
    numeri = [m for m, _ in note]
    assert 61 not in numeri and 64 not in numeri and 67 not in numeri
    assert 73 in numeri and 76 in numeri
    esercizio_scale._tabella_posizioni(s, richter, 1)
    assert "la tabella non si fa" in capsys.readouterr().out
    assert esercizio_scale._si_ripete_all_ottava(esercizio_scale._costruisci_scala("C", "comune:blues", 4, richter))


def test_i_gradi_si_contano_dalla_tonica_come_nelle_formule(monkeypatch, capsys, richter):
    """Verifica della teoria del 7 ottobre 2026: nel SOL blues il REb era il
    grado 4, mentre e' la quinta diminuita."""
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    etichetta = esercizio_scale._etichetta_grado
    assert [etichetta("G", n) for n in ("G", "B-", "C", "D-", "D", "F")] == ["1", "b3", "4", "b5", "5", "b7"]
    assert [etichetta("C", n) for n in ("D", "E", "F#", "G#", "B-")] == ["2", "3", "#4", "#5", "b7"]
    assert [etichetta("A#", n) for n in ("C##", "E#", "G##")] == ["3", "5", "7"]
    s = esercizio_scale._costruisci_scala("G", "comune:blues", 4, richter)
    esercizio_scale._tablatura_completa(s, richter)
    gradi = [r for r in capsys.readouterr().out.splitlines() if r.startswith("Grado ")]
    assert [r.split(":")[0] for r in gradi] == ["Grado 1, SOL", "Grado b3, SIb", "Grado 4, DO", "Grado b5, REb", "Grado 5, RE", "Grado b7, FA"]


def test_gli_accordi_sulle_minori_hanno_la_grafia_dell_accordo(monkeypatch, capsys):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumento_attivo": "Minore"})
    monkeypatch.setattr(config, "ARMONICA", armonica.HarmonicaModel("C", "natural_minor"))
    viste = []
    monkeypatch.setattr(armonica_vista, "menu", lambda **k: viste.append(k["d"]))
    armonica_vista.accordi({7, 10, 2}, {7: "G", 10: "B-", 2: "D"}, "SOL minore")
    voci = " ".join(viste[0].values())
    assert "-1 -2 -3: RE4 SOL4 SIb4" in voci
    assert "LA#" not in voci + capsys.readouterr().out


def test_le_toniche_delle_posizioni_con_l_armatura_dell_armonica():
    assert [armonica.tonica_della_posizione("E", n) for n in (1, 2, 3, 4, 5, 6, 12)] == ["E", "B", "F#", "C#", "G#", "D#", "A"]
    assert [armonica.tonica_della_posizione("C", n) for n in (1, 2, 3, 4, 5, 6, 12)] == ["C", "G", "D", "A", "E", "B", "F"]
    assert [armonica.tonica_della_posizione("Bb", n) for n in (1, 2, 4, 6)] == ["Bb", "F", "G", "A"]
    assert armonica.tonica_della_posizione("E", 7) == "Bb"


def test_la_cima_delle_solo_a_dodici_e_sedici_fori_e_un_re():
    """La Hohner 270 va dal DO4 al RE7: il foro 12 aspirato con il cursore e'
    un RE, perche' il DO c'e' gia' soffiando."""
    dodici = armonica.HarmonicaModel("C", "solo", 12)
    assert simboli(dodici)["-12<"] == "D7"
    assert [nome(m) for m in dodici.estensione()] == ["C4", "D7"]
    assert "-12<" not in [t.simbolo for t in dodici.tecniche_per_nota(96)]
    assert simboli(armonica.HarmonicaModel("C", "solo", 16))["-16<"] == "D7"
    # La Solo a dieci fori, come la Trochilus, finisce su FA6 e FA#6: non cambia
    assert simboli(armonica.HarmonicaModel("C", "solo", 10, valvole=False))["-10<"] == "F#6"


def test_il_messaggio_senza_gruppi_dice_senza_note_estranee(monkeypatch, capsys, richter):
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumento_attivo": "Special 20"})
    monkeypatch.setattr(config, "ARMONICA", richter)
    monkeypatch.setattr(armonica_vista, "key", lambda *_a, **_k: "")
    monkeypatch.setattr(richter, "accordi", lambda classi: [])
    armonica_vista.accordi({2, 6, 9, 0}, {2: "D", 6: "F#", 9: "A", 0: "C"}, "RE7")
    assert "senza note estranee" in capsys.readouterr().out
