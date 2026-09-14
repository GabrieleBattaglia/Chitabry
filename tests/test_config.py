# Chitabry, prove dell'archivio delle impostazioni.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Tutto avviene in una cartella temporanea: il file vero non si tocca mai.

import json
import os

import pytest

import config


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    percorso = str(tmp_path / "chitabry-settings.json")
    monkeypatch.setattr(config, "FILE_IMPOSTAZIONI", percorso)
    monkeypatch.setattr(config, "impostazioni", {})
    monkeypatch.setattr(config, "archivio_modificato", False)
    return percorso


def test_file_mancante_crea_i_predefiniti(archivio):
    config.carica_impostazioni()
    assert os.path.exists(archivio)
    assert config.impostazioni["versione_formato"] == config.VERSIONE_FORMATO
    assert config.impostazioni["strumento_attivo"] == config.STRUMENTO_PREDEFINITO
    assert not config.archivio_modificato


def test_migrazione_da_formato_vecchio(archivio):
    vecchio = {
        "nomenclatura": "latino",
        "strumento": {"nome": "Mia chitarra", "accordatura": ["D2", "A2", "D3", "G3", "B3", "E4"], "tasti": 19},
        "suono_1": {"descrizione": "x", "pluck_hardness": 0.5, "damping_factor": 0.99},
        "suono_2": {"descrizione": "Suono per scale (simil-flauto)", "kind": 1, "adsr": [1, 1, 90, 1]},
        "chordpedia": {"C": {"x32010": 1}},
    }
    with open(archivio, "w", encoding="utf-8") as f:
        json.dump(vecchio, f)
    config.carica_impostazioni()
    imp = config.impostazioni
    assert "strumento" not in imp
    assert imp["strumento_attivo"] == "Mia chitarra"
    assert imp["strumenti"]["Mia chitarra"]["tasti"] == 19
    assert imp["suono_2"]["descrizione"] == "Suono sintetico (onda semplice)"
    assert imp["suono_1"]["volume"] == 0.45
    assert imp["suono_1"]["pluck_hardness"] == 0.5
    assert imp["default_bpm"] == 60
    assert imp["midi_in_dispositivo"] == ""
    assert imp["chordpedia"] == {"C": {"x32010": 1}}
    assert imp["versione_formato"] == config.VERSIONE_FORMATO
    with open(archivio, encoding="utf-8") as f:
        su_disco = json.load(f)
    assert su_disco == imp


def test_archivio_gia_aggiornato_non_si_riscrive(archivio):
    config.impostazioni = config.get_impostazioni_default()
    config.salva_modifiche()
    prima = os.path.getmtime(archivio)
    config.impostazioni = {}
    config.carica_impostazioni()
    assert os.path.getmtime(archivio) == prima
    assert config._migra(config.impostazioni) == []


def test_salvataggio_conserva_la_copia_precedente(archivio):
    config.impostazioni = config.get_impostazioni_default()
    config.salva_modifiche()
    config.impostazioni["default_bpm"] = 99
    assert config.salva_modifiche()
    assert not os.path.exists(archivio + ".tmp")
    with open(archivio + ".bak", encoding="utf-8") as f:
        assert json.load(f)["default_bpm"] == 60
    with open(archivio, encoding="utf-8") as f:
        assert json.load(f)["default_bpm"] == 99


def test_file_corrotto_non_viene_sovrascritto(archivio, capsys):
    with open(archivio, "w", encoding="utf-8") as f:
        f.write("{ questo non e' json")
    with pytest.raises(SystemExit):
        config.carica_impostazioni()
    with open(archivio, encoding="utf-8") as f:
        assert f.read() == "{ questo non e' json"
    assert "non si legge" in capsys.readouterr().out


def test_aggiorna_manico_ripiega_sul_primo_strumento(archivio):
    config.impostazioni = config.get_impostazioni_default()
    config.impostazioni["strumenti"] = {"Ukulele": {"accordatura": ["G4", "C4", "E4", "A4"], "tasti": 12}}
    config.impostazioni["strumento_attivo"] = "Sparito"
    config.aggiorna_manico()
    assert config.impostazioni["strumento_attivo"] == "Ukulele"
    assert config.NUM_CORDE == 4
    assert config.NUM_TASTI == 12
    assert config.CORDE["4.0"] == "G4"
    assert config.CORDE["1.3"] == "C5"


def scrivi_archivio(percorso, dati):
    with open(percorso, "w", encoding="utf-8") as f:
        json.dump(dati, f)


def test_inviluppo_convertito_in_millesimi(archivio):
    # Il due per cento di nove secondi faceva centottanta millesimi di attacco:
    # la conversione conserva il suono che l'utente si era tarato.
    scrivi_archivio(archivio, {
        "versione_formato": 1,
        "suono_2": {"descrizione": "Suono sintetico (onda semplice)", "kind": 1,
                    "adsr": [0.2, 99.8, 0.0, 0.0], "volume": 0.35},
    })
    config.carica_impostazioni()
    assert config.impostazioni["suono_2"]["adsr"] == [18.0, 8982.0, 0.0, 0.0]
    assert config.impostazioni["versione_formato"] == 2


def test_chi_non_aveva_toccato_niente_prende_i_valori_nuovi(archivio):
    # Con la conversione fedele si ritroverebbe centottanta millesimi di
    # attacco, cioe' proprio il difetto che il formato nuovo toglie.
    scrivi_archivio(archivio, {
        "versione_formato": 1,
        "suono_2": {"descrizione": "Suono sintetico (onda semplice)", "kind": 1,
                    "adsr": list(config.ADSR_VECCHIO_PREDEFINITO), "volume": 0.35},
    })
    config.carica_impostazioni()
    assert config.impostazioni["suono_2"]["adsr"] == config.ADSR_PREDEFINITO


def test_il_mantenimento_resta_una_percentuale(archivio):
    # I tre tempi diventano millesimi, il mantenimento no: e' un livello di
    # volume e in millesimi non vorrebbe dire niente.
    scrivi_archivio(archivio, {
        "versione_formato": 1,
        "suono_2": {"descrizione": "x", "kind": 1, "adsr": [1.0, 2.0, 55.0, 3.0], "volume": 0.35},
    })
    config.carica_impostazioni()
    assert config.impostazioni["suono_2"]["adsr"][2] == 55.0


def test_un_archivio_gia_al_formato_2_non_si_riconverte(archivio):
    # Riconvertirlo vorrebbe dire prendere dei millesimi per percentuali e
    # moltiplicarli per novanta: l'attacco diventerebbe di novanta secondi.
    scrivi_archivio(archivio, {
        "versione_formato": 2,
        "suono_2": {"descrizione": "x", "kind": 1, "adsr": [10.0, 60.0, 70.0, 120.0], "volume": 0.35},
    })
    config.carica_impostazioni()
    assert config.impostazioni["suono_2"]["adsr"] == [10.0, 60.0, 70.0, 120.0]


def test_la_conversione_usa_la_durata_del_suono(archivio):
    # Le percentuali erano della durata di riferimento: chi l'aveva cambiata
    # aveva tempi diversi a parita' di percentuali.
    scrivi_archivio(archivio, {
        "versione_formato": 1,
        "suono_2": {"descrizione": "x", "kind": 1, "adsr": [10.0, 10.0, 50.0, 10.0],
                    "dur_accordi": 2.0, "volume": 0.35},
    })
    config.carica_impostazioni()
    assert config.impostazioni["suono_2"]["adsr"] == [200.0, 200.0, 50.0, 200.0]
