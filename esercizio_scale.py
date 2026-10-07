# Chitabry, esercizio scale: scelta della scala dal catalogo, note sul manico, diteggiature e ascolto a tempo.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Nato con la revisione 1 del 2026-09-09 dallo spezzettamento di views.py:
# la funzione unica di 665 righe e' divisa nelle sue fasi, e l'ascolto a
# tempo, che era scritto due volte, una per il loop e una per il comando
# singolo, sta in un posto solo. Dal collaudo del 2026-09-10: i battiti su
# una griglia di scadenze assolute, le note sintetizzate in anticipo durante
# il battito precedente, e il click in MIDI quando il suono e' MIDI, perche'
# passando da due sintetizzatori diversi nota e battito arrivavano in tempi
# diversi. Dalla 9.0.0, issue 58, con un'armonica attiva al posto del manico
# ci sono la posizione, la tablatura e la scelta dell'ottava da esercitare.

from time import monotonic as orologio

import numpy as np
from GBUtils import dgt, enter_escape, key, menu
from music21 import pitch, scale
from music21.exceptions21 import Music21Exception

import armonica
import armonica_vista
import clitronomo
import config
import GBAudio
import scale_catalog
import suoni
from generatore_scale import ScalePathfinder
from manico import Manlimiti, visualizza_note_su_manico
from nomenclatura import get_nota, mappa_toniche, nome_con_grafia, nome_da_midi
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
DURATA_CLICK_MIDI = 0.1   # secondi prima del note off: il wood block e' un colpo secco
# Il note off di una nota MIDI arriva un po' prima del battito seguente: se
# due battiti hanno la stessa nota, altrimenti spegnerebbe quella appena partita.
ANTICIPO_NOTE_OFF = 0.03
DURATA_MINIMA_NOTA_MIDI = 0.05
# Quanto una nota puo' scostarsi dal temperamento, in semitoni, e contare
# ancora come quella nota sull'armonica: trentadue centesimi tengono dentro
# le intonazioni naturali, anche la settima naturale 7/4, a 969 centesimi, cioe'
# 31 sotto il SIb temperato, e lasciano fuori le note gia' vicine al quarto di
# tono, come quelle della Bohlen-Pierce a 33. Fino alla 9.6.0 erano trenta, e
# la settima naturale restava fuori.
SCARTO_TEMPERATO = 0.32
# Quanti risultati mostra la ricerca nell'archivio Scala prima di chiedere
# un'altra parola: cinquanta tengono dentro pentatonic, che ne trova 43.
RISULTATI_ARCHIVIO = 50


def midi_temperato(p):
    """Il numero MIDI della nota temperata piu' vicina, se lo scarto resta
    entro SCARTO_TEMPERATO; None per una nota piu' lontana, come un quarto
    di tono, o per cio' che non e' un'altezza. Le scale dell'archivio Scala
    sono quasi tutte in intonazione naturale, con la quinta a 702 centesimi
    invece di 700: senza tolleranza, sull'armonica non ci starebbe niente."""
    if not isinstance(p, pitch.Pitch):
        return None
    ps = float(p.ps)
    vicino = round(ps)
    return vicino if abs(ps - vicino) <= SCARTO_TEMPERATO else None


def velocita_del_click(config_suono):
    """La velocita' MIDI del wood block da un suono del metronomo: il suo
    volume in percentuale, sui 127 della velocita', almeno 1."""
    return max(1, min(127, round(127 * config_suono.get('volume_perc', 100) / 100)))


class Scala:
    """Una scala pronta per l'esercizio: nome, note per il manico, note da
    mostrare in salita e in discesa, frequenze da suonare."""
    # Le note MIDI escono sul primo canale, con lo strumento delle impostazioni
    canale_midi = 0

    def __init__(self, tonica_std, nome_base, scala_m21):
        self.tonica_std = tonica_std
        self.nome_base = nome_base
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
        self.pitches = pitches_asc
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

    def nomi_note(self, direzione):
        note = self.note_asc if direzione == 'a' else self.note_desc
        return " ".join(note)

    def testo_note(self, direzione):
        """Le note come le mostra la riga di stato dell'esercizio."""
        return self.nomi_note(direzione)

    def stampa_riepilogo(self):
        asc = self.nomi_note('a')
        desc = self.nomi_note('d')
        print(f"Scala: {self.nome}")
        print(f"Note (Asc): {asc if asc else '(Nessuna nota trovata)'}")
        if self.microtonale:
            print("INFO: scala microtonale rilevata. L'audio usera' le frequenze esatte, se calcolabili.")
        if desc and asc != desc:
            print(f"Note (Desc): {desc}")


class ScalaArmonica(Scala):
    """La scala su un tratto dell'armonica attiva: per ogni nota anche il
    modo meno faticoso di suonarla, che la riga di stato dell'esercizio
    mostra al posto del nome. In MIDI le note escono con il programma
    Harmonica, sul canale dell'armonica."""
    canale_midi = GBAudio.CANALE_ARMONICA

    def __init__(self, tonica_std, nome_base, scala_m21, modello):
        super().__init__(tonica_std, nome_base, scala_m21)
        self.tecniche = []
        for p in self.pitches:
            midi = midi_temperato(p)
            self.tecniche.append(None if midi is None else modello.migliore(midi))

    def testo_note(self, direzione):
        simboli = [t.simbolo if t is not None else "x" for t in self.tecniche]
        if direzione != 'a':
            simboli.reverse()
        return " ".join(simboli)

    def estremi(self):
        """Il nome della prima e dell'ultima nota, per dire il tratto."""
        return self.note_asc[0], self.note_asc[-1]


def _scegli_tipo(tonica_std):
    """Il tipo di scala in due passi: il gruppo, poi la scala dentro il
    gruppo. Le scale comuni e le classi di music21 sono poche, e si scelgono
    scrivendo l'inizio del nome; l'archivio Scala ne ha quasi quattromila, e
    si cerca per parola dentro le descrizioni. Restituisce la chiave
    paradigma:id, o None se si rinuncia.
    Fino alla 9.3 c'era un menu unico, che filtrava l'inizio di chiavi come
    concrete:MajorScale o scala:05-19: scrivendo blues non usciva niente."""
    nota = get_nota(tonica_std)
    per_gruppo = {"comune": [], "concrete": [], "scala": []}
    for voce in scale_catalog.SCALE_CATALOG:
        per_gruppo.setdefault(voce["paradigm"], []).append(voce)
    gruppi = {
        "1": f"Scale comuni, {len(per_gruppo['comune'])}, con i nomi italiani: maggiore, minori, modi, pentatoniche, blues, bebop",
        "2": f"Le classi di music21, {len(per_gruppo['concrete'])}, con i nomi inglesi: modi, ipomodi, raga, ottatonica",
        "3": f"L'archivio Scala, {len(per_gruppo['scala'])} scale storiche, etniche e microtonali, da cercare per parola inglese",
    }
    print(f"Gruppo di scale per {nota}:")
    gruppo = menu(d=gruppi, keyslist=True, show=True, show_on_filter=False, ordered=False, ntf="Scelta non valida")
    if gruppo is None:
        return None
    if gruppo == "3":
        voci = {f"scala:{v['programmatic_id']}": f"{v['friendly_name']} ({v['programmatic_id']})" for v in per_gruppo["scala"]}
        return fuzzy_search_and_select(voci, f"Cerca nell'archivio Scala per {nota}, una o piu' parole inglesi, per esempio blues, raga o pentatonic japanese: ",
                                       "scala", massimo=RISULTATI_ARCHIVIO)
    if gruppo == "1":
        # Nell'ordine in cui sono scritte: le maggiori e le minori, i modi, le altre
        voci_gruppo = sorted(per_gruppo["comune"], key=lambda v: [c[0] for c in scale_catalog.SCALE_COMUNI].index(v["programmatic_id"]))
        paradigma = "comune"
    else:
        voci_gruppo = sorted(per_gruppo["concrete"], key=lambda v: v["friendly_name"].lower())
        paradigma = "concrete"
    voci = {v["friendly_name"]: v.get("descrizione", "") for v in voci_gruppo}
    chiavi = {v["friendly_name"]: f"{paradigma}:{v['programmatic_id']}" for v in voci_gruppo}
    print(f"Tipo di scala per {nota}: scrivi le prime lettere, il menu completa da solo il resto, e Invio sceglie il nome completo.")
    scelto = menu(d=voci, keyslist=True, show=True, pager=25, ordered=False, ntf="Tipo non valido")
    return None if scelto is None else chiavi[scelto]


def _scegli_scala():
    """Tonica e tipo. Restituisce la coppia (tonica standard, chiave paradigma:id) o None."""
    toniche = mappa_toniche()
    scelta = menu(d=toniche, keyslist=True, show=True, pager=12, ntf="Nota non valida", p="Scegli la TONICA della scala: ")
    if scelta is None:
        return None
    tonica_std = toniche[scelta]
    selected_key = _scegli_tipo(tonica_std)
    if selected_key is None:
        print("Annullato.")
        return None
    return tonica_std, selected_key


def _costruisci_scala(tonica_std, selected_key, ottava=4, modello=None):
    """La scala di music21 per la chiave scelta, con la tonica nell'ottava
    indicata, la quarta se non si dice; con il modello di un'armonica e' una
    ScalaArmonica. Solleva ValueError se la chiave e' malformata,
    ScaleException o Music21Exception se music21 non la istanzia."""
    try:
        paradigm, scale_id = selected_key.split(':', 1)
    except ValueError:
        raise ValueError(f"chiave di selezione '{selected_key}' malformata") from None
    nome_base = scale_catalog.SCALE_TYPES_DICT.get(selected_key, scale_id)
    scala_m21 = scale_catalog.get_scale_from_usi(f"{paradigm}:{tonica_std}{ottava}:{scale_id}")
    if modello is not None:
        return ScalaArmonica(tonica_std, nome_base, scala_m21, modello)
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


def _nome_nella_scala(nome_m21, midi):
    """Il nome di una nota con la grafia della scala e l'ottava che suona:
    un SIb resta SIb, e un DOb si numera con l'ottava del SI che suona."""
    return nome_con_grafia(nome_m21, midi)


def _etichetta_grado(tonica_std, nome_m21):
    """Il grado di una nota contato dalla tonica, nella forma delle formule
    delle scale comuni: 4, b5, #4, b7. Fino alla 9.6 il numero era la
    posizione della nota nella scala, giusto solo per le scale di sette note:
    nel SOL blues il REb risultava grado 4, mentre e' la quinta diminuita."""
    from music21 import interval
    sotto = pitch.Pitch(tonica_std)
    sotto.octave = 4
    sopra = pitch.Pitch(nome_m21)
    sopra.octave = 4
    lettere = "CDEFGAB"
    if sopra.ps < sotto.ps or (sopra.ps == sotto.ps and lettere.index(sopra.step) < lettere.index(sotto.step)):
        sopra.octave = 5
    nome = interval.Interval(sotto, sopra).simpleName
    qualita, numero = nome.rstrip("0123456789"), nome[len(nome.rstrip("0123456789")):]
    perfetto = numero in ("1", "4", "5", "8")
    alterazioni = {"P": "", "M": "", "m": "b", "d": "b" if perfetto else "bb", "A": "#",
                   "dd": "bb" if perfetto else "bbb", "AA": "##"}
    return f"{alterazioni.get(qualita, '?')}{numero}"


def _riassunto(tecniche):
    """Le tecniche di un tratto di scala in una frase corta."""
    conteggi = armonica.conta_tecniche(tecniche)
    if list(conteggi) == ["naturale"]:
        return "tutte naturali"
    return ", ".join(f"{categoria} {quante}" for categoria, quante in conteggi.items())


def _si_ripete_all_ottava(s):
    """Vero se la scala torna uguale un'ottava sopra, come tutte quelle di
    music21, le comuni e quasi tutte quelle dell'archivio Scala. Per queste
    ultime music21 risponde sempre di no, quindi lo dice il file: l'ultima
    nota e' il periodo, che per la Bohlen-Pierce, per esempio, e' una
    dodicesima. Le scale che non si ripetono all'ottava cambiano note da
    un'ottava all'altra, e ridurle a dodici classi ne inventa di false."""
    if not isinstance(s.scala_m21, scale.ScalaScale):
        return True
    altezze = [p for p in s.pitches if isinstance(p, pitch.Pitch)]
    if len(altezze) < 2:
        return True
    return abs(float(altezze[-1].ps) - float(altezze[0].ps) - 12) < 0.01


def _note_su_estensione(s, modello):
    """Le note temperate della scala che cadono nell'estensione dell'armonica,
    come coppie (numero MIDI, nome da mostrare) dal basso, e i gradi, cioe'
    classe di altezza e nome music21 dalla tonica in su: vuoti se la scala non
    si ripete all'ottava, perche' allora i gradi non tornano a ogni ottava."""
    grave, acuta = modello.estensione()
    if _si_ripete_all_ottava(s):
        ordine, nomi = [], {}
        for p in s.pitches:
            midi = midi_temperato(p)
            if midi is not None and midi % 12 not in nomi:
                # Una nota presa per vicinanza si chiama come la nota che suona
                esatta = float(p.ps) == midi
                nomi[midi % 12] = p.name if esatta else config.NOTE_STD[midi % 12]
                ordine.append(midi % 12)
        # I gradi si contano dalla tonica: gli ipomodi cominciano una quarta sotto
        tonica = pitch.Pitch(s.tonica_std).pitchClass
        if tonica in ordine:
            ordine = ordine[ordine.index(tonica):] + ordine[:ordine.index(tonica)]
        gradi = {classe: nomi[classe] for classe in ordine}
        note = [(m, _nome_nella_scala(nomi[m % 12], m)) for m in range(grave, acuta + 1) if m % 12 in nomi]
        return note, gradi
    try:
        altezze = s.scala_m21.getPitches(pitch.Pitch(midi=grave), pitch.Pitch(midi=acuta))
    except Music21Exception:
        altezze = s.pitches
    note = {}
    for p in altezze:
        midi = midi_temperato(p)
        if midi is not None and grave <= midi <= acuta and midi not in note:
            esatta = float(p.ps) == midi
            note[midi] = get_nota(p.nameWithOctave.replace('-', 'b')) if esatta else nome_da_midi(midi)
    return sorted(note.items()), {}


def _tablatura_completa(s, modello):
    """La scala su tutta l'estensione dell'armonica: una riga per nota con il
    modo piu' comodo e gli altri, le due sequenze compatte, i gradi con il
    modo piu' comodo in ogni ottava, il conteggio delle tecniche e le note
    critiche."""
    note, gradi = _note_su_estensione(s, modello)
    if not note:
        print("La scala non ha note temperate nell'estensione dell'armonica: sull'armonica non si suona.")
        return
    if s.microtonale:
        print("Sull'armonica le note si prendono temperate: quelle a non piu' di trentadue centesimi diventano la nota vicina, quelle piu' lontane, come i quarti di tono, restano fuori.")
    if not gradi:
        print("Questa scala non si ripete all'ottava: la tablatura mostra le sue note vere ottava per ottava, e i gradi non si contano.")
    tecniche = [modello.migliore(m) for m, _ in note]
    print(f"Tablatura su tutta l'estensione, da {note[0][1]} a {note[-1][1]}, {len(note)} note:")
    for (midi, nome), tecnica in zip(note, tecniche, strict=True):
        if tecnica is None:
            print(f"{nome}: non c'e' su questa armonica")
            continue
        altre = modello.tecniche_per_nota(midi)[1:]
        riga = f"{nome}: {tecnica.simbolo}"
        if altre:
            riga += f" (anche {' '.join(a.simbolo for a in altre)})"
        print(riga)
    simboli = [t.simbolo if t is not None else "x" for t in tecniche]
    print(f"In salita: {' '.join(simboli)}")
    print(f"In discesa: {' '.join(reversed(simboli))}")
    if gradi:
        print("Gradi della scala, contati dalla tonica, con il modo piu' comodo in ogni ottava:")
        for classe, nome in gradi.items():
            dove = [t.simbolo for (m, _), t in zip(note, tecniche, strict=True) if m % 12 == classe and t is not None]
            testo = " ".join(dove) if dove else "non c'e' su questa armonica"
            print(f"Grado {_etichetta_grado(s.tonica_std, nome)}, {get_nota(nome.replace('-', 'b'))}: {testo}")
    print(f"Tecniche su tutta l'estensione: {_riassunto(tecniche)}.")
    critiche = [(nome, t) for (_, nome), t in zip(note, tecniche, strict=True) if t is not None and t.livello >= 2]
    if critiche:
        print("Note critiche, che chiedono un bending profondo o un overbend:")
        for nome, tecnica in critiche:
            print(f"{nome}: {tecnica.simbolo}, {tecnica.descrizione().lower()}")


def _tabella_posizioni(s, modello, scelta):
    """Le dodici posizioni in cui si suona questa scala, nell'ordine, ognuna
    con la scala che da' su questa armonica, l'armonica che serve per la
    tonica scelta e le tecniche che chiede su tutta l'estensione; in fondo,
    le tre piu' comode. Per un'armonica sola le domande sono due, quale
    tonica in quale posizione e quale armonica per questa tonica, e la
    tabella risponde a tutte e due."""
    if not _si_ripete_all_ottava(s):
        print("Le posizioni si contano in quinte e valgono per le scale che si ripetono all'ottava: per questa la tabella non si fa.")
        return
    tonica = pitch.Pitch(s.tonica_std).pitchClass
    intervalli = {(m - tonica) % 12 for m in (midi_temperato(p) for p in s.pitches) if m is not None}
    if not intervalli:
        return
    righe = armonica.tabella_posizioni(modello, intervalli)
    print(f"Le dodici posizioni della scala {s.nome_base}, con le tecniche dell'ottava piu' comoda in ciascuna:")
    for numero, _classe, _estensione, ottava in righe:
        titolo = armonica.ORDINALI[numero - 1].capitalize() + " posizione"
        if numero in armonica.NOMI_POSIZIONE:
            titolo += f" ({armonica.NOMI_POSIZIONE[numero]})"
        if numero == scelta:
            dove = f"quella scelta, {s.nome} su questa armonica"
        else:
            sull_armonica = get_nota(armonica.tonalita_per(tonica, numero))
            dove = f"{get_nota(armonica.tonica_della_posizione(modello.tonalita, numero))} {s.nome_base} su questa armonica, oppure {s.nome} sull'armonica in {sull_armonica}"
        if ottava is None:
            tecniche = "la tonica non c'e' sull'armonica"
        else:
            # La tonica con la grafia della riga: SIb, non LA#
            nome_tonica = get_nota(s.tonica_std if numero == scelta else armonica.tonica_della_posizione(modello.tonalita, numero))
            tecniche = f"dalla tonica {nome_tonica}{ottava[0] // 12 - 1}, {_riassunto(ottava[1])}"
        print(f"{titolo}: {dove}. Ottava piu' comoda {tecniche}.")
    comode = armonica.piu_comode(righe)
    print(f"Le piu' comode, per le tecniche che chiedono nell'ottava migliore: {', '.join(armonica.ORDINALI[n - 1] for n in comode)}.")


def _scegli_ottava(tonica_std, selected_key, modello):
    """Le ottave in cui la scala comincia sull'armonica, con le tecniche che
    chiede ciascuna, e la scelta di quella da esercitare: Invio prende la
    piu' comoda, a parita' la piu' grave. None se non ce n'e' nessuna."""
    grave, acuta = modello.estensione()
    candidate = []
    for ottava in range(0, 9):
        if not grave <= pitch.Pitch(f"{tonica_std}{ottava}").midi <= acuta:
            continue
        try:
            sa = _costruisci_scala(tonica_std, selected_key, ottava, modello)
        except (scale_catalog.ScaleException, Music21Exception, ValueError):
            continue
        # La scala deve cominciare sull'armonica: un ipomodo parte una quarta
        # sotto la tonica, e la tonica dentro l'estensione non basta
        if sa.tecniche and sa.tecniche[0] is not None and sum(1 for t in sa.tecniche if t is not None) >= 2:
            candidate.append(sa)
    if not candidate:
        print("Su questa armonica la scala non ha un tratto da esercitare.")
        return None
    comoda = min(range(len(candidate)), key=lambda i: (armonica.fatica(candidate[i].tecniche), i))
    if len(candidate) == 1:
        return candidate[0]
    print("Ottave in cui si puo' fare l'esercizio:")
    for numero, sa in enumerate(candidate, start=1):
        primo, ultimo = sa.estremi()
        print(f"{numero}: da {primo} a {ultimo}, {_riassunto(sa.tecniche)}")
    scelta = dgt(f"Quale ottava (Invio per la {comoda + 1}, la piu' comoda): ", kind='i', imin=1, imax=len(candidate), default=comoda + 1)
    return candidate[scelta - 1]


def _mostra_armonica(s, tonica_std, selected_key):
    """Con un'armonica attiva, al posto del manico: l'armonica e la posizione,
    la tablatura su tutta l'estensione e la scelta dell'ottava. Restituisce
    la scala da esercitare, o None se non ce n'e'."""
    modello = config.ARMONICA
    print(f"Armonica attiva: {armonica_vista.nome_attivo()}, {armonica_vista.descrivi(modello)}.")
    numero = armonica.posizione(modello.tonalita, pitch.Pitch(tonica_std).pitchClass)
    print(f"Scala richiesta: {s.nome}, in {armonica.descrivi_posizione(numero)}.")
    if modello.chiave_accordatura == "richter" and numero in armonica.USI_RICHTER:
        print(f"Sulla Richter questa posizione si usa per {armonica.USI_RICHTER[numero]}.")
    _tabella_posizioni(s, modello, numero)
    _tablatura_completa(s, modello)
    scelta = _scegli_ottava(tonica_std, selected_key, modello)
    if scelta is not None:
        primo, ultimo = scelta.estremi()
        print(f"Esercizio da {primo} a {ultimo}: {scelta.testo_note('a')}")
    return scelta


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
        config_accento, config_tick = self._preset_metronomo()
        self.accent_beep, self.tick_beep = self._beep_metronomo(config_accento, config_tick)
        # Col suono MIDI il click e' un wood block, ma il volume e' quello del
        # preset: fino alla 9.8 era fisso, al massimo sull'accento, e copriva
        # le note (collaudo di Gabriele del 7 ottobre 2026)
        self.velocita_accento = velocita_del_click(config_accento)
        self.velocita_tick = velocita_del_click(config_tick)
        self.key_map = {str(i + 1): i for i in range(min(self.num_notes, 9))}
        if self.num_notes >= 10:
            self.key_map['0'] = 9
        self.note_pronte = {}   # indice -> mono sintetizzato in anticipo, consumato al pizzico
        self.griglia = None     # istante del prossimo battito, quando il loop continua

    @staticmethod
    def _preset_metronomo():
        """Le configurazioni di accento e battito dell'ultimo preset del
        metronomo, cioe' quello attivo, o quelle di fabbrica."""
        _, last_state = clitronomo.PresetManager(silenzioso=True).get_last_used_preset()
        stato = last_state or {}
        return (stato.get('config_accento') or clitronomo.CONFIG_ACCENTO,
                stato.get('config_tick') or clitronomo.CONFIG_TICK)

    @staticmethod
    def _beep_metronomo(config_accento, config_tick):
        """Accento e battito del preset, come campioni per il mixer."""
        accent = clitronomo.genera_suono_mono_int16(config_accento).astype(np.float32) / 32767.0
        tick = clitronomo.genera_suono_mono_int16(config_tick).astype(np.float32) / 32767.0
        return accent, tick

    def _configura_renderer(self):
        self.note_pronte.clear()
        if self.suono == 'midi':
            self._prepara_midi()
            if self.s.canale_midi != 0:
                suoni.prepara_canale_armonica()
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
            GBAudio.play_midi_note_temp(GBAudio.freq_to_midi(freq), max(DURATA_MINIMA_NOTA_MIDI, dur - ANTICIPO_NOTE_OFF),
                                        canale=self.s.canale_midi)
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
            velocita = self.velocita_accento if accento else self.velocita_tick
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
    if config.ARMONICA is not None:
        s = _mostra_armonica(s, tonica_std, selected_key)
        if s is None:
            key("Premi un tasto per tornare al menu...")
            return
    else:
        _mostra_manico(s)
    if not s.frequenze:
        print("Nessuna nota audio generata per l'esercizio.")
        key("Premi un tasto per tornare al menu...")
        return
    Esercizio(s).avvia()
    print("Fine esercizio.")
