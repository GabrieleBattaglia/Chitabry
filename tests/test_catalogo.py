# Chitabry, prove del catalogo delle scale: descrizioni dell'archivio Scala e classi di music21.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Il catalogo vero si costruisce una volta sola per tutto il file: interroga
# music21 e legge quasi quattromila file, e costa un secondo.

import pytest

import scale_catalog


@pytest.fixture(scope="module")
def catalogo():
    return scale_catalog.build_scale_catalog()


def test_le_scale_scala_portano_la_loro_descrizione(catalogo):
    per_id = {voce["programmatic_id"]: voce for voce in catalogo if voce["paradigm"] == "scala"}
    assert len(per_id) > 3900
    assert per_id["breed-blues1"]["friendly_name"] == "Graham Breed's blues scale in 22-tET"
    assert per_id["05-19"]["friendly_name"] == "5 out of 19-tET"
    con_blues = [v for v in per_id.values() if "blues" in v["friendly_name"].lower()]
    assert len(con_blues) >= 6


def test_le_classi_generiche_non_sono_scale(catalogo):
    concrete = {voce["programmatic_id"] for voce in catalogo if voce["paradigm"] == "concrete"}
    assert not concrete & scale_catalog.CLASSI_GENERICHE
    assert {"MajorScale", "DorianScale", "WeightedHexatonicBlues", "OctatonicScale"} <= concrete


def test_la_descrizione_salta_i_commenti(tmp_path):
    file_scl = tmp_path / "prova.scl"
    file_scl.write_text("! prova.scl\n!\nUna scala di prova\n 2\n!\n9/8\n2/1\n", encoding="utf-8")
    assert scale_catalog.descrizione_scl(file_scl) == "Una scala di prova"
    vuota = tmp_path / "vuota.scl"
    vuota.write_text("! vuota.scl\n\n 1\n2/1\n", encoding="utf-8")
    assert scale_catalog.descrizione_scl(vuota) == ""
    vecchia = tmp_path / "vecchia.scl"
    vecchia.write_bytes("! vecchia\nMaqam Sab\xe1\n".encode("latin-1"))
    assert scale_catalog.descrizione_scl(vecchia) == "Maqam Sabá"
    assert scale_catalog.descrizione_scl(tmp_path / "manca.scl") == ""


def test_il_sol_blues_ha_la_grafia_giusta():
    from music21 import pitch
    sol_blues = scale_catalog.scala_comune(pitch.Pitch("G4"), "blues")
    assert [p.nameWithOctave for p in sol_blues.pitches] == ["G4", "B-4", "C5", "D-5", "D5", "F5", "G5"]
    usi = scale_catalog.get_scale_from_usi("comune:G4:blues")
    assert [p.name for p in usi.pitches] == ["G", "B-", "C", "D-", "D", "F", "G"]
    with pytest.raises(scale_catalog.ScaleException):
        scale_catalog.get_scale_from_usi("comune:G4:inesistente")


def test_ogni_scala_comune_si_costruisce_su_ogni_tonica():
    from music21 import pitch
    for tonica in ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"):
        for chiave, _nome, intervalli, _formula in scale_catalog.SCALE_COMUNI:
            altezze = scale_catalog.scala_comune(pitch.Pitch(tonica + "4"), chiave).pitches
            assert len(altezze) == len(intervalli) + 1, (tonica, chiave)
            # La grafia e' quella degli intervalli, anche sulle toniche con il diesis
            attese = [pitch.Pitch(tonica + "4").transpose(i).nameWithOctave for i in intervalli]
            assert [p.nameWithOctave for p in altezze[:-1]] == attese, (tonica, chiave)
            assert altezze[-1].name == altezze[0].name, (tonica, chiave)
            semitoni = [round(p.ps - altezze[0].ps) for p in altezze]
            assert semitoni == sorted(semitoni) and semitoni[-1] == 12, (tonica, chiave)
            assert len({s % 12 for s in semitoni}) == len(intervalli), (tonica, chiave)


def test_il_catalogo_ha_i_tre_gruppi(catalogo):
    comuni = [v for v in catalogo if v["paradigm"] == "comune"]
    # Il catalogo e' ordinato per nome: conta che ci siano tutte, una volta sola
    assert sorted(v["programmatic_id"] for v in comuni) == sorted(c[0] for c in scale_catalog.SCALE_COMUNI)
    assert all(v["descrizione"] for v in comuni)
    assert all(v["descrizione"] for v in catalogo if v["paradigm"] == "concrete")


def test_la_scelta_del_tipo_in_tre_gruppi(catalogo, monkeypatch):
    import config
    import esercizio_scale
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino"})
    monkeypatch.setattr(scale_catalog, "SCALE_CATALOG", catalogo)
    risposte = iter(["1", "blues", "2", "Major", "3"])
    viste = []

    def menu_finto(**opzioni):
        viste.append(opzioni["d"])
        return next(risposte)

    monkeypatch.setattr(esercizio_scale, "menu", menu_finto)
    cercate = []

    def ricerca_finta(voci, prompt, tipo, **_opzioni):
        cercate.append(voci)
        return next(chiave for chiave, testo in voci.items() if "breed-blues1" in testo)

    monkeypatch.setattr(esercizio_scale, "fuzzy_search_and_select", ricerca_finta)
    assert esercizio_scale._scegli_tipo("G") == "comune:blues"
    assert "1 b3 4 b5 5 b7" in viste[1]["blues"]
    assert esercizio_scale._scegli_tipo("G") == "concrete:MajorScale"
    assert esercizio_scale._scegli_tipo("G") == "scala:breed-blues1"
    assert len(cercate[0]) > 3900


def test_la_ricerca_con_piu_parole(monkeypatch):
    import ricerca
    voci = {"a": "Observed Japanese pentatonic koto scale", "b": "Chinese pentatonic", "c": "Japanese ritsu"}
    risposte = iter(["pentatonic japanese", "1"])
    monkeypatch.setattr(ricerca, "dgt", lambda *_a, **_k: next(risposte))
    assert ricerca.fuzzy_search_and_select(voci, "Cerca: ", "scala") == "a"


def test_la_ricerca_rispetta_il_massimo(monkeypatch, capsys):
    import ricerca
    voci = {str(i): f"scala pentatonic {i}" for i in range(30)}
    risposte = iter(["pentatonic", ""])
    monkeypatch.setattr(ricerca, "dgt", lambda *_a, **_k: next(risposte))
    assert ricerca.fuzzy_search_and_select(voci, "Cerca: ", "scala") is None
    assert "troppi risultati (30, il massimo e' 20)" in capsys.readouterr().out
    risposte = iter(["pentatonic", "3"])
    assert ricerca.fuzzy_search_and_select(voci, "Cerca: ", "scala", massimo=50) == "2"
