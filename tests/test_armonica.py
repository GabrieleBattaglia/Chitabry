# Chitabry, prove dell'armonica: ance, bending, overbend, notazione, posizioni, accordi e archivio.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nate con la 9.0.0, issue 58. Le tabelle di confronto sono quelle dei
# metodi e dei costruttori: l'armonica in DO comincia dal DO centrale.

import json

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
    assert [nome(m) for m in cromatica.estensione()] == ["C4", "C#7"]
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
        armonica.HarmonicaModel("C", "solo", 10)
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
        "-4//": "al massimo di 1 semitoni",
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
    quarto = pitch.Pitch("A4")
    quarto.microtone = 50
    assert esercizio_scale.midi_temperato(quarto) is None
    assert esercizio_scale.midi_temperato("non un'altezza") is None
