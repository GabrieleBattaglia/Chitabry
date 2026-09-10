# Chitabry, esercizio scale: scelta della scala dal catalogo, note sul manico, diteggiature e ascolto a tempo.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py:
# la funzione unica di 665 righe e' divisa nelle sue fasi, e l'ascolto a
# tempo, che era scritto due volte, una per il loop e una per il comando
# singolo, sta in un posto solo. Dal collaudo del 2026-09-10: i battiti su
# una griglia di scadenze assolute, le note sintetizzate in anticipo durante
# il battito precedente, e il click in MIDI quando il suono e' MIDI, perche'
# passando da due sintetizzatori diversi nota e battito arrivavano in tempi
# diversi.

from time import monotonic as orologio

import numpy as np
from GBUtils import dgt, enter_escape, key, menu
from music21 import pitch, scale
from music21.exceptions21 import Music21Exception

import clitronomo
import config
import GBAudio
import scale_catalog
import suoni
from generatore_scale import ScalePathfinder
from manico import Manlimiti, visualizza_note_su_manico
from nomenclatura import get_nota, mappa_toniche
from ricerca import fuzzy_search_and_select
from strumento import InstrumentModel

MENU_ESERCIZIO = {
    "1-9 e 0": "Suona la nota singola",
    "a": "Ascolta ascendente",
    "d": "Ascolta discendente",
    "l": "Attiva o disattiva il loop",
    "b": "Imposta i BPM",
    "m": "Attiva o disattiva il metronomo",
}
# Con quanta frequenza si ascolta la tastiera durante un passo, in secondi
PASSO_ASCOLTO = 0.02
# Con il suono MIDI il click e' un wood block General MIDI su un canale suo:
# due altezze vicine ai beep di fabbrica, forte l'accento e piu' piano il battito.
NOTA_ACCENTO = 81   # La5, 880 Hz, accanto ai 915 Hz dell'accento di fabbrica
NOTA_TICK = 72      # Do5, 523 Hz, accanto ai 550 Hz del battito di fabbrica
VELOCITA_ACCENTO = 127
VELOCITA_TICK = 90
DURATA_CLICK_MIDI = 0.1   # secondi prima del note off: il wood block e' un colpo secco
# Il note off di una nota MIDI arriva un po' prima del battito seguente: se
# due battiti hanno la stessa nota, altrimenti spegnerebbe quella appena partita.
ANTICIPO_NOTE_OFF = 0.03
DURATA_MINIMA_NOTA_MIDI = 0.05


class Scala:
    """Una scala pronta per l'esercizio: nome, note per il manico, note da
    mostrare in salita e in discesa, frequenze da suonare."""
    def __init__(self, tonica_std, nome_base, scala_m21):
        self.tonica_std = tonica_std
        self.nome = f"{get_nota(tonica_std)} {nome_base}"
        self.scala_m21 = scala_m21
        self.microtonale = False
        self.note_manico = []   # nomi standard senza ottava, senza doppioni
        self.note_asc = []      # nomi da mostrare in salita, senza doppioni
        self.note_desc = []     # nomi da mostrare in discesa, senza doppioni
        self.frequenze = []     # una per nota in salita, doppioni compresi
        if isinstance(scala_m21, (scale.ScalaScale, scale.ConcreteScale)):
            pitches_asc = list(scala_m21.pitches)
        else:
            print("Attenzione: tipo di scala non riconosciuto per l'estrazione delle note.")
            pitches_asc = []
        for p in pitches_asc:
            nota_manico, nota_display, freq = self._analizza(p)
            if nota_manico and nota_manico not in self.note_manico:
                self.note_manico.append(nota_manico)
            if nota_display not in self.note_asc:
                self.note_asc.append(nota_display)
            self.frequenze.append(freq)
        for p in reversed(pitches_asc):
            _, nota_display, _ = self._analizza(p)
            if nota_display not in self.note_desc:
                self.note_desc.append(nota_display)

    def _analizza(self, p):
        """Da un pitch di music21 alla terna (nome per il manico, nome da mostrare, frequenza)."""
        if not isinstance(p, pitch.Pitch):
            return None, str(p), None
        frequenza = p.frequency
        nota_display = get_nota(p.nameWithOctave.replace('-', 'b'))
        micro = p.accidental is not None and hasattr(p.accidental, 'alter') and p.accidental.alter not in (0.0, 1.0, -1.0, 2.0, -2.0)
        if micro:
            self.microtonale = True
        p_standard = pitch.Pitch(p.step + str(p.octave if p.octave is not None else 4))
        if p.accidental and p.accidental.name in ('sharp', 'flat', 'double-sharp', 'double-flat'):
            p_standard.accidental = p.accidental
        nota_manico = ''.join(c for c in p_standard.name.replace('-', 'b') if not c.isdigit())
        if frequenza is None and micro:
            print(f"Attenzione: impossibile calcolare la frequenza per {p.nameWithOctave}")
        return nota_manico, nota_display, frequenza

    def testo_note(self, direzione):
        note = self.note_asc if direzione == 'a' else self.note_desc
        return " ".join(note)

    def stampa_riepilogo(self):
        asc = self.testo_note('a')
        desc = self.testo_note('d')
        print(f"Scala: {self.nome}")
        print(f"Note (Asc): {asc if asc else '(Nessuna nota trovata)'}")
        if self.microtonale:
            print("INFO: scala microtonale rilevata. L'audio usera' le frequenze esatte, se calcolabili.")
        if desc and asc != desc:
            print(f"Note (Desc): {desc}")


def _scegli_scala():
    """Tonica e tipo dal catalogo. Restituisce la coppia (tonica standard, chiave paradigma:id) o None."""
    toniche = mappa_toniche()
    scelta = menu(d=toniche, keyslist=True, show=True, pager=12, ntf="Nota non valida", p="Scegli la TONICA della scala: ")
    if scelta is None:
        return None
    tonica_std = toniche[scelta]
    selected_key = menu(d=scale_catalog.SCALE_TYPES_DICT, keyslist=True, show=False, pager=20, ntf="Tipo non valido",
                        p=f"Filtra TIPO scala per {get_nota(tonica_std)} (o '...'): ")
    if selected_key is None:
        return None
    if selected_key == "...":
        selected_key = fuzzy_search_and_select(scale_catalog.SCALE_TYPES_DICT,
                                               f"Cerca TIPO scala per {get_nota(tonica_std)} (testo parziale): ",
                                               "tipo di scala")
        if selected_key is None or selected_key == "...":
            print("Annullato.")
            return None
    return tonica_std, selected_key


def _costruisci_scala(tonica_std, selected_key):
    """La scala di music21 per la chiave scelta, con tonica alla quarta ottava.
    Solleva ValueError se la chiave e' malformata, ScaleException o
    Music21Exception se music21 non la istanzia."""
    try:
        paradigm, scale_id = selected_key.split(':', 1)
    except ValueError:
        raise ValueError(f"chiave di selezione '{selected_key}' malformata") from None
    nome_base = scale_catalog.SCALE_TYPES_DICT.get(selected_key, scale_id)
    scala_m21 = scale_catalog.get_scale_from_usi(f"{paradigm}:{tonica_std}4:{scale_id}")
    return Scala(tonica_std, nome_base, scala_m21)


def _mostra_diteggiature(s, maninf, mansup):
    """Le migliori diteggiature della scala nel box indicato, con il pathfinder.
    Restituisce False se il calcolo e' fallito e va mostrato il manico piatto."""
    print(f"Calcolo delle migliori diteggiature nel box {maninf}-{mansup} in corso...")
    try:
        strum_attivo = config.impostazioni.get("strumento_attivo", config.STRUMENTO_PREDEFINITO)
        dati_strum = config.impostazioni.get("strumenti", {}).get(strum_attivo, {})
        accordatura = dati_strum.get("accordatura", config.ACCORDATURA_CHITARRA)
        num_tasti = int(dati_strum.get("tasti", config.TASTI_PREDEFINITI))
        model = InstrumentModel(tuning_midi=[pitch.Pitch(n).midi for n in accordatura], num_frets=num_tasti)
        if isinstance(s.scala_m21, (scale.ScalaScale, scale.ConcreteScale)):
            target_pc = [p.pitchClass for p in s.scala_m21.pitches if isinstance(p, pitch.Pitch)]
        else:
            target_pc = [pitch.Pitch(n).pitchClass for n in s.note_manico]
        root_pc = pitch.Pitch(s.tonica_std + "4").pitchClass
        solver = ScalePathfinder(model, target_pc, root_pc)
        priorita_caged = enter_escape("Desideri dare priorita' alla forma CAGED? (INVIO per si', ESC per forme a 3 note per corda): ")
        sols = solver.find_paths(maninf, mansup, priorita_caged=priorita_caged)
    except (Music21Exception, ValueError, KeyError, RecursionError) as e:
        print(f"Errore durante il calcolo delle diteggiature: {e}")
        return False
    if not sols:
        print("Nessuna diteggiatura fisicamente possibile trovata per questa scala nel box specificato.")
        return True
    top_n = min(5, len(sols))
    print(f"Le {top_n} migliori diteggiature per {s.nome}:")
    voci = {}
    dettagli_map = {}
    for i in range(top_n):
        meta = sols[i]['meta']
        path = sols[i]['path']
        nps = ", ".join(str(meta['nps'][idx]) for idx in range(model.num_strings))
        chiave = str(i + 1)
        voci[chiave] = f"Difficolta' {meta['difficolta_score_perc']}%, stretch {meta['difficolta_stretch_perc']}%, note per corda {nps}"
        dettagli = f"Difficolta' generale: {meta['difficolta_score_perc']}%. Estensione: {meta['difficolta_stretch_perc']}% ({meta['stretch_tasti']} tasti).\n"
        per_corda = {idx: {'f': [], 'd': [], 'n': []} for idx in range(model.num_strings)}
        for idx_path, p_dict in enumerate(path):
            dito = meta['fingering'][idx_path] if meta['fingering'] else 0
            nome_nota = get_nota(pitch.Pitch(midi=p_dict['midi']).nameWithOctave.replace('-', 'b'))
            per_corda[p_dict['string']]['f'].append(str(p_dict['fret']))
            per_corda[p_dict['string']]['d'].append(str(dito))
            per_corda[p_dict['string']]['n'].append(nome_nota)
        dettagli += "Posizioni (dalla corda piu' grave):\n"
        for idx in range(model.num_strings):
            if per_corda[idx]['f']:
                corda_num = model.num_strings - idx
                dettagli += (f"Corda {corda_num}: tasti ({', '.join(per_corda[idx]['f'])}), "
                             f"dita ({', '.join(per_corda[idx]['d'])}), note ({', '.join(per_corda[idx]['n'])});\n")
        dettagli_map[chiave] = dettagli.rstrip('\n')
    if top_n == 1:
        print("Dettagli dell'unica forma trovata:")
        print(dettagli_map['1'])
        key("Premi un tasto per proseguire all'esercizio audio...")
        return True
    voci["p"] = ">> Prosegui all'esercizio audio"
    while True:
        scelta = menu(d=voci, keyslist=True, show=True, numbered=False, ntf="Scelta non valida",
                      p="Scegli il numero per i dettagli (o 'p' per proseguire): ")
        if scelta is None or scelta == 'p':
            break
        print(f"Dettagli della forma {scelta}:")
        print(dettagli_map[scelta])
        key("Premi un tasto per tornare alle opzioni...")
    return True


def _mostra_manico(s):
    """Chiede la porzione di manico e mostra diteggiature o posizioni delle note."""
    if s.microtonale:
        print("Visualizzazione sul manico approssimata per scale microtonali.")
    if not s.note_manico:
        print("Impossibile mostrare sul manico: nessuna nota standard generata.")
        return
    print("Puoi indicare una porzione di manico per cercare le diteggiature (es. 5-8).")
    scelta_manico = dgt("Limiti Tasti (Invio per tutto il manico): ")
    maninf, mansup = 0, config.NUM_TASTI
    if scelta_manico != "":
        maninf, mansup = Manlimiti(scelta_manico)
        # Con un box stretto e una scala ordinaria si cercano le diteggiature
        if mansup - maninf <= 14 and not s.microtonale and _mostra_diteggiature(s, maninf, mansup):
            return
    visualizza_note_su_manico(s.note_manico, maninf, mansup)


class Esercizio:
    """L'ascolto della scala a tempo, con loop, metronomo e cambio di suono.
    Le note stanno su un mixer polifonico, una voce per nota piu' una per il
    metronomo, cosi' una nota puo' risuonare mentre parte la successiva.
    I battiti cadono su una griglia di scadenze assolute: la sintesi di una
    nota e il polling della tastiera non allungano piu' il tempo. Ogni nota
    si sintetizza durante l'attesa del battito precedente, fresca a ogni
    pizzico come una corda vera, e con il suono MIDI anche il click e' un
    wood block MIDI: nota e battito passano dallo stesso sintetizzatore e
    arrivano insieme."""
    def __init__(self, s):
        self.s = s
        self.num_notes = len(s.frequenze)
        self.suono = suoni.suono_attivo()
        self.bpm = config.impostazioni['default_bpm']
        self.metronomo = False
        self.direzione = 'a'
        self.loop_count = 1
        self.ultima_voce = None
        self.poly = GBAudio.PolyphonicPlayer(fs=GBAudio.FS, num_strings=self.num_notes + 1)
        self.poly.set_pan(self.num_notes, 0.0)  # Il metronomo al centro
        self.renderers = [GBAudio.NoteRenderer(fs=GBAudio.FS) for _ in range(self.num_notes)]
        self.accent_beep, self.tick_beep = self._beep_metronomo()
        self.key_map = {str(i + 1): i for i in range(min(self.num_notes, 9))}
        if self.num_notes >= 10:
            self.key_map['0'] = 9
        self.note_pronte = {}   # indice -> mono sintetizzato in anticipo, consumato al pizzico
        self.griglia = None     # istante del prossimo battito, quando il loop continua

    @staticmethod
    def _beep_metronomo():
        """Accento e beat dell'ultimo preset del metronomo, o quelli di fabbrica."""
        _, last_state = clitronomo.PresetManager(silenzioso=True).get_last_used_preset()
        stato = last_state or {}
        config_accento = stato.get('config_accento') or clitronomo.CONFIG_ACCENTO
        config_tick = stato.get('config_tick') or clitronomo.CONFIG_TICK
        accent = clitronomo.genera_suono_mono_int16(config_accento).astype(np.float32) / 32767.0
        tick = clitronomo.genera_suono_mono_int16(config_tick).astype(np.float32) / 32767.0
        return accent, tick

    def _configura_renderer(self):
        self.note_pronte.clear()
        if self.suono == 'midi':
            self._prepara_midi()
            return
        parametri = suoni.parametri_suono(self.suono)
        for i in range(self.num_notes):
            self.poly.set_pan(i, suoni.pan_per_voce(i, self.num_notes))
            suoni.configura_renderer(self.renderers[i], self.s.frequenze[i] or 0.0, parametri)

    @staticmethod
    def _prepara_midi():
        """Apre la porta MIDI, se non lo era gia', e prepara il canale del click:
        programma Woodblock, pan al centro, niente riverbero ne' chorus."""
        porta = GBAudio.get_midi_out()
        if porta.h_midi is not None:
            porta.program_change(GBAudio.PROGRAMMA_WOODBLOCK, GBAudio.CANALE_CLICK)
            porta.control_change(GBAudio.CC_PAN, GBAudio.PAN_CENTRO, GBAudio.CANALE_CLICK)
            porta.control_change(GBAudio.CC_RIVERBERO, 0, GBAudio.CANALE_CLICK)
            porta.control_change(GBAudio.CC_CHORUS, 0, GBAudio.CANALE_CLICK)

    def _cambia_suono(self):
        self.suono = suoni.prossimo_suono(self.suono)
        self._configura_renderer()

    def _riga_stato(self, in_loop):
        note = self.s.testo_note(self.direzione) or "(vuota)"
        dir_abbrev = "asc" if self.direzione == 'a' else "dis"
        sigla = suoni.sigla_suono(self.suono)
        if in_loop:
            print(f"\r{note} | L:{self.loop_count} {dir_abbrev} {sigla}{' ' * 15}\r", end="", flush=True)
        else:
            metro = " (M)" if self.metronomo else ""
            print(f"\r{note} | {dir_abbrev} {sigla}{metro} (1-9, 0, A, D, L, B, M, SPAZIO, ?, ESC):\r", end="", flush=True)

    def _mono(self, idx):
        """Il mono della nota idx: quello preparato in anticipo se c'e', altrimenti
        lo sintetizza adesso. Una volta preso non si riusa: il pizzico dopo ne
        avra' uno nuovo, con il suo attacco."""
        if idx not in self.note_pronte:
            self.note_pronte[idx] = suoni.mono_da_renderer(self.renderers[idx])
        return self.note_pronte.pop(idx)

    def _prepara(self, idx):
        """Sintetizza in anticipo la nota idx, se non e' gia' pronta: si chiama
        durante l'attesa di un battito, cosi' il pizzico che segue non aspetta."""
        if idx is not None and self.suono != 'midi' and idx not in self.note_pronte:
            self.note_pronte[idx] = suoni.mono_da_renderer(self.renderers[idx])

    def _suona_nota(self, idx, dur):
        """Suona la nota idx. True se occupa una voce del mixer da spegnere dopo."""
        freq = self.s.frequenze[idx]
        if freq is None or freq <= 0:
            return False
        if self.suono == 'midi':
            GBAudio.play_midi_note_temp(GBAudio.freq_to_midi(freq), max(DURATA_MINIMA_NOTA_MIDI, dur - ANTICIPO_NOTE_OFF))
            return False
        mono = self._mono(idx)
        if mono is None:
            return False
        self.poly.pluck(idx, mono)
        return True

    def _click(self, accento):
        """Il battito del metronomo: con il suono MIDI e' un wood block sul canale
        del click, con gli altri suoni e' il beep del metronomo sul mixer.
        Se la porta MIDI non si e' aperta, il beep resta l'unico click."""
        if self.suono == 'midi' and GBAudio.get_midi_out().h_midi is not None:
            nota = NOTA_ACCENTO if accento else NOTA_TICK
            velocita = VELOCITA_ACCENTO if accento else VELOCITA_TICK
            GBAudio.play_midi_note_temp(nota, DURATA_CLICK_MIDI, velocita, canale=GBAudio.CANALE_CLICK)
            return
        click = self.accent_beep if accento else self.tick_beep
        if click.size > 0:
            self.poly.pluck(self.num_notes, click)

    def _ferma_voci(self):
        """Zittisce il mixer e azzera la griglia: il prossimo ascolto riparte da capo."""
        self.poly.mute()
        self.ultima_voce = None
        self.griglia = None

    def _attendi(self, scadenza, in_loop, prossima=None):
        """Aspetta la scadenza del battito ascoltando la tastiera e, intanto,
        prepara la nota prossima. La tastiera si guarda almeno una volta per
        battito, anche se la sintesi ha mangiato tutta l'attesa. Restituisce
        None a battito finito, altrimenti esci, fermato o interrotto."""
        self._prepara(prossima)
        while True:
            residuo = scadenza - orologio()
            tasto = key(attesa=max(0.0, min(PASSO_ASCOLTO, residuo)))
            if tasto == ' ':
                self._cambia_suono()
                self._prepara(prossima)
                self._riga_stato(in_loop)
            elif tasto.lower() == 'l' and in_loop:
                self._ferma_voci()
                print(f"\rLoop disattivato.{' ' * 40}\r", end="", flush=True)
                return 'fermato'
            elif tasto == chr(27):
                self._ferma_voci()
                return 'esci' if in_loop else 'interrotto'
            if residuo <= 0:
                return None

    def _suona_sequenza(self, in_loop):
        """Suona la scala una volta nella direzione corrente, con il metronomo
        se attivo: se le note non riempiono la battuta di 4/4, la completano
        battiti muti. I battiti cadono su una griglia di scadenze assolute
        che in loop continua da un giro all'altro. Restituisce l'esito di _attendi."""
        n = self.num_notes
        seq = list(range(n)) if self.direzione == 'a' else list(range(n - 1, -1, -1))
        extra_beats = (4 - (n % 4)) % 4 if self.metronomo else 0
        dur_step = 60.0 / self.bpm
        # La prima nota si prepara prima di fissare la griglia, cosi' parte in tempo
        self._prepara(seq[0])
        origine = self.griglia if in_loop and self.griglia is not None else orologio()
        for idx_step in range(n + extra_beats):
            ritardo = orologio() - (origine + idx_step * dur_step)
            if ritardo > dur_step / 2:
                # Troppo indietro per recuperare in silenzio: la griglia riparte da qui
                origine += ritardo
            if self.ultima_voce is not None:
                self.poly.mute(self.ultima_voce)
                self.ultima_voce = None
            if idx_step < n:
                idx = seq[idx_step]
                if self._suona_nota(idx, dur_step):
                    self.ultima_voce = idx
            if self.metronomo:
                self._click(idx_step % 4 == 0)
            prossima = seq[idx_step + 1] if idx_step + 1 < n else seq[0]
            esito = self._attendi(origine + (idx_step + 1) * dur_step, in_loop, prossima)
            if esito:
                return esito
        self.griglia = origine + (n + extra_beats) * dur_step if in_loop else None
        return None

    def _imposta_bpm(self):
        nuovo_bpm = dgt(f"\rNuovi BPM (attuale: {self.bpm}): ", kind='i', imin=20, imax=300, default=self.bpm)
        if nuovo_bpm != self.bpm:
            self.bpm = nuovo_bpm
            config.impostazioni['default_bpm'] = nuovo_bpm
            config.salva_modifiche()
            print(f"\rBPM predefiniti aggiornati a {nuovo_bpm}.{' ' * 20}")

    @staticmethod
    def _aiuto():
        print("\nAiuto esercizio scala.")
        for k, v in MENU_ESERCIZIO.items():
            print(f"  Tasto {k}: {v}")
        print("  Tasto SPAZIO: cambia suono")
        print("  Tasto ESC: torna al menu principale")

    def avvia(self):
        print("Menu esercizio scala. Premi '?' per aiuto.")
        self.poly.start()
        self._configura_renderer()
        loop_attivo = False
        try:
            while True:
                if loop_attivo:
                    self._riga_stato(True)
                    esito = self._suona_sequenza(True)
                    if esito == 'esci':
                        break
                    if esito == 'fermato':
                        loop_attivo = False
                        continue
                    self.loop_count += 1
                    continue
                self._riga_stato(False)
                scelta = key()
                if not scelta:
                    continue
                scelta = scelta.lower()
                if scelta == chr(27):
                    break
                if scelta == '?':
                    self._aiuto()
                elif scelta == 'm':
                    self.metronomo = not self.metronomo
                    print(f"\rMetronomo {'attivo' if self.metronomo else 'disattivato'} per l'esercizio.{' ' * 20}")
                elif scelta == ' ':
                    self._cambia_suono()
                elif scelta in self.key_map:
                    self._suona_nota(self.key_map[scelta], suoni.parametri_suono('midi')['dur'])
                elif scelta == 'l':
                    loop_attivo = True
                    self.loop_count = 1
                    self.ultima_voce = None
                    self.griglia = None
                    print(f"\rLoop attivo. Premi L per fermare.{' ' * 20}\r", end="", flush=True)
                elif scelta == 'b':
                    self._imposta_bpm()
                elif scelta in ('a', 'd'):
                    self.direzione = scelta
                    self._suona_sequenza(False)
        finally:
            self.poly.stop()


def VisualizzaEsercitatiScala():
    """Voce di menu: scelta della scala, riepilogo, manico e ascolto a tempo."""
    print("Visualizza ed esercitati sulle scale (catalogo di music21).")
    scelta = _scegli_scala()
    if scelta is None:
        return
    tonica_std, selected_key = scelta
    try:
        s = _costruisci_scala(tonica_std, selected_key)
    except (scale_catalog.ScaleException, Music21Exception, ValueError) as e:
        print(f"Errore nella generazione della scala: {e}")
        key("Premi un tasto...")
        return
    s.stampa_riepilogo()
    _mostra_manico(s)
    if not s.frequenze:
        print("Nessuna nota audio generata per l'esercizio.")
        key("Premi un tasto per tornare al menu...")
        return
    Esercizio(s).avvia()
    print("Fine esercizio.")
