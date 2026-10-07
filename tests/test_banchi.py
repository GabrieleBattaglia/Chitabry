# Chitabry, prove dei banchi di suoni: riconoscimento dei soundfont General MIDI, ricerca, suono banco.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nate con la 9.10.0. I soundfont delle prove sul formato sono finti, fatti
# di sola intestazione; le prove che suonano davvero usano il FluidSynth e il
# banco che MeTeOra ha gia' scaricato sul computer di Gabriele, e altrove si
# saltano.

import math
import os
import struct

import numpy as np
import pytest

import accordatore
import banchi
import config
import GBAudio
import suoni

FLUIDSYNTH_DI_METEORA = "E:/git/mine/MeTeOra/fluidsynth"
BANCO_SGM = r"E:\VstPlugins\SF2 Instruments\SGM-V2.01.sf2"
CI_SONO = os.path.isfile(os.path.join(FLUIDSYNTH_DI_METEORA, banchi.FLUIDSYNTH_DLL[0])) and os.path.isfile(BANCO_SGM)


def soundfont_finto(percorso, programmi=128, batteria=True):
    """Un sf2 di sola intestazione: RIFF sfbk, una lista pdta con il phdr."""
    record = [struct.pack("<20sHHH", b"preset", p, 0, 0) + b"\0" * 12 for p in range(programmi)]
    if batteria:
        record.append(struct.pack("<20sHHH", b"drum", 0, 128, 0) + b"\0" * 12)
    record.append(struct.pack("<20sHHH", b"EOP", 0, 0, 0) + b"\0" * 12)
    phdr = b"".join(record)
    pdta = b"pdta" + b"phdr" + struct.pack("<I", len(phdr)) + phdr
    lista = b"LIST" + struct.pack("<I", len(pdta)) + pdta
    corpo = b"sfbk" + lista
    with open(percorso, "wb") as f:
        f.write(b"RIFF" + struct.pack("<I", len(corpo)) + corpo)


def test_si_riconoscono_i_banchi_general_midi(tmp_path):
    gm = tmp_path / "completo.sf2"
    soundfont_finto(gm)
    pochi = tmp_path / "pochi.sf2"
    soundfont_finto(pochi, programmi=12)
    senza = tmp_path / "senza_batteria.sf2"
    soundfont_finto(senza, batteria=False)
    falso = tmp_path / "falso.sf2"
    falso.write_bytes(b"non sono un soundfont")
    assert banchi.e_un_banco(gm) and banchi.general_midi(gm)
    assert banchi.e_un_banco(pochi) and not banchi.general_midi(pochi)
    assert not banchi.general_midi(senza)
    assert not banchi.e_un_banco(falso) and not banchi.general_midi(falso)


def test_la_ricerca_tiene_solo_i_general_midi(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "node_modules").mkdir()
    soundfont_finto(tmp_path / "a" / "Bello.sf2")
    soundfont_finto(tmp_path / "a" / "Piccolo.sf2", programmi=5)
    soundfont_finto(tmp_path / "node_modules" / "Saltato.sf2")
    trovati = banchi.cerca_banchi([str(tmp_path)])
    assert [os.path.basename(p) for p, _ in trovati] == ["Bello.sf2"]
    assert banchi.cerca_banchi([str(tmp_path)], fermo=lambda: True) == []
    assert banchi.dimensione_da_leggere(148398306) == "148 MB"
    assert banchi.dimensione_da_leggere(2_500_000) == "2.5 MB"


def test_il_banco_si_salta_finche_non_e_pronto(monkeypatch):
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": ""}, "midi_strumento": 0})
    assert suoni.prossimo_suono("midi") == "suono_1"
    monkeypatch.setattr(suoni, "banco_pronto", lambda: True)
    assert suoni.prossimo_suono("midi") == "banco"
    assert suoni.prossimo_suono("banco") == "suono_1"
    assert suoni.sigla_suono("banco") == "BAN"


def test_il_gioco_col_suono_alterna_anche_il_banco(monkeypatch):
    """In Gioca col suono la barra spaziatrice alternava solo i due suoni
    sintetici: con un banco pronto c'e' anche lui."""
    import gioca_suono
    monkeypatch.setattr(suoni, "banco_pronto", lambda: False)
    assert gioca_suono._prossimo_suono("suono_1") == "suono_2"
    assert gioca_suono._prossimo_suono("suono_2") == "suono_1"
    monkeypatch.setattr(suoni, "banco_pronto", lambda: True)
    giro = ["suono_1"]
    for _ in range(3):
        giro.append(gioca_suono._prossimo_suono(giro[-1]))
    assert giro == ["suono_1", "suono_2", "banco", "suono_1"]
    assert gioca_suono._prossimo_suono("midi") == "suono_1"


def test_le_note_del_banco_passano_dal_renderer(monkeypatch):
    """Chi suona non sa quale suono sta suonando: configura e chiede il mono."""
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "x.sf2", "volume": 0.5, "dur": 2.0}, "midi_strumento": 22})
    chiamate = []

    def rendi_finta(banco, programma, frequenza, secondi, fs, velocita=100, coda=banchi.CODA):
        chiamate.append((banco, programma, round(frequenza, 2), secondi, coda))
        return np.ones(10, dtype=np.float32)

    monkeypatch.setattr(banchi, "rendi_nota", rendi_finta)
    monkeypatch.setattr(banchi, "fattore_dello_strumento", lambda *_a: 1.0)
    parametri = suoni.parametri_suono("banco")
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    suoni.configura_renderer(renderer, 440.0, parametri)
    mono = suoni.mono_da_renderer(renderer)
    assert mono.tolist() == [0.5] * 10
    tenuta, ciclo = suoni.tenuta_da_renderer(renderer)
    assert ciclo is None and len(tenuta) == 10
    # La tenuta lascia dentro gli otto secondi il rilascio dello strumento
    assert chiamate == [("x.sf2", 22, 440.0, 2.0, banchi.CODA), ("x.sf2", 22, 440.0, banchi.SECONDI_TENUTA - banchi.CODA, banchi.CODA)]
    # Lo stesso renderer, riconfigurato per un sintetico, torna sintetico
    suoni.configura_renderer(renderer, 440.0, {**parametri, "banco": False, "kind": 1})
    assert renderer.nota_del_banco is None


def test_un_banco_che_non_suona_si_dice_una_volta(monkeypatch, capsys):
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "manca.sf2"}, "midi_strumento": 0})
    monkeypatch.setattr(suoni, "_BANCO_AVVISATO", [])

    def rotto(*_a, **_k):
        raise OSError("il banco di suoni manca.sf2 non si carica")

    monkeypatch.setattr(banchi, "rendi_nota", rotto)
    renderer = GBAudio.NoteRenderer(fs=GBAudio.FS)
    suoni.configura_renderer(renderer, 440.0, suoni.parametri_suono("banco"))
    assert suoni.mono_da_renderer(renderer) is None
    assert suoni.mono_da_renderer(renderer) is None
    assert capsys.readouterr().out.count("non suona") == 1


@pytest.mark.skipif(not CI_SONO, reason="FluidSynth di MeTeOra o banco SGM assenti")
def test_il_banco_vero_suona_intonato(monkeypatch):
    """Con FluidSynth e il banco SGM: la nota ha la frequenza chiesta, anche
    fuori dal temperamento grazie al pitch bend, e un'armonica senza vibrato."""
    monkeypatch.setattr(banchi, "cartella_fluidsynth", lambda: FLUIDSYNTH_DI_METEORA)
    banchi.chiudi()
    try:
        for frequenza in (440.0, 446.0, 261.63):
            mono = banchi.rendi_nota(BANCO_SGM, GBAudio.PROGRAMMA_ARMONICA, frequenza, 1.0, 48000)
            assert len(mono) == int(1.0 * 48000) + int(banchi.CODA * 48000)
            letture = [accordatore.rileva_frequenza(mono[i:i + 4096], 48000) for i in range(9600, 40000, 4096)]
            centesimi = [1200 * math.log2(f / frequenza) for f in letture if f > 0]
            assert centesimi and max(abs(c) for c in centesimi) < 8, (frequenza, centesimi)
        assert float(np.abs(mono).max()) > 0.05
    finally:
        banchi.chiudi()


@pytest.mark.skipif(not CI_SONO, reason="FluidSynth di MeTeOra o banco SGM assenti")
def test_gli_strumenti_del_banco_hanno_lo_stesso_livello(monkeypatch):
    """Il DO centrale di ogni strumento arriva al picco di riferimento:
    l'armonica e la chitarra del banco SGM partivano da 0,14 e 0,45. Gli
    archi tremolo, che crescono piano, misurati su mezzo secondo prendevano
    un fattore che nelle note lunghe li portava a 0,68 su 0,4."""
    monkeypatch.setattr(banchi, "cartella_fluidsynth", lambda: FLUIDSYNTH_DI_METEORA)
    banchi.chiudi()
    try:
        for programma in (GBAudio.PROGRAMMA_ARMONICA, 24, 0):
            renderer = banchi.RendererBanco(BANCO_SGM, programma, 48000)
            renderer.set_params(261.63, 4.0, 1.0)
            picco = float(np.abs(renderer.render()).max())
            assert picco == pytest.approx(banchi.PICCO_DI_RIFERIMENTO, rel=0.1), programma
        archi = banchi.RendererBanco(BANCO_SGM, 44, 48000)
        archi.set_params(261.63, 4.0, 1.0)
        assert float(np.abs(archi.render()).max()) <= banchi.PICCO_DI_RIFERIMENTO * 1.1
    finally:
        banchi.chiudi()


@pytest.mark.skipif(not CI_SONO, reason="FluidSynth di MeTeOra o banco SGM assenti")
def test_la_nota_prima_non_rientra_nella_successiva(monkeypatch):
    """Dopo un DO4 d'organo, nei primi 100 ms del MI4 non c'e' piu' il DO:
    il reset non spegneva le voci, e il DO valeva piu' del MI stesso."""
    monkeypatch.setattr(banchi, "cartella_fluidsynth", lambda: FLUIDSYNTH_DI_METEORA)
    banchi.chiudi()
    try:
        fs = 44100
        banchi.rendi_nota(BANCO_SGM, 19, 261.63, 1.0, fs, coda=0.0)
        mi = banchi.rendi_nota(BANCO_SGM, 19, 329.63, 1.0, fs)[:fs // 10]
        tempi = np.arange(len(mi)) / fs

        def componente(frequenza):
            return abs(np.dot(mi, np.exp(-2j * np.pi * frequenza * tempi))) * 2 / len(mi)

        assert componente(261.63) < 0.1 * componente(329.63)
    finally:
        banchi.chiudi()


@pytest.mark.skipif(not CI_SONO, reason="FluidSynth di MeTeOra o banco SGM assenti")
def test_la_nota_tenuta_finisce_col_suo_rilascio(monkeypatch):
    """La tenuta della Tastiera dura otto secondi e finisce nel silenzio,
    senza lo scatto di una nota troncata a pieno volume."""
    monkeypatch.setattr(banchi, "cartella_fluidsynth", lambda: FLUIDSYNTH_DI_METEORA)
    banchi.chiudi()
    try:
        fs = 44100
        for programma in (19, 52, GBAudio.PROGRAMMA_ARMONICA):
            renderer = banchi.RendererBanco(BANCO_SGM, programma, fs)
            renderer.set_params(261.63, 1.0, 0.8)
            mono, ciclo = renderer.render_tenuta()
            assert ciclo is None
            assert len(mono) == pytest.approx(banchi.SECONDI_TENUTA * fs, abs=2)
            assert float(np.abs(mono[-fs // 100:]).max()) < 0.01, programma
    finally:
        banchi.chiudi()


def test_chiudi_aspetta_la_nota_in_corso():
    """chiudi libera il synth solo quando la nota che lo usa ha finito: senza
    il lucchetto, la tastiera MIDI che suona mentre si cambia banco faceva
    chiudere Chitabry con un accesso non valido."""
    import threading
    chiuso = threading.Event()
    with banchi._BLOCCO:
        filo = threading.Thread(target=lambda: (banchi.chiudi(), chiuso.set()))
        filo.start()
        assert not chiuso.wait(0.2)
    filo.join(2)
    assert chiuso.is_set()


def test_una_risposta_interrotta_e_un_errore_di_scaricamento(monkeypatch):
    """Una risposta HTTP troncata o che non e' HTTP diventa un OSError, che
    le impostazioni dicono come scaricamento non riuscito invece di chiudersi."""
    import http.client
    import urllib.request

    def interrotta(*_a, **_k):
        raise http.client.IncompleteRead(b"mezzo")

    monkeypatch.setattr(urllib.request, "urlopen", interrotta)
    with pytest.raises(OSError, match="non valida o interrotta"):
        banchi._scarica("https://esempio.invalid/banco.sf2")


def test_scegliere_un_banco_dalle_impostazioni(monkeypatch, tmp_path):
    """Il percorso a copione: FluidSynth gia' presente, un banco trovato sui
    dischi, scelto, con il volume, e usato come suono attivo."""
    import gestore_impostazioni
    trovato = str(tmp_path / "Bello.sf2")
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "", "volume": 0.8}, "tipo_suono": "suono_1"})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(banchi, "fluidsynth_presente", lambda: True)
    monkeypatch.setattr(banchi, "cerca_banchi", lambda **_k: [(trovato, 30_000_000)])
    monkeypatch.setattr(gestore_impostazioni, "enter_escape", lambda *_a: True)
    viste = []

    def menu_finto(**opzioni):
        viste.append(opzioni["d"])
        return trovato

    monkeypatch.setattr(gestore_impostazioni, "menu", menu_finto)
    risposte = iter([0.6, "s"])
    monkeypatch.setattr(gestore_impostazioni, "dgt", lambda *_a, **_k: next(risposte))
    monkeypatch.setattr(gestore_impostazioni, "key", lambda *_a, **_k: "")
    gestore_impostazioni._configura_banco()
    assert config.impostazioni["banco"] == {"percorso": trovato, "volume": 0.6}
    assert config.impostazioni["tipo_suono"] == "banco"
    assert list(viste[0]) == [trovato, "scarica"]
    assert viste[0][trovato].startswith("Bello.sf2, 30 MB, in ")


def test_senza_banchi_fluidr3_si_scarica_solo_con_un_si(monkeypatch):
    """Senza banchi trovati l'elenco aveva la sola voce per scaricare, e il
    menu, con una voce, la sceglieva da solo: 148 MB senza chiedere."""
    import gestore_impostazioni
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "", "volume": 0.8}, "tipo_suono": "suono_1"})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(banchi, "fluidsynth_presente", lambda: True)
    monkeypatch.setattr(banchi, "cerca_banchi", lambda **_k: [])
    domande = []

    def risposta(testo):
        domande.append(testo)
        return len(domande) == 1

    monkeypatch.setattr(gestore_impostazioni, "enter_escape", risposta)
    monkeypatch.setattr(gestore_impostazioni, "menu", lambda **_k: pytest.fail("il menu sceglierebbe da solo"))
    monkeypatch.setattr(banchi, "scarica_fluidr3", lambda *_a: pytest.fail("scaricato senza chiedere"))
    gestore_impostazioni._configura_banco()
    assert len(domande) == 2 and "Scarico FluidR3 GM" in domande[1] and "148 MB" in domande[1]
    assert config.impostazioni["banco"]["percorso"] == "" and config.impostazioni["tipo_suono"] == "suono_1"


def test_cambiare_strumento_lascia_attivo_il_banco(monkeypatch, capsys):
    """Scegliere lo strumento passava sempre al MIDI di Windows, anche con il
    banco attivo, che usa lo stesso strumento."""
    import gestore_impostazioni
    armonica = GBAudio.MIDI_INSTRUMENTS[GBAudio.PROGRAMMA_ARMONICA]
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(gestore_impostazioni, "menu", lambda **_k: armonica)
    monkeypatch.setattr(gestore_impostazioni, "key", lambda *_a, **_k: "")
    monkeypatch.setattr(GBAudio, "get_midi_out", lambda: type("Uscita", (), {"select_instrument": lambda self, p: None})())
    for prima, dopo in (("banco", "banco"), ("suono_1", "midi")):
        monkeypatch.setattr(config, "impostazioni", {"tipo_suono": prima, "midi_strumento": 0})
        gestore_impostazioni._scegli_strumento_midi()
        assert config.impostazioni == {"tipo_suono": dopo, "midi_strumento": GBAudio.PROGRAMMA_ARMONICA}
    assert "Il suono attivo resta il banco." in capsys.readouterr().out
