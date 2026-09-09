# Chitabry, gestore impostazioni: suoni, strumenti, nomenclatura e porte MIDI.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py.
# Ogni modifica si scrive subito su disco con config.salva_modifiche.

import numpy as np
from GBUtils import dgt, key, menu

import config
import GBAudio
from nomenclatura import nome_utente_in_std


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
        print("Inserisci i valori ADSR (premi Invio per confermare il valore attuale):")
        labels_adsr = ["Attacco % (tempo)", "Decadimento % (tempo)", "Sustain Livello % (vol)", "Rilascio % (tempo)"]
        vecchio_adsr = suono['adsr']
        nuovo_adsr = [dgt(f"{labels_adsr[i]} (attuale: {vecchio_adsr[i]}): ", kind='f', fmin=0.0, fmax=100.0, default=vecchio_adsr[i]) for i in range(4)]
        somma_adr = nuovo_adsr[0] + nuovo_adsr[1] + nuovo_adsr[3]
        if somma_adr > 100.0:
            print(f"ATTENZIONE: La somma di Attacco, Decadimento e Rilascio ({somma_adr}%) supera 100%.")
            print("ADSR non modificato.")
        else:
            suono['adsr'] = nuovo_adsr
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
    return {k: f"{k} ({v.get('tasti')} tasti, {len(v.get('accordatura', []))} corde)" for k, v in strumenti.items()}


def GestoreStrumenti():
    """Scelta, aggiunta ed eliminazione degli strumenti."""
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
            print("Seleziona lo strumento attivo:")
            scelto = menu(d=_descrivi_strumenti(strumenti), keyslist=True, show=True, numbered=True, ntf="Strumento non trovato")
            if scelto is not None and scelto != strum_attivo:
                config.impostazioni['strumento_attivo'] = scelto
                config.salva_modifiche()
                config.aggiorna_manico()
                print(f"Strumento attivo impostato su: {scelto}.")
        elif scelta == 'a':
            print("Aggiungi nuovo strumento.")
            nome = dgt("Nome strumento: ", kind="s").strip()
            if not nome:
                continue
            if nome in strumenti:
                print("Esiste gia' uno strumento con questo nome.")
                continue
            num_corde = dgt("Numero di corde (es. 4 per Ukulele): ", kind="i", imin=1, imax=12)
            accordatura = _chiedi_accordatura(num_corde)
            if accordatura is None:
                continue
            tasti = dgt("Numero di tasti: ", kind="i", imin=1, imax=50)
            strumenti[nome] = {"accordatura": accordatura, "tasti": tasti}
            config.impostazioni['strumenti'] = strumenti
            ans = dgt(f"Vuoi impostare {nome} come strumento attivo? (S/N): ", kind="s")
            if ans.strip().lower() == 's':
                config.impostazioni['strumento_attivo'] = nome
            config.salva_modifiche()
            config.aggiorna_manico()
            print(f"Strumento {nome} aggiunto con successo!")
        elif scelta == 'e':
            print("Seleziona lo strumento da eliminare:")
            eliminabili = {k: v for k, v in strumenti.items() if k != strum_attivo}
            if not eliminabili:
                print("Non ci sono altri strumenti da eliminare.")
                continue
            scelto = menu(d=_descrivi_strumenti(eliminabili), keyslist=True, show=True, numbered=True, ntf="Strumento non trovato")
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
    return f"MIDI ({GBAudio.MIDI_INSTRUMENTS[config.impostazioni.get('midi_strumento', 0)]})"


def _scegli_tipo_suono():
    menu_tipi = {'1': "Sintesi Karplus-Strong", '2': "Sintesi Onda Semplice", '3': "Strumento MIDI del Banco Attivo"}
    print("Seleziona il tipo di suono attivo:")
    scelta_t = menu(d=menu_tipi, keyslist=True, show=True, show_on_filter=False, ntf="Scelta non valida")
    tipi = {'1': 'suono_1', '2': 'suono_2', '3': 'midi'}
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
        config.impostazioni['tipo_suono'] = 'midi'
        config.salva_modifiche()
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
            '4': f"Connetti Tastiera MIDI (Attivo: {midi_in_attivo if midi_in_attivo else 'Nessuno'})"
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
