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


def test_la_ricerca_trova_anche_le_copie_di_fluidsynth(tmp_path):
    (tmp_path / "MeTeOra" / "fluidsynth").mkdir(parents=True)
    (tmp_path / "MeTeOra" / "fluidsynth" / "libfluidsynth-3.dll").write_bytes(b"finta")
    (tmp_path / "vlc").mkdir()
    (tmp_path / "vlc" / "libfluidsynth_plugin.dll").write_bytes(b"un plugin, non FluidSynth")
    motori = []
    banchi.cerca_banchi([str(tmp_path)], motori=motori)
    assert motori == [str(tmp_path / "MeTeOra" / "fluidsynth")]


def test_fluidsynth_trovato_si_usa_dalle_impostazioni(monkeypatch, tmp_path):
    """Con la cartella scritta nelle impostazioni si usa quella; se sparisce
    si torna a quella dello scaricamento, accanto ai dati di Chitabry."""
    trovata = tmp_path / "MeTeOra" / "fluidsynth"
    trovata.mkdir(parents=True)
    (trovata / "libfluidsynth-3.dll").write_bytes(b"finta")
    monkeypatch.setattr(config, "cartella_dati", lambda: str(tmp_path / "Chitabry"))
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "", "fluidsynth": str(trovata)}})
    assert banchi.cartella_fluidsynth() == str(trovata)
    assert banchi.fluidsynth_presente()
    (trovata / "libfluidsynth-3.dll").unlink()
    assert banchi.cartella_fluidsynth() == str(tmp_path / "Chitabry" / "fluidsynth")
    assert not banchi.fluidsynth_presente()
    # Nella cartella dello scaricamento servono tutte e due le DLL dello zip:
    # con la prima sola lo scaricamento si e' interrotto, e va rifatto
    scaricata = tmp_path / "Chitabry" / "fluidsynth"
    scaricata.mkdir(parents=True)
    (scaricata / "libfluidsynth-3.dll").write_bytes(b"finta")
    assert not banchi.fluidsynth_presente()
    (scaricata / "sndfile.dll").write_bytes(b"finta")
    assert banchi.fluidsynth_presente()
    # Una DLL finta non si carica, e non viene scelta
    (trovata / "libfluidsynth-3.dll").write_bytes(b"finta")
    assert banchi.fluidsynth_che_funziona([str(trovata)]) is None
    assert not banchi.fluidsynth_pronto()


@pytest.mark.skipif(not CI_SONO, reason="FluidSynth di MeTeOra o banco SGM assenti")
def test_si_sceglie_la_prima_copia_di_fluidsynth_che_si_carica(tmp_path):
    finta = tmp_path / "finta"
    finta.mkdir()
    (finta / "libfluidsynth-3.dll").write_bytes(b"non sono una DLL")
    vera = os.path.normpath(FLUIDSYNTH_DI_METEORA)
    assert banchi.fluidsynth_che_funziona([str(finta), vera]) == vera


def test_con_fluidsynth_sul_computer_non_si_scarica_un_doppione(monkeypatch, capsys):
    """Collaudo di Gabriele del 7 ottobre 2026: FluidSynth c'era, quello di
    MeTeOra, e Chitabry proponeva di scaricarlo perche' guardava solo nella
    sua cartella. Adesso la ricerca dei banchi trova anche le copie di
    FluidSynth, e Chitabry usa la prima che si carica."""
    import gestore_impostazioni
    trovato = r"E:\banchi\Bello.sf2"
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "", "volume": 0.8}, "tipo_suono": "suono_1"})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(banchi, "fluidsynth_pronto", lambda: False)

    def cerca(motori=None, **_k):
        motori.extend([r"E:\vecchia", r"E:\git\mine\MeTeOra\fluidsynth"])
        return [(trovato, 30_000_000)]

    monkeypatch.setattr(banchi, "cerca_banchi", cerca)
    monkeypatch.setattr(banchi, "fluidsynth_che_funziona", lambda cartelle: cartelle[1])
    monkeypatch.setattr(banchi, "scarica_fluidsynth", lambda *_a: pytest.fail("scaricato un doppione"))
    domande = []
    monkeypatch.setattr(gestore_impostazioni, "enter_escape", lambda testo: domande.append(testo) or True)
    monkeypatch.setattr(gestore_impostazioni, "menu", lambda **_k: trovato)
    risposte = iter([0.7, "n"])
    monkeypatch.setattr(gestore_impostazioni, "dgt", lambda *_a, **_k: next(risposte))
    monkeypatch.setattr(gestore_impostazioni, "key", lambda *_a, **_k: "")
    gestore_impostazioni._configura_banco()
    assert len(domande) == 1 and "una copia di FluidSynth" in domande[0]
    assert config.impostazioni["banco"] == {"percorso": trovato, "volume": 0.7, "fluidsynth": r"E:\git\mine\MeTeOra\fluidsynth"}
    assert "Chitabry usa quello, senza scaricarne un altro" in capsys.readouterr().out


def banco_senza_fluidsynth(monkeypatch, motori_trovati, tasto_durante_la_ricerca):
    """_configura_banco con FluidSynth che non si carica e una ricerca finta:
    restituisce le domande fatte, e alla domanda dello scaricamento risponde
    ESC."""
    import gestore_impostazioni
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": "", "volume": 0.8, "fluidsynth": r"E:\guasta"}})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(banchi, "fluidsynth_pronto", lambda: False)

    def cerca(fermo=None, motori=None, **_k):
        if fermo():
            return []
        motori.extend(motori_trovati)
        return []

    monkeypatch.setattr(banchi, "cerca_banchi", cerca)
    monkeypatch.setattr(banchi, "fluidsynth_che_funziona", lambda _cartelle: None)
    monkeypatch.setattr(banchi, "scarica_fluidsynth", lambda *_a: pytest.fail("scaricato senza un si'"))
    domande = []
    monkeypatch.setattr(gestore_impostazioni, "enter_escape", lambda testo: domande.append(testo) or len(domande) == 1)
    monkeypatch.setattr(gestore_impostazioni, "key", lambda *_a, **_k: tasto_durante_la_ricerca)
    gestore_impostazioni._configura_banco()
    return domande


def test_una_copia_guasta_si_dimentica_e_la_ricerca_fermata_si_dice(monkeypatch, capsys):
    """Una copia salvata che non si carica piu' non blocca il banco: si
    dimentica, cosi' vale di nuovo lo scaricamento. E se la ricerca si ferma
    con ESC, Chitabry non dice piu' che FluidSynth non c'e' sul computer."""
    domande = banco_senza_fluidsynth(monkeypatch, [], chr(27))
    assert "fluidsynth" not in config.impostazioni["banco"]
    assert "Ricerca fermata con ESC." in capsys.readouterr().out
    assert domande[1] == ("\rLa ricerca e' stata fermata prima di trovare FluidSynth. "
                          "Lo scarico da GitHub, dalla pagina ufficiale? (INVIO per si', ESC per no): \r")
    assert all(d.startswith("\r") and d.endswith("\r") for d in domande)


def test_copie_trovate_che_non_si_caricano(monkeypatch):
    """Prima: copie trovate, ma nessuna si carica, e subito dopo FluidSynth
    non c'e' sul computer. Le due frasi si contraddicevano."""
    domande = banco_senza_fluidsynth(monkeypatch, [r"E:\a", r"E:\b"], "")
    assert domande[1].startswith("\rNessuna delle copie di FluidSynth trovate, 2, si puo' usare.")
    domande = banco_senza_fluidsynth(monkeypatch, [], "")
    assert domande[1].startswith("\rFluidSynth non c'e' sul computer.")


def test_gli_strumenti_si_scelgono_per_nome(monkeypatch):
    """Il menu degli strumenti era numerato: adesso le chiavi sono i nomi, e
    si scelgono scrivendone le prime lettere (collaudo del 7 ottobre 2026)."""
    import gestore_impostazioni
    strumenti = {"Chitarra Standard": {"tipo": "corde", "accordatura": ["E2", "A2", "D3", "G3", "B3", "E4"], "tasti": 21,
                                       "programma_gm": 24},
                 "Special 20": {"tipo": "armonica", "famiglia": "diatonica", "tonalita": "C", "accordatura": "richter", "fori": 10,
                                "programma_gm": 22}}
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumenti": strumenti, "strumento_attivo": "Chitarra Standard"})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(config, "aggiorna_manico", lambda: None)
    viste = []
    risposte = iter(["s", "Special 20", None])

    def menu_finto(**opzioni):
        viste.append(opzioni)
        return next(risposte)

    monkeypatch.setattr(gestore_impostazioni, "menu", menu_finto)
    gestore_impostazioni.GestoreStrumenti()
    scelta = viste[1]
    assert not scelta.get("numbered") and scelta["keyslist"]
    assert list(scelta["d"]) == ["Chitarra Standard", "Special 20"]
    assert scelta["d"]["Chitarra Standard"] == "21 tasti, 6 corde, General MIDI Acoustic Guitar (nylon)"
    assert scelta["d"]["Special 20"].startswith("armonica diatonica in DO")
    assert scelta["d"]["Special 20"].endswith(", General MIDI Harmonica")
    assert config.impostazioni["strumento_attivo"] == "Special 20"


def test_con_uno_strumento_solo_non_si_invita_a_scrivere(monkeypatch, capsys):
    """Il menu con una voce sola la sceglie senza leggere tasti: l'invito a
    scrivere le prime lettere mandava le lettere al menu dopo, o nella
    risposta S/N. E scegliendo lo strumento gia' attivo non si leggeva niente."""
    import gestore_impostazioni
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(config, "aggiorna_manico", lambda: None)
    chitarra = {"tipo": "corde", "accordatura": ["E2", "A2", "D3", "G3", "B3", "E4"], "tasti": 21}

    def gestore(strumenti, attivo, risposte, conferme=()):
        monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumenti": dict(strumenti), "strumento_attivo": attivo})
        sequenza = iter(risposte)
        monkeypatch.setattr(gestore_impostazioni, "menu", lambda **_k: next(sequenza))
        altre = iter(conferme)
        monkeypatch.setattr(gestore_impostazioni, "dgt", lambda *_a, **_k: next(altre))
        gestore_impostazioni.GestoreStrumenti()
        return capsys.readouterr().out

    uscita = gestore({"Chitarra": chitarra}, "Chitarra", ["s", None])
    assert "C'e' un solo strumento, Chitarra, ed e' gia' quello attivo." in uscita and "prime lettere" not in uscita
    uscita = gestore({"Chitarra": chitarra, "Basso": chitarra}, "Chitarra", ["s", "Chitarra", None])
    assert "Chitarra e' gia' lo strumento attivo." in uscita
    uscita = gestore({"Chitarra": chitarra, "Basso": chitarra}, "Chitarra", ["e", None], ["s"])
    assert "prime lettere" not in uscita and "Strumento Basso eliminato." in uscita
    assert list(config.impostazioni["strumenti"]) == ["Chitarra"]


def test_il_giro_dei_suoni(monkeypatch):
    """Dalla 10.0.0 la barra spaziatrice gira fra i due sintetici, il banco
    con lo strumento scelto e il banco con lo strumento General MIDI dello
    strumento attivo (collaudo di Gabriele del 7 ottobre 2026). I suoni del
    banco si saltano finche' non e' pronto; quello dell'attivo anche quando
    l'attivo non ha uno strumento General MIDI, o ha proprio quello scelto."""
    strumenti = {"Hohner": {"tipo": "armonica", "programma_gm": 22}, "Ukulele": {"tipo": "corde", "programma_gm": None}}
    monkeypatch.setattr(config, "impostazioni", {"banco": {"percorso": ""}, "midi_strumento": 0, "strumenti": strumenti,
                                                 "strumento_attivo": "Hohner", "tipo_suono": "banco_strumento"})
    assert suoni.prossimo_suono("suono_2") == "suono_1"
    assert suoni.suono_attivo() == "suono_1"
    monkeypatch.setattr(suoni, "banco_pronto", lambda: True)
    giro = ["suono_1"]
    for _ in range(4):
        giro.append(suoni.prossimo_suono(giro[-1]))
    assert giro == ["suono_1", "suono_2", "banco", "banco_strumento", "suono_1"]
    assert suoni.suono_attivo() == "banco_strumento"
    assert suoni.parametri_suono("banco_strumento")["programma"] == 22
    assert suoni.parametri_suono("banco")["programma"] == 0
    assert [suoni.sigla_suono(c) for c in giro[:4]] == ["S1", "S2", "BAN", "STR"]
    # Il midi di un archivio vecchio vale il primo suono
    assert suoni.prossimo_suono("midi") == "suono_1"
    # Lo strumento scelto e' gia' l'armonica: un suono in meno
    config.impostazioni["midi_strumento"] = 22
    assert suoni.prossimo_suono("banco") == "suono_1"
    assert suoni.suono_attivo() == "banco"
    # L'ukulele non ha uno strumento General MIDI
    config.impostazioni["midi_strumento"] = 0
    config.impostazioni["strumento_attivo"] = "Ukulele"
    assert suoni.prossimo_suono("banco") == "suono_1"
    assert "nessuno" in suoni.descrizione_suono("banco_strumento")


def test_il_gioco_col_suono_usa_lo_stesso_giro(monkeypatch):
    """In Gioca col suono la barra spaziatrice alternava solo i due suoni
    sintetici; dalla 9.11 anche il banco, e dalla 10.0.0 il giro e' quello
    di tutta l'app."""
    import gioca_suono
    assert not hasattr(gioca_suono, "_prossimo_suono")
    with open(gioca_suono.__file__, encoding="utf-8") as f:
        assert "suoni.prossimo_suono(stato['suono'])" in f.read()


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
            mono = banchi.rendi_nota(BANCO_SGM, config.PROGRAMMA_ARMONICA, frequenza, 1.0, 48000)
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
        for programma in (config.PROGRAMMA_ARMONICA, 24, 0):
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
        for programma in (19, 52, config.PROGRAMMA_ARMONICA):
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
    monkeypatch.setattr(banchi, "fluidsynth_pronto", lambda: True)
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
    monkeypatch.setattr(banchi, "fluidsynth_pronto", lambda: True)
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


def test_lo_strumento_del_banco_non_cambia_il_suono_attivo(monkeypatch, capsys):
    """Scegliere lo strumento del banco lo imposta e basta: fino alla 9.13
    passava al MIDI di Windows, che dalla 10.0.0 non c'e' piu'."""
    import gestore_impostazioni
    armonica = GBAudio.MIDI_INSTRUMENTS[config.PROGRAMMA_ARMONICA]
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(gestore_impostazioni, "menu", lambda **_k: armonica)
    monkeypatch.setattr(gestore_impostazioni, "key", lambda *_a, **_k: "")
    monkeypatch.setattr(suoni, "banco_pronto", lambda: False)
    for prima in ("banco", "suono_1"):
        monkeypatch.setattr(config, "impostazioni", {"tipo_suono": prima, "midi_strumento": 0})
        gestore_impostazioni._scegli_strumento_midi()
        assert config.impostazioni == {"tipo_suono": prima, "midi_strumento": config.PROGRAMMA_ARMONICA}
    uscita = capsys.readouterr().out
    assert "Strumento del banco impostato su: Harmonica." in uscita and "voce 5" in uscita


def test_lo_strumento_general_midi_di_uno_strumento(monkeypatch, capsys):
    """La voce g di Gestisci Strumenti: lo strumento General MIDI si sceglie
    dal nome, e nessuno lo toglie."""
    import gestore_impostazioni
    strumenti = {"Ukulele": {"tipo": "corde", "accordatura": ["G4", "C4", "E4", "A4"], "tasti": 12, "programma_gm": None},
                 "Chitarra": {"tipo": "corde", "accordatura": ["E2", "A2", "D3", "G3", "B3", "E4"], "tasti": 21, "programma_gm": 24}}
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumenti": strumenti, "strumento_attivo": "Chitarra"})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    risposte = iter(["g", "Ukulele", "Acoustic Guitar (nylon)", "g", "Chitarra", "0", None])
    viste = []

    def menu_finto(**opzioni):
        viste.append(opzioni["d"])
        return next(risposte)

    monkeypatch.setattr(gestore_impostazioni, "menu", menu_finto)
    gestore_impostazioni.GestoreStrumenti()
    assert strumenti["Ukulele"]["programma_gm"] == 24
    assert strumenti["Chitarra"]["programma_gm"] is None
    assert list(viste[2])[:2] == ["0", "Acoustic Grand Piano"] and len(viste[2]) == 129
    assert "Strumento General MIDI di Ukulele: Acoustic Guitar (nylon)." in capsys.readouterr().out


def test_uno_strumento_nuovo_riceve_lo_strumento_proposto(monkeypatch, capsys):
    import gestore_impostazioni
    monkeypatch.setattr(config, "impostazioni", {"nomenclatura": "latino", "strumenti": {}, "strumento_attivo": ""})
    monkeypatch.setattr(config, "salva_modifiche", lambda: True)
    monkeypatch.setattr(config, "aggiorna_manico", lambda: None)
    monkeypatch.setattr(gestore_impostazioni, "menu", lambda **_k: "1")
    monkeypatch.setattr(gestore_impostazioni, "_nuovo_strumento_a_corda",
                        lambda _s: ("Basso fretless", {"tipo": "corde", "accordatura": ["E1", "A1", "D2", "G2"], "tasti": 24}))
    monkeypatch.setattr(gestore_impostazioni, "dgt", lambda *_a, **_k: "n")
    gestore_impostazioni._aggiungi_strumento(config.impostazioni["strumenti"])
    assert config.impostazioni["strumenti"]["Basso fretless"]["programma_gm"] == 32
    assert "Strumento General MIDI proposto: Acoustic Bass." in capsys.readouterr().out

