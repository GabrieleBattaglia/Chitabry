# Chitabry, gestore impostazioni: suoni, strumenti, nomenclatura e porte MIDI.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.
# Ogni modifica si scrive subito su disco con config.salva_modifiche.

import os

import numpy as np
from GBUtils import dgt, enter_escape, key, menu

import armonica
import armonica_vista
import banchi
import config
import GBAudio
import suoni
from nomenclatura import get_nota, nome_da_midi, nome_utente_in_std


def ModificaSuono(suono_key):
    """Modifica i parametri di suono_1 (Karplus-Strong) o di suono_2 (onda semplice).
    I parametri fisici si chiedono su una scala da 1 a 10 e si riportano
    all'intervallo reale prima di salvarli."""
    suono = config.impostazioni[suono_key]
    print(f"Modifica {suono['descrizione']}.")
    if suono_key == 'suono_1':
        # Durezza del plettro: da 0.1 a 0.9
        attuale = round(1 + (np.clip(suono.get('pluck_hardness', 0.6), 0.1, 0.9) - 0.1) * (9.0 / 0.8))
        nuovo = dgt(f"Durezza plettro (1=morbido, 10=brillante) (attuale: {attuale}): ", kind='i', imin=1, imax=10, default=attuale)
        suono['pluck_hardness'] = 0.1 + (nuovo - 1) * (0.8 / 9.0)
        # Sustain: da 0.990 a 0.999
        attuale = round(1 + (np.clip(suono.get('damping_factor', 0.997), 0.990, 0.999) - 0.990) / 0.001)
        nuovo = dgt(f"Sustain (1=corto, 10=lungo) (attuale: {attuale}): ", kind='i', imin=1, imax=10, default=attuale)
        suono['damping_factor'] = 0.990 + (nuovo - 1) * 0.001
        # Posizione del plettro: da 0.01 al ponte a 0.5 al manico
        attuale = round(1 + (np.clip(suono.get('pick_position', 0.15), 0.01, 0.5) - 0.01) * (9.0 / 0.49))
        nuovo = dgt(f"Posizione plettro (1=ponte, 10=manico) (attuale: {attuale}): ", kind='i', imin=1, imax=10, default=attuale)
        suono['pick_position'] = 0.01 + (nuovo - 1) * (0.49 / 9.0)
        # Brillantezza: da 0.0 a 1.0
        attuale = round(1 + np.clip(suono.get('brightness', 0.4), 0.0, 1.0) * 9.0)
        nuovo = dgt(f"Brillantezza (1=scuro, 10=tagliente) (attuale: {attuale}): ", kind='i', imin=1, imax=10, default=attuale)
        suono['brightness'] = (nuovo - 1) * (1.0 / 9.0)
        suono['dur_accordi'] = dgt(f"Durata max accordi (sec) (attuale: {suono['dur_accordi']}): ", kind='f', fmin=0.1, fmax=10.0, default=suono['dur_accordi'])
    elif suono_key == 'suono_2':
        suono['kind'] = dgt(f"Onda (1=Sin, 2=Quadra, 3=Tri, 4=Saw, 5=String) (attuale: {suono['kind']}): ", kind='i', imin=1, imax=5, default=suono['kind'])
        print("Inviluppo della nota. Invio conferma il valore attuale.")
        print("I tre tempi sono in millesimi di secondo, il mantenimento e' un livello di volume.")
        vecchio_adsr = suono['adsr']
        nuovo_adsr = [
            dgt(f"Attacco, ms (attuale: {vecchio_adsr[0]}): ", kind='f', fmin=0.0, fmax=10000.0, default=vecchio_adsr[0]),
            dgt(f"Decadimento, ms (attuale: {vecchio_adsr[1]}): ", kind='f', fmin=0.0, fmax=10000.0, default=vecchio_adsr[1]),
            dgt(f"Mantenimento, % (attuale: {vecchio_adsr[2]}): ", kind='f', fmin=0.0, fmax=100.0, default=vecchio_adsr[2]),
            dgt(f"Rilascio, ms (attuale: {vecchio_adsr[3]}): ", kind='f', fmin=0.0, fmax=10000.0, default=vecchio_adsr[3]),
        ]
        suono['adsr'] = nuovo_adsr
        # I tempi non si sommano piu' a cento per forza: se sforano la durata
        # della nota, l'inviluppo si stringe da solo. Va detto, perche' chi ha
        # messo quei numeri si aspetta di sentirli.
        somma = (nuovo_adsr[0] + nuovo_adsr[1] + nuovo_adsr[3]) / 1000.0
        durata = suono.get('dur_accordi', 9.0)
        if somma > durata:
            print(f"Attacco, decadimento e rilascio fanno {somma:.1f} s,")
            print(f"piu' della durata della nota, {durata:.1f} s: su una nota")
            print("non tenuta l'inviluppo verra' stretto per starci dentro.")
    suono['volume'] = dgt(f"Volume (0.0 - 1.0) (attuale: {suono['volume']}): ", kind='f', fmin=0.0, fmax=1.0, default=suono['volume'])
    config.salva_modifiche()
    print(f"Impostazioni per {suono['descrizione']} aggiornate.")
    key("Premi un tasto per continuare...")


def _chiedi_accordatura(num_corde):
    """Chiede la nota a vuoto di ogni corda, dalla piu' grave. None se l'utente rinuncia."""
    accordatura = []
    print("Inserisci la nota vuota per ogni corda (es. E2).")
    print("La corda 1 e' la piu' sottile (quella in basso nella tablatura).")
    for i in range(num_corde, 0, -1):
        while True:
            nota = dgt(f"Nota per la corda {i} (es. corda piu' grave E2, Invio per annullare): ", kind="s").strip().upper()
            if not nota:
                return None
            if len(nota) >= 2 and nota[-1].isdigit():
                nota_std = nome_utente_in_std(nota[:-1], qualsiasi=True)
                if nota_std is not None:
                    accordatura.append(f"{nota_std}{nota[-1]}")
                    break
            print("Formato non valido. Es: E2, SOL3.")
    return accordatura


def _descrivi_strumenti(strumenti):
    """Le voci del menu degli strumenti: la chiave e' il nome, che si sceglie
    scrivendone le prime lettere, e la descrizione dice che strumento e'.
    Fino alla 9.11 il menu era numerato, e si sceglieva da un numero invece
    che dal nome (collaudo di Gabriele del 7 ottobre 2026)."""
    descrizioni = {}
    for nome, conf in strumenti.items():
        if config.e_armonica(conf):
            try:
                descrizioni[nome] = f"armonica {armonica_vista.descrivi(config.modello_armonica(conf))}"
            except ValueError:
                descrizioni[nome] = "armonica con dati da correggere"
        else:
            descrizioni[nome] = f"{conf.get('tasti')} tasti, {len(conf.get('accordatura', []))} corde"
    return descrizioni


def _scegli_strumento(strumenti):
    """Uno strumento per nome, con il menu che filtra a ogni lettera; None con Esc."""
    return menu(d=_descrivi_strumenti(strumenti), keyslist=True, show=True, show_on_filter=False, ordered=False,
                ntf="Strumento non trovato")


def _nuovo_strumento_a_corda(strumenti):
    """Nome, corde, accordatura e tasti. Restituisce la coppia (nome, voce)
    o (None, None) se l'utente rinuncia."""
    nome = dgt("Nome strumento: ", kind="s").strip()
    if not nome:
        return None, None
    if nome in strumenti:
        print("Esiste gia' uno strumento con questo nome.")
        return None, None
    num_corde = dgt("Numero di corde (es. 4 per Ukulele): ", kind="i", imin=1, imax=12)
    accordatura = _chiedi_accordatura(num_corde)
    if accordatura is None:
        return None, None
    tasti = dgt("Numero di tasti: ", kind="i", imin=1, imax=50)
    return nome, {"tipo": config.TIPO_CORDE, "accordatura": accordatura, "tasti": tasti}


def _scelta(titolo, voci):
    """Un menu di poche voci, nell'ordine in cui sono scritte; None con Esc."""
    print(titolo)
    return menu(d=voci, keyslist=True, show=True, show_on_filter=False, ordered=False, ntf="Scelta non valida")


def _nuova_armonica(strumenti):
    """Famiglia, tonalita', accordatura, e poi solo se servono i fori, le
    valvole e il registro; infine il nome, con quello suggerito che si
    accetta con Invio. Restituisce la coppia (nome, voce) o (None, None) se
    l'utente rinuncia con Esc."""
    scelta = _scelta("Famiglia dell'armonica:", {"1": "Diatonica, 10 fori",
                                                 "2": "Cromatica, con il cursore: 10, 12 o 16 fori"})
    if scelta is None:
        return None, None
    famiglia = "diatonica" if scelta == "1" else "cromatica"
    # Non quella stampata sopra: le Natural Minor e le Melody Maker portano
    # scritta la tonalita' della seconda posizione, una quinta piu' su.
    print("Tonalita' dell'armonica, cioe' la nota del foro 1 soffiato:")
    toniche = {get_nota(t): t for t in armonica.TONALITA}
    scelta = menu(d=toniche, keyslist=True, show=True, pager=12, ordered=False, ntf="Tonalita' non valida")
    if scelta is None:
        return None, None
    tonalita = toniche[scelta]
    chiavi = armonica.accordature_per_famiglia(famiglia)
    scelta = _scelta("Accordatura:", {str(i): f"{armonica.ACCORDATURE[k].nome}, {armonica.ACCORDATURE[k].descrizione}"
                                      for i, k in enumerate(chiavi, start=1)})
    if scelta is None:
        return None, None
    accordatura = chiavi[int(scelta) - 1]
    acc = armonica.ACCORDATURE[accordatura]
    fori = acc.fori[0]
    if len(acc.fori) > 1:
        scelta = _scelta("Quanti fori:", {str(f): f"{f} fori" for f in acc.fori})
        if scelta is None:
            return None, None
        fori = int(scelta)
    voce = {"tipo": config.TIPO_ARMONICA, "famiglia": famiglia, "tonalita": tonalita, "accordatura": accordatura, "fori": fori}
    if famiglia == "cromatica":
        # La scelta che l'accordatura ha di solito viene per prima
        con = "Con le valvole, come le Hohner 270: le ance non si piegano"
        senza = "Senza valvole, come la Trochilus o una bebop: si piega come una diatonica, anche con il cursore"
        ordine = [(True, con), (False, senza)] if acc.valvole else [(False, senza), (True, con)]
        scelta = _scelta("Valvole:", {str(i): testo for i, (_, testo) in enumerate(ordine, start=1)})
        if scelta is None:
            return None, None
        voce["valvole"] = ordine[int(scelta) - 1][0]
    normale = armonica.midi_foro_1(tonalita, famiglia, fori)
    scelta = _scelta("Registro:", {"1": f"Normale, il foro 1 soffiato e' {nome_da_midi(normale)}",
                                   "2": f"Basso, quello delle armoniche Low: il foro 1 soffiato e' {nome_da_midi(normale - 12)}"})
    if scelta is None:
        return None, None
    voce["registro"] = "normale" if scelta == "1" else "basso"
    suggerito = f"Armonica {famiglia} {get_nota(tonalita)}"
    if voce["registro"] == "basso":
        suggerito += " basso"
    suggerito += f" {acc.nome}"
    if famiglia == "cromatica":
        suggerito += f" {fori} fori"
        if voce["valvole"] != acc.valvole:
            suggerito += " con le valvole" if voce["valvole"] else " senza valvole"
    nome = dgt(f"Nome strumento (Invio per {suggerito}): ", kind="s", default=suggerito).strip()
    if not nome:
        return None, None
    if nome in strumenti:
        print("Esiste gia' uno strumento con questo nome.")
        return None, None
    return nome, voce


def _aggiungi_strumento(strumenti):
    """Prima la categoria, poi le domande di quella categoria."""
    print("Aggiungi nuovo strumento. Di che tipo?")
    categoria = menu(d={"1": "Strumento a corda (chitarra, basso, ukulele...)", "2": "Armonica a bocca"},
                     keyslist=True, show=True, show_on_filter=False, ordered=False, ntf="Scelta non valida")
    if categoria is None:
        return
    if categoria == "1":
        nome, voce = _nuovo_strumento_a_corda(strumenti)
    else:
        nome, voce = _nuova_armonica(strumenti)
    if voce is None:
        return
    strumenti[nome] = voce
    config.impostazioni['strumenti'] = strumenti
    ans = dgt(f"Vuoi impostare {nome} come strumento attivo? (S/N): ", kind="s")
    if ans.strip().lower() == 's':
        config.impostazioni['strumento_attivo'] = nome
    config.salva_modifiche()
    config.aggiorna_manico()
    print(f"Strumento {nome} aggiunto con successo!")


def GestoreStrumenti():
    """Scelta, aggiunta ed eliminazione degli strumenti, a corda e armoniche."""
    print("Gestore strumenti.")
    while True:
        strumenti = config.impostazioni.get('strumenti', {})
        strum_attivo = config.impostazioni.get('strumento_attivo')
        menu_strum = {
            's': f"Seleziona strumento attivo (Attuale: {strum_attivo})",
            'a': "Aggiungi nuovo strumento",
            'e': "Elimina strumento"
        }
        scelta = menu(d=menu_strum, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
        if scelta is None:
            break
        if scelta == 's':
            # Con una voce sola il menu la sceglie senza leggere tasti: le
            # lettere scritte seguendo l'invito finirebbero nel menu dopo
            if len(strumenti) == 1:
                print(f"C'e' un solo strumento, {next(iter(strumenti))}, ed e' gia' quello attivo.")
                continue
            print("Seleziona lo strumento attivo, scrivendo le prime lettere del nome:")
            scelto = _scegli_strumento(strumenti)
            if scelto is not None and scelto == strum_attivo:
                print(f"{scelto} e' gia' lo strumento attivo.")
            elif scelto is not None:
                config.impostazioni['strumento_attivo'] = scelto
                config.salva_modifiche()
                config.aggiorna_manico()
                print(f"Strumento attivo impostato su: {scelto}.")
        elif scelta == 'a':
            _aggiungi_strumento(strumenti)
        elif scelta == 'e':
            eliminabili = {k: v for k, v in strumenti.items() if k != strum_attivo}
            if not eliminabili:
                print("Non ci sono altri strumenti da eliminare.")
                continue
            if len(eliminabili) == 1:
                scelto = next(iter(eliminabili))
            else:
                print("Seleziona lo strumento da eliminare, scrivendo le prime lettere del nome:")
                scelto = _scegli_strumento(eliminabili)
            if scelto is not None:
                conferma = dgt(f"Sei sicuro di voler eliminare {scelto}? (S/N): ", kind="s")
                if conferma.strip().lower() == 's':
                    del strumenti[scelto]
                    config.impostazioni['strumenti'] = strumenti
                    config.salva_modifiche()
                    print(f"Strumento {scelto} eliminato.")


def _descrizione_tipo_suono():
    tipo_suono = config.impostazioni.get('tipo_suono', 'suono_1')
    if tipo_suono == 'suono_1':
        return "Sintesi Karplus-Strong"
    if tipo_suono == 'suono_2':
        return "Sintesi Onda Semplice"
    if tipo_suono == 'banco':
        return suoni.descrizione_suono('banco')
    return f"MIDI ({GBAudio.MIDI_INSTRUMENTS[config.impostazioni.get('midi_strumento', 0)]})"


def _scegli_tipo_suono():
    menu_tipi = {'1': "Sintesi Karplus-Strong", '2': "Sintesi Onda Semplice", '3': "Strumento MIDI di Windows",
                 '4': "Banco di suoni, un soundfont suonato da FluidSynth"}
    print("Seleziona il tipo di suono attivo:")
    scelta_t = menu(d=menu_tipi, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
    tipi = {'1': 'suono_1', '2': 'suono_2', '3': 'midi', '4': 'banco'}
    if scelta_t == '4' and not suoni.banco_pronto():
        # Il banco non e' ancora pronto: lo si prepara, e alla fine si chiede
        # se usarlo come suono attivo
        _configura_banco()
        return
    if scelta_t in tipi:
        config.impostazioni['tipo_suono'] = tipi[scelta_t]
        config.salva_modifiche()
        print(f"Tipo suono attivo impostato su: {menu_tipi[scelta_t]}.")
    key("Premi un tasto...")


def _scegli_strumento_midi():
    midi_dict = {name: name for name in GBAudio.MIDI_INSTRUMENTS}
    print("Seleziona uno strumento MIDI iniziando a digitare il nome per filtrare:")
    scelto = menu(d=midi_dict, keyslist=True, show=True, show_on_filter=False, ntf="Strumento non valido")
    if scelto is not None:
        program = GBAudio.MIDI_INSTRUMENTS.index(scelto)
        config.impostazioni['midi_strumento'] = program
        # Il banco suona con lo stesso strumento: se e' il suono attivo resta,
        # invece di lasciare il posto al MIDI di Windows
        banco_attivo = config.impostazioni.get('tipo_suono') == 'banco'
        if not banco_attivo:
            config.impostazioni['tipo_suono'] = 'midi'
        config.salva_modifiche()
        if banco_attivo:
            print(f"Strumento impostato su: {scelto}. Il suono attivo resta il banco.")
        else:
            print(f"Strumento MIDI impostato su: {scelto} e attivato.")
        GBAudio.get_midi_out().select_instrument(program)
    key("Premi un tasto...")


def _scegli_tastiera_midi():
    dispositivi = GBAudio.get_midi_in_devices()
    if not dispositivi:
        print("Nessun dispositivo MIDI di input rilevato nel sistema.")
        key("Premi un tasto...")
        return
    midi_in_menu = {"0": "Disconnetti / Nessuno"}
    for idx, name in enumerate(dispositivi):
        midi_in_menu[str(idx + 1)] = name
    print("Seleziona una tastiera MIDI da connettere:")
    scelta_kbd = menu(d=midi_in_menu, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
    if scelta_kbd == "0":
        config.impostazioni['midi_in_dispositivo'] = ""
        config.salva_modifiche()
        GBAudio.close_global_midi_in()
        print("Tastiera MIDI disconnessa.")
    elif scelta_kbd is not None:
        idx_sel = int(scelta_kbd) - 1
        nome_sel = dispositivi[idx_sel]
        config.impostazioni['midi_in_dispositivo'] = nome_sel
        config.salva_modifiche()
        GBAudio.open_global_midi_in(idx_sel)
        print(f"Tastiera MIDI connessa ed attivata: {nome_sel}")
    key("Premi un tasto...")


def _riga(testo):
    """Una riga che si riscrive, fra due ritorni carrello, per l'avanzamento."""
    print(f"\r{testo}\r", end="", flush=True)


def _scarica_con_avanzamento(funzione, cosa):
    """Scarica con una riga che dice i megabyte arrivati. Restituisce cio' che
    la funzione restituisce, True se niente, o None se lo scaricamento fallisce."""
    def avanza(scaricati, totale):
        if totale:
            _riga(f"{cosa}: {scaricati / 1_000_000:.0f} di {totale / 1_000_000:.0f} MB")
        else:
            _riga(f"{cosa}: {scaricati / 1_000_000:.0f} MB")
    try:
        risultato = funzione(avanza)
    except (OSError, ValueError) as e:
        print(f"\nScaricamento di {cosa} non riuscito: {e}")
        return None
    print()
    return True if risultato is None else risultato


def _configura_banco():
    """Il banco di suoni: FluidSynth, se manca, la ricerca dei banchi General
    MIDI sui dischi, la scelta, il volume. Il codice che cerca e scarica viene
    da MeTeOra, che fa la stessa cosa per i suoi MIDI."""
    print("Banco di suoni. Chitabry suona un banco General MIDI, cioe' un file sf2, con FluidSynth: e' un quarto suono, "
          "accanto ai due sintetici e al MIDI di Windows, e lo scegli fra i banchi che hai sul computer.")
    presente = banchi.fluidsynth_pronto()
    if not presente:
        # Una copia salvata che non si carica piu' si dimentica: altrimenti
        # varrebbe anche dopo uno scaricamento riuscito
        banco_salvato = config.impostazioni.get('banco')
        if isinstance(banco_salvato, dict) and banco_salvato.pop('fluidsynth', None):
            config.salva_modifiche()
    # La ricerca sui dischi trova i banchi e, nello stesso giro, le copie di
    # FluidSynth gia' sul computer: si scarica solo se non ce n'e' nessuna
    domanda = ("Cerco i banchi General MIDI su tutti i dischi fissi?" if presente else
               "Cerco su tutti i dischi fissi i banchi General MIDI e una copia di FluidSynth gia' presente, per esempio quella di MeTeOra?")
    voci = {}
    motori = []
    interrotta = []
    attuale = config.impostazioni.get('banco', {}).get('percorso', '')

    def fermo():
        # Si ricorda che la ricerca e' stata fermata: senza, Chitabry diceva
        # che FluidSynth non c'era sul computer anche se non l'aveva cercato
        # dappertutto
        if not interrotta and key(attesa=0) == chr(27):
            interrotta.append(True)
        return bool(interrotta)

    cercato = enter_escape(f"\r{domanda} Puo' durare qualche minuto, e ESC la ferma. (INVIO per si', ESC per no): \r")
    if cercato:
        trovati = banchi.cerca_banchi(avvisa=lambda n: _riga(f"Cartelle visitate: {n}"), fermo=fermo, motori=motori)
        print()
        if interrotta:
            print("Ricerca fermata con ESC.")
        print(f"Banchi General MIDI trovati: {len(trovati)}.")
        for percorso, dimensione in trovati:
            voci[percorso] = f"{os.path.basename(percorso)}, {banchi.dimensione_da_leggere(dimensione)}, in {os.path.dirname(percorso)}"
    if not presente:
        cartella = banchi.fluidsynth_che_funziona(motori)
        if cartella is not None:
            config.impostazioni.setdefault('banco', {})['fluidsynth'] = cartella
            config.salva_modifiche()
            print(f"FluidSynth trovato in {cartella}: Chitabry usa quello, senza scaricarne un altro.")
        else:
            # La frase dice cio' che e' successo davvero, prima di proporre
            # lo scaricamento
            if motori:
                perche = f"Nessuna delle copie di FluidSynth trovate, {len(motori)}, si puo' usare."
            elif interrotta:
                perche = "La ricerca e' stata fermata prima di trovare FluidSynth."
            elif cercato:
                perche = "FluidSynth non c'e' sul computer."
            else:
                perche = "FluidSynth non c'e' nella cartella di Chitabry."
            if not enter_escape(f"\r{perche} Lo scarico da GitHub, dalla pagina ufficiale? (INVIO per si', ESC per no): \r"):
                return
            if _scarica_con_avanzamento(banchi.scarica_fluidsynth, "FluidSynth") is None:
                key("Premi un tasto...")
                return
            print("FluidSynth scaricato.")
    if attuale and attuale not in voci and os.path.isfile(attuale):
        voci = {attuale: f"{os.path.basename(attuale)}, quello attuale", **voci}
    dimensione = banchi.dimensione_da_leggere(banchi.FLUIDR3_DIMENSIONE)
    if not voci:
        # Con una voce sola il menu la sceglie senza chiedere: 148 MB si
        # scaricano solo con un si'
        if not enter_escape(f"\rNessun banco da scegliere. Scarico FluidR3 GM, il banco libero di FluidSynth, {dimensione}? (INVIO per si', ESC per no): \r"):
            return
        scelta = "scarica"
    else:
        voci["scarica"] = f"Scarica FluidR3 GM, il banco libero di FluidSynth, {dimensione}"
        print("Scegli il banco di suoni:")
        scelta = menu(d=voci, keyslist=True, show=True, numbered=True, ordered=False, ntf="Scelta non valida", p="Banco: ")
    if scelta is None:
        return
    if scelta == "scarica":
        percorso = _scarica_con_avanzamento(banchi.scarica_fluidr3, "FluidR3 GM")
        if percorso is None:
            key("Premi un tasto...")
            return
    else:
        percorso = scelta
    banco = config.impostazioni.setdefault('banco', {})
    banco['percorso'] = percorso
    banco['volume'] = dgt(f"Volume del banco (0.0 - 1.0) (attuale: {banco.get('volume', 0.8)}): ", kind='f', fmin=0.0, fmax=1.0,
                          default=banco.get('volume', 0.8))
    banchi.chiudi()
    if dgt("Vuoi usarlo come suono attivo? (S/N): ", kind="s").strip().lower() == 's':
        config.impostazioni['tipo_suono'] = 'banco'
    config.salva_modifiche()
    print(f"Banco di suoni: {os.path.basename(percorso)}. Lo strumento e' quello scelto per il MIDI, e l'armonica suona con Harmonica.")
    key("Premi un tasto...")


def _scegli_volume_midi():
    """Il volume delle note MIDI, strumenti e armonica, in percentuale. Il
    click del metronomo non c'entra: il suo volume e' quello del preset."""
    attuale = config.impostazioni.get('midi_volume', 100)
    nuovo = dgt(f"Volume MIDI, da 0 a 100 (attuale: {attuale}): ", kind='i', imin=0, imax=100, default=attuale)
    config.impostazioni['midi_volume'] = nuovo
    config.salva_modifiche()
    suoni.applica_volume_midi()
    print(f"Volume MIDI impostato a {nuovo}%.")
    key("Premi un tasto...")


def GestoreImpostazioni():
    """Il menu delle impostazioni dell'applicazione."""
    print("Gestore impostazioni.")
    while True:
        midi_in_attivo = config.impostazioni.get('midi_in_dispositivo', '')
        menu_impostazioni = {
            's': f"Gestisci Strumenti (Attivo: {config.impostazioni.get('strumento_attivo')})",
            'n': f"Cambia nomenclatura (attuale: {config.impostazioni['nomenclatura']})",
            't': f"Cambia Tipo Suono Attivo (attuale: {_descrizione_tipo_suono()})",
            '1': f"Modifica {config.impostazioni['suono_1']['descrizione']}",
            '2': f"Modifica {config.impostazioni['suono_2']['descrizione']}",
            '3': f"Seleziona Strumento MIDI (Attivo: {GBAudio.MIDI_INSTRUMENTS[config.impostazioni.get('midi_strumento', 0)]})",
            '4': f"Connetti Tastiera MIDI (Attivo: {midi_in_attivo if midi_in_attivo else 'Nessuno'})",
            '5': f"Volume MIDI (attuale: {config.impostazioni.get('midi_volume', 100)}%)",
            '6': f"Banco di suoni (attuale: {os.path.basename(config.impostazioni.get('banco', {}).get('percorso', '')) or 'nessuno'})",
        }
        scelta = menu(d=menu_impostazioni, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
        if scelta is None:
            print("Ritorno al menu principale.")
            break
        if scelta == 's':
            GestoreStrumenti()
        elif scelta == 'n':
            if config.impostazioni['nomenclatura'] == 'latino':
                config.impostazioni['nomenclatura'] = 'anglosassone'
            else:
                config.impostazioni['nomenclatura'] = 'latino'
            config.salva_modifiche()
            print(f"Nomenclatura impostata su: {config.impostazioni['nomenclatura']}")
            key("Premi un tasto...")
        elif scelta == 't':
            _scegli_tipo_suono()
        elif scelta == '1':
            ModificaSuono('suono_1')
        elif scelta == '2':
            ModificaSuono('suono_2')
        elif scelta == '3':
            _scegli_strumento_midi()
        elif scelta == '4':
            _scegli_tastiera_midi()
        elif scelta == '5':
            _scegli_volume_midi()
        elif scelta == '6':
            _configura_banco()
