# Chitabry, prove della nota tenuta: il tratto che si ripete e il rilascio.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5, modalita' auto).
# Nate con la issue 55, il 14 settembre 2026. Non aprono nessun dispositivo e
# non emettono nessun suono: la callback del mixer viene chiamata a mano, un
# blocco alla volta, e si guarda cosa esce.

import numpy as np

import GBAudio

FRAMES = 1024
# Attacco, decadimento e rilascio in millesimi di secondo, il mantenimento in
# percentuale di volume: e' il formato 2 delle impostazioni. Questo e' il
# preset di fabbrica, che tiene.
ADSR_TENUTO = [10.0, 60.0, 70.0, 120.0]
# Un inviluppo che sale e scende fino al silenzio, cioe' che non tiene niente:
# e' il pizzicato, e con il mantenimento a zero non c'e' niente da ripetere.
ADSR_PIZZICATO = [1.0, 900.0, 0.0, 0.0]


def renderer_osc(adsr, freq=220.0, dur=2.0, vol=0.5):
    r = GBAudio.NoteRenderer(fs=GBAudio.FS)
    r.set_params(freq, dur, vol, 0.0, kind=1, adsr_list=adsr)
    return r


def renderer_corda(freq=220.0, dur=2.0, vol=0.5):
    r = GBAudio.NoteRenderer(fs=GBAudio.FS)
    r.set_params(freq, dur, vol, 0.0, pluck_hardness=0.5, damping_factor=0.996,
                 pick_position=0.15, brightness=0.4)
    return r


def blocco(player, frames=FRAMES):
    """Un giro di callback, come lo farebbe il dispositivo audio."""
    fuori = np.zeros((frames, 2), dtype=np.float32)
    player._audio_callback(fuori, frames, None, None)
    return fuori


def test_corda_pizzicata_non_ha_niente_da_ripetere():
    # Ripetere un tratto del decadimento vorrebbe dire risentire sempre lo
    # stesso pezzo di spegnimento: la corda tenuta non esiste.
    mono, ciclo = renderer_corda().render_tenuta()
    assert ciclo is None
    assert mono.size > 0


def test_inviluppo_senza_mantenimento_non_ha_niente_da_ripetere():
    mono, ciclo = renderer_osc(ADSR_PIZZICATO).render_tenuta()
    assert ciclo is None
    assert mono.size > 0


def test_inviluppo_che_tiene_da_un_tratto_da_ripetere():
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    assert ciclo is not None
    inizio, fine = ciclo
    assert 0 < inizio < fine <= mono.size
    # Il tratto e' lungo un numero intero di periodi, a meno dell'arrotondamento
    # al campione.
    periodo = GBAudio.FS / 220.0
    giri = (fine - inizio) / periodo
    assert abs(giri - round(giri)) < 0.01


def test_il_tratto_ripetuto_sta_al_livello_di_mantenimento():
    volume = 0.5
    mono, ciclo = renderer_osc(ADSR_TENUTO, vol=volume).render_tenuta()
    inizio, fine = ciclo
    atteso = volume * ADSR_TENUTO[2] / 100.0
    # Il massimo del tratto e' il livello di mantenimento, perche' l'onda ci
    # passa sopra a ogni periodo.
    assert abs(np.max(np.abs(mono[inizio:fine])) - atteso) < 0.02


def test_la_giunzione_del_ciclo_non_fa_scatti():
    # E' la misura del click: il salto fra l'ultimo campione del tratto e il
    # primo non deve essere piu' grande dei salti che il suono fa da solo.
    mono, ciclo = renderer_osc(ADSR_TENUTO, freq=1760.0).render_tenuta()
    inizio, fine = ciclo
    dentro = mono[inizio:fine]
    passo_tipico = np.max(np.abs(np.diff(dentro)))
    salto = abs(float(mono[inizio]) - float(mono[fine - 1]))
    assert salto <= passo_tipico * 1.5, f"salto {salto}, passo tipico {passo_tipico}"


def test_il_raccordo_non_tocca_l_ingresso_nel_ciclo():
    # La prima volta si entra nel tratto venendo dal decadimento: quel passaggio
    # deve restare intatto, altrimenti lo scatto si sposta li'.
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    inizio = ciclo[0]
    salto = abs(float(mono[inizio]) - float(mono[inizio - 1]))
    passo_tipico = np.max(np.abs(np.diff(mono[inizio:ciclo[1]])))
    assert salto <= passo_tipico * 1.5


def test_una_nota_tenuta_non_finisce():
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=2)
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    player.tieni(0, mono, ciclo)
    # Molto piu' lunga del buffer: senza il ciclo, qui ci sarebbe silenzio.
    quanti_blocchi = int(mono.size / FRAMES) + 20
    ultimo = blocco(player)
    for _giro in range(quanti_blocchi):
        ultimo = blocco(player)
    assert np.max(np.abs(ultimo)) > 0.01
    assert player.sta_suonando(0)


def test_lasciare_spegne_in_una_rampa():
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=2)
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    player.tieni(0, mono, ciclo)
    for _giro in range(5):
        blocco(player)
    prima = np.max(np.abs(blocco(player)))
    player.lascia(0, secondi=0.06)
    # Sessanta millesimi sono poco meno di tre blocchi da 1024 a 44100.
    picchi = [np.max(np.abs(blocco(player))) for _giro in range(4)]
    assert picchi[0] < prima
    assert picchi == sorted(picchi, reverse=True), picchi
    assert picchi[-1] == 0.0
    assert not player.sta_suonando(0)


def test_la_rampa_non_riparte_a_ogni_blocco():
    # Senza la memoria di quanti campioni sono gia' passati, ogni blocco
    # ripartirebbe da guadagno uno e la nota non si spegnerebbe mai.
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=1)
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    player.tieni(0, mono, ciclo)
    blocco(player)
    player.lascia(0, secondi=0.2)
    # Duecento millesimi sono 8820 campioni, cioe' otto blocchi e mezzo: il
    # decimo blocco cade tutto dopo la fine della rampa.
    massimi = [np.max(np.abs(blocco(player))) for _giro in range(10)]
    assert massimi[0] > massimi[4] > massimi[7]
    assert massimi[-1] == 0.0


def test_lasciare_una_corda_la_smorza_prima_del_suo_tempo():
    # La corda non ha un tratto da ripetere, ma lasciare il tasto deve zittirla
    # lo stesso: e' la mano appoggiata sulle corde.
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=1)
    mono, ciclo = renderer_corda(dur=6.0).render_tenuta()
    assert ciclo is None
    player.tieni(0, mono, ciclo)
    blocco(player)
    player.lascia(0, secondi=0.06)
    for _giro in range(4):
        ultimo = blocco(player)
    assert np.max(np.abs(ultimo)) == 0.0
    assert not player.sta_suonando(0)


def test_lasciare_due_volte_non_accelera_il_rilascio():
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=1)
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    player.tieni(0, mono, ciclo)
    blocco(player)
    player.lascia(0, secondi=0.2)
    player.lascia(0, secondi=0.01)
    picchi = [np.max(np.abs(blocco(player))) for _giro in range(3)]
    # Con la seconda richiesta presa sul serio, qui sarebbe gia' tutto zero.
    assert picchi[-1] > 0.0


def test_pluck_resta_quello_di_prima():
    # Le sei corde, gli accordi e le scale continuano a passare di qui: una
    # nota one-shot che finisce quando finisce il buffer.
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=1)
    mono = np.ones(FRAMES * 2, dtype=np.float32) * 0.5
    player.pluck(0, mono)
    assert np.max(np.abs(blocco(player))) > 0.0
    blocco(player)
    assert np.max(np.abs(blocco(player))) == 0.0
    assert not player.sta_suonando(0)


def test_una_nota_nuova_cancella_il_rilascio_in_corso():
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=1)
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    player.tieni(0, mono, ciclo)
    blocco(player)
    player.lascia(0, secondi=1.0)
    blocco(player)
    player.tieni(0, mono, ciclo)
    picchi = [np.max(np.abs(blocco(player))) for _giro in range(3)]
    assert min(picchi) > 0.01, picchi


def test_mute_azzera_anche_cicli_e_rilasci():
    player = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=2)
    mono, ciclo = renderer_osc(ADSR_TENUTO).render_tenuta()
    player.tieni(0, mono, ciclo)
    player.tieni(1, mono, ciclo)
    player.lascia(1)
    player.mute()
    assert np.max(np.abs(blocco(player))) == 0.0
    assert player.cicli == [None, None]
    assert player.rilasci == [None, None]


def test_render_e_render_tenuta_dicono_la_stessa_nota():
    # Chi non tiene niente deve sentire esattamente quello che sentiva prima.
    r = renderer_osc(ADSR_PIZZICATO)
    stereo = r.render()
    mono, ciclo = r.render_tenuta()
    assert ciclo is None
    assert stereo.shape[0] == mono.size
    atteso = stereo[:, 0] / r.pan_l
    assert np.allclose(atteso, mono, atol=1e-5)
