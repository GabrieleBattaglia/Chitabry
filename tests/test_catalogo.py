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
