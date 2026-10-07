# Chitabry, armonica: le ance di ogni foro, i bending, gli overbend e la notazione simbolica dell'armonica a bocca.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Opus 5.5, modalita' auto).
# Nato con la 9.0.0 dal piano della issue 58. Il modulo lavora solo con i
# numeri MIDI e non importa music21: i nomi delle note li mette chi mostra,
# nella nomenclatura scelta dall'utente. Dalla 9.3.0 la cromatica puo' avere
# dieci fori, la disposizione della Richter e niente valvole, come la JDR
# Trochilus, e ogni armonica puo' essere nel registro basso.

import re
from dataclasses import dataclass

# Le dodici tonalita' come le stampano i costruttori sulle armoniche.
TONALITA = ["C", "Db", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
# Gli altri nomi con cui una tonalita' si puo' trovare scritta nell'archivio.
_SINONIMI_TONALITA = {"C#": "Db", "D#": "Eb", "Gb": "F#", "G#": "Ab", "A#": "Bb"}
FAMIGLIE = ("diatonica", "cromatica")
REGISTRI = ("normale", "basso")


@dataclass(frozen=True)
class Accordatura:
    """Le ance di un'armonica in DO, in semitoni sopra il foro 1 soffiato.
    Se ripetuta e' falso ci sono tutti i dieci fori; se e' vero ci sono i
    primi quattro, che si ripetono un'ottava piu' su ogni quattro fori, per
    quanti fori ha l'armonica. famiglie dice su quali armoniche si trova:
    la Richter, per esempio, anche sulle cromatiche a cursore come la
    Trochilus; fori dice con quanti fori; valvole dice se la cromatica, di
    solito, le ha."""
    nome: str
    descrizione: str
    soffiati: tuple
    aspirati: tuple
    famiglie: tuple = ("diatonica",)
    fori: tuple = (10,)
    ripetuta: bool = False
    valvole: bool = False


_RICHTER_SOFFIATI = (0, 4, 7, 12, 16, 19, 24, 28, 31, 36)
_RICHTER_ASPIRATI = (2, 7, 11, 14, 17, 21, 23, 26, 29, 33)

ACCORDATURE = {
    "richter": Accordatura("Richter", "la standard di blues, folk e rock",
                           _RICHTER_SOFFIATI, _RICHTER_ASPIRATI, famiglie=FAMIGLIE),
    "country": Accordatura("Country", "la Richter con il foro 5 aspirato alzato di un semitono",
                           _RICHTER_SOFFIATI, (2, 7, 11, 14, 18, 21, 23, 26, 29, 33)),
    "paddy_richter": Accordatura("Paddy Richter", "la Richter con il foro 3 soffiato alzato di un tono, per la musica irlandese",
                                 (0, 4, 9, 12, 16, 19, 24, 28, 31, 36), _RICHTER_ASPIRATI, famiglie=FAMIGLIE),
    "natural_minor": Accordatura("Natural Minor", "minore naturale in seconda posizione",
                                 (0, 3, 7, 12, 15, 19, 24, 27, 31, 36), (2, 7, 10, 14, 17, 21, 22, 26, 29, 33)),
    "harmonic_minor": Accordatura("Harmonic Minor", "minore armonica in prima posizione",
                                  (0, 3, 7, 12, 15, 19, 24, 27, 31, 36), (2, 7, 11, 14, 17, 20, 23, 26, 29, 32)),
    "melody_maker": Accordatura("Melody Maker", "melodie maggiori in seconda posizione",
                                (0, 4, 9, 12, 16, 19, 24, 28, 31, 36), (2, 7, 11, 14, 18, 21, 23, 26, 30, 33)),
    "solo": Accordatura("Solo", "la standard: ogni quattro fori un'ottava, con la tonica ripetuta",
                        (0, 4, 7, 12), (2, 5, 9, 11), famiglie=("cromatica",), fori=(10, 12, 16),
                        ripetuta=True, valvole=True),
    # La bebop scambia le due ance dei fori 4, 8 e 12: la nota piu' grave sta
    # sempre sul soffio, e senza valvole i fori si possono piegare.
    "bebop": Accordatura("Bebop", "la Solo con le ance dei fori 4, 8 e 12 scambiate, la piu' grave sul soffio",
                         (0, 4, 7, 11), (2, 5, 9, 12), famiglie=("cromatica",), fori=(12, 16), ripetuta=True),
}

# Le posizioni si contano in quinte dalla tonalita' dell'armonica.
ORDINALI = ("prima", "seconda", "terza", "quarta", "quinta", "sesta", "settima",
            "ottava", "nona", "decima", "undicesima", "dodicesima")
NOMI_POSIZIONE = {1: "straight harp", 2: "cross harp", 3: "slant harp"}
# Gli usi tradizionali delle posizioni valgono per l'accordatura Richter:
# le altre spostano proprio le note che rendono adatta una posizione.
USI_RICHTER = {
    1: "le melodie folk e pop e le scale maggiori",
    2: "blues, rock e country: scala blues, pentatonica minore, misolidia",
    3: "le scale minori, dorica e minore naturale",
    4: "la minore naturale, cioe' l'eolia",
    5: "la frigia",
    12: "la lidia",
}

_PASSI_BENDING = {1: "mezzo tono", 2: "un tono", 3: "un tono e mezzo"}
# Il simbolo: verso, foro, poi le barre del bending o l'asterisco
# dell'overbend, e il segno del cursore premuto. Per il cursore si accettano
# anche ^ e ~, che il piano della issue 58 lascia come alternative.
_SIMBOLO = re.compile(r"^([+-])(\d{1,2})(/{1,3}|\*)?([<^~])?$")


def normalizza_tonalita(nome):
    """Il nome di una tonalita' come sta in TONALITA, da C a B con i bemolli
    dei costruttori; ValueError se non e' una delle dodici."""
    pulito = str(nome).strip()
    if len(pulito) > 1:
        pulito = pulito[0].upper() + pulito[1:].lower()
    else:
        pulito = pulito.upper()
    pulito = _SINONIMI_TONALITA.get(pulito, pulito)
    if pulito not in TONALITA:
        raise ValueError(f"'{nome}' non e' una tonalita' d'armonica: si scrive da C a B, per esempio Bb o F#")
    return pulito


def midi_foro_1(tonalita, famiglia="diatonica", fori=10, registro="normale"):
    """Il numero MIDI del foro 1 soffiato.
    Le armoniche da DO a FA# cominciano dal DO centrale in su, quelle da SOL a
    SI sotto: e' l'uso dei costruttori, per cui l'armonica in SOL e' la piu'
    grave delle standard e quella in FA# la piu' acuta. La cromatica a sedici
    fori aggiunge un'ottava sotto, e il registro basso, quello delle
    armoniche Low come la Low F, scende di un'ottava."""
    classe = TONALITA.index(normalizza_tonalita(tonalita))
    base = 60 + classe if classe <= 6 else 48 + classe
    if famiglia == "cromatica" and fori == 16:
        base -= 12
    if registro == "basso":
        base -= 12
    return base


def accordature_per_famiglia(famiglia):
    """Le chiavi delle accordature di una famiglia, nell'ordine del piano."""
    return [chiave for chiave, acc in ACCORDATURE.items() if famiglia in acc.famiglie]


@dataclass(frozen=True)
class Tecnica:
    """Un modo di suonare una nota: il foro, il verso dell'aria e cio' che si
    fa in piu', cioe' piegare la nota, fare l'overbend o premere il cursore.
    Su una cromatica senza valvole le tre cose si combinano: -3//< e' il
    foro 3 aspirato, con il cursore premuto, piegato di un tono."""
    foro: int
    verso: str          # '+' soffiato, '-' aspirato
    midi: int
    bend: int = 0       # semitoni di bending, una barra per semitono
    overbend: bool = False
    cursore: bool = False

    @property
    def simbolo(self):
        coda = "/" * self.bend + ("*" if self.overbend else "") + ("<" if self.cursore else "")
        return f"{self.verso}{self.foro}{coda}"

    @property
    def livello(self):
        """Quanto costa al labbro: 0 la nota naturale, anche con il cursore,
        da 1 a 3 i semitoni di bending, 4 l'overbend."""
        if self.overbend:
            return 4
        return self.bend

    @property
    def categoria(self):
        """Il nome della tecnica, per i conteggi e per le note critiche."""
        if self.overbend:
            return "overblow" if self.verso == "+" else "overdraw"
        if self.bend:
            return f"bending di {_PASSI_BENDING[self.bend]}"
        return "cursore" if self.cursore else "naturale"

    def descrizione(self):
        """La stessa tecnica detta a parole, per lo screen reader."""
        cursore = " con il cursore premuto" if self.cursore else ""
        if self.overbend:
            return f"Foro {self.foro} {self.categoria}{cursore}"
        testo = f"Foro {self.foro} {'soffiato' if self.verso == '+' else 'aspirato'}{cursore}"
        if self.bend:
            testo += f", {self.categoria}"
        return testo

    def ordine(self):
        """Chiave d'ordinamento fra i modi di suonare la stessa nota: prima il
        meno faticoso, a parita' senza cursore, poi il foro piu' grave."""
        return (self.livello, self.cursore, self.foro, self.verso)


def analizza_simbolo(testo):
    """Dal simbolo scritto, per esempio -3//, +4* o -4<, alla quintupla
    (verso, foro, bend, overbend, cursore). Solleva ValueError se il testo
    non e' scritto nella notazione."""
    pulito = str(testo).strip().replace(" ", "")
    trovato = _SIMBOLO.match(pulito)
    if not trovato:
        raise ValueError(f"'{testo}' non e' un simbolo dell'armonica: si scrive + o - seguito dal numero del foro, "
                         "poi le barre del bending, l'asterisco dell'overbend o il segno < del cursore, per esempio -3// o +4*")
    verso, foro, segni, cursore = trovato.groups()
    segni = segni or ""
    return verso, int(foro), segni.count("/"), segni == "*", cursore is not None


@dataclass(frozen=True)
class Finestra:
    """Un gruppo di fori vicini suonati insieme nello stesso verso."""
    verso: str
    cursore: bool
    primo: int
    ultimo: int
    note: tuple         # i numeri MIDI, dal foro piu' grave
    completo: bool
    mancanti: frozenset  # le classi di altezza dell'accordo che non ci sono

    @property
    def simboli(self):
        coda = "<" if self.cursore else ""
        return " ".join(f"{self.verso}{foro}{coda}" for foro in range(self.primo, self.ultimo + 1))


class HarmonicaModel:
    """Un'armonica concreta: tonalita', accordatura, famiglia, fori, valvole
    e registro.
    Calcola per ogni foro l'ancia soffiata e quella aspirata, e da queste le
    note che si ottengono piegando e con l'overbend, secondo la fisica delle
    due ance che condividono la cella: si piega l'ancia piu' acuta, verso la
    piu' grave, di tutti i semitoni che stanno fra le due; l'overbend fa
    suonare l'ancia piu' grave un semitono sopra la piu' acuta.
    Sulla cromatica il cursore alza tutto di un semitono. Se ha le valvole,
    queste tengono separate le due ance e niente si piega; se non le ha, come
    la Trochilus o una bebop, si piega come una diatonica, con il cursore
    aperto e con il cursore premuto."""

    def __init__(self, tonalita="C", accordatura="richter", fori=None, famiglia=None, valvole=None, registro="normale"):
        # Un archivio ritoccato a mano puo' avere i tipi sbagliati, come una
        # lista al posto del nome dell'accordatura o 10.0 al posto di 10: tutto
        # deve diventare ValueError, che chi chiama sa gestire, e non un crash.
        if not isinstance(accordatura, str) or accordatura not in ACCORDATURE:
            raise ValueError(f"accordatura '{accordatura}' sconosciuta: quelle conosciute sono {', '.join(ACCORDATURE)}")
        self.tonalita = normalizza_tonalita(tonalita)
        self.chiave_accordatura = accordatura
        self.accordatura = ACCORDATURE[accordatura]
        self.famiglia = famiglia or self.accordatura.famiglie[0]
        if self.famiglia not in self.accordatura.famiglie:
            raise ValueError(f"l'accordatura {self.accordatura.nome} non c'e' sulla {self.famiglia}")
        if fori is None:
            fori = 12 if 12 in self.accordatura.fori else self.accordatura.fori[0]
        if isinstance(fori, bool) or not isinstance(fori, int) or fori not in self.accordatura.fori:
            possibili = " o ".join(str(f) for f in self.accordatura.fori)
            raise ValueError(f"la {self.accordatura.nome} ha {possibili} fori, non {fori}")
        self.fori = fori
        if registro not in REGISTRI:
            raise ValueError(f"registro '{registro}' sconosciuto: e' normale o basso")
        self.registro = registro
        # Le valvole ci sono solo sulle cromatiche, e la diatonica non ne ha mai
        self.valvole = self.cromatica and (self.accordatura.valvole if valvole is None else bool(valvole))
        base = midi_foro_1(self.tonalita, self.famiglia, self.fori, self.registro)
        if self.accordatura.ripetuta:
            self.soffiati = [base + 12 * (i // 4) + self.accordatura.soffiati[i % 4] for i in range(self.fori)]
            self.aspirati = [base + 12 * (i // 4) + self.accordatura.aspirati[i % 4] for i in range(self.fori)]
        else:
            self.soffiati = [base + s for s in self.accordatura.soffiati]
            self.aspirati = [base + a for a in self.accordatura.aspirati]
        self.tecniche = self._calcola_tecniche()
        self.per_midi = {}
        for tecnica in self.tecniche:
            self.per_midi.setdefault(tecnica.midi, []).append(tecnica)
        for elenco in self.per_midi.values():
            elenco.sort(key=Tecnica.ordine)

    @property
    def cromatica(self):
        return self.famiglia == "cromatica"

    @property
    def si_piega(self):
        """Vero se bending e overbend si calcolano: sempre sulla diatonica,
        sulla cromatica solo senza valvole."""
        return not self.valvole

    def _calcola_tecniche(self):
        tecniche = []
        stati_cursore = (False, True) if self.cromatica else (False,)
        for cursore in stati_cursore:
            alzo = 1 if cursore else 0
            for foro, (soffio, aspiro) in enumerate(zip(self.soffiati, self.aspirati, strict=True), start=1):
                soffio, aspiro = soffio + alzo, aspiro + alzo
                tecniche.append(Tecnica(foro, "+", soffio, cursore=cursore))
                tecniche.append(Tecnica(foro, "-", aspiro, cursore=cursore))
                if not self.si_piega:
                    continue
                if aspiro > soffio:
                    # Fori bassi: si piega aspirando, e l'overblow sale sopra l'aspirata
                    for passo in range(1, aspiro - soffio):
                        tecniche.append(Tecnica(foro, "-", aspiro - passo, bend=passo, cursore=cursore))
                    tecniche.append(Tecnica(foro, "+", aspiro + 1, overbend=True, cursore=cursore))
                elif soffio > aspiro:
                    # Fori alti: si piega soffiando, e l'overdraw sale sopra la soffiata
                    for passo in range(1, soffio - aspiro):
                        tecniche.append(Tecnica(foro, "+", soffio - passo, bend=passo, cursore=cursore))
                    tecniche.append(Tecnica(foro, "-", soffio + 1, overbend=True, cursore=cursore))
        return tecniche

    def descrizione(self):
        """L'armonica detta per esteso, senza i nomi delle note: la tonalita'
        la mette chi mostra, nella nomenclatura dell'utente."""
        testo = f"{self.famiglia}, accordatura {self.accordatura.nome}, {self.fori} fori"
        if self.cromatica:
            testo += ", con le valvole" if self.valvole else ", senza valvole"
        if self.registro == "basso":
            testo += ", registro basso"
        return testo

    def estensione(self):
        """La nota piu' grave e la piu' acuta, overbend compresi."""
        return min(self.per_midi), max(self.per_midi)

    def tecniche_per_nota(self, midi):
        """Tutti i modi di suonare la nota, dal meno faticoso; vuoto se non c'e'."""
        return list(self.per_midi.get(midi, []))

    def migliore(self, midi):
        """Il modo meno faticoso di suonare la nota, o None."""
        elenco = self.per_midi.get(midi)
        return elenco[0] if elenco else None

    def da_simbolo(self, testo):
        """La tecnica che il simbolo indica su questa armonica.
        Solleva ValueError con la spiegazione se il simbolo e' scritto male o
        se su questa armonica quella tecnica non esiste: e' un'occasione per
        imparare perche', non solo un rifiuto."""
        verso, foro, bend, overbend, cursore = analizza_simbolo(testo)
        if not 1 <= foro <= self.fori:
            raise ValueError(f"questa armonica ha i fori da 1 a {self.fori}")
        if cursore and not self.cromatica:
            raise ValueError("il cursore c'e' solo sulle cromatiche")
        if (bend or overbend) and not self.si_piega:
            raise ValueError("questa cromatica ha le valvole, che separano le due ance: Chitabry non calcola bending ne' overbend, "
                             "le note in piu' le da' il cursore, con il segno <")
        for tecnica in self.tecniche:
            if (tecnica.foro, tecnica.verso, tecnica.bend, tecnica.overbend, tecnica.cursore) == (foro, verso, bend, overbend, cursore):
                return tecnica
        raise ValueError(self._perche_no(foro, verso, bend, overbend, cursore))

    def _perche_no(self, foro, verso, bend, overbend, cursore=False):
        """Perche' su questo foro la tecnica chiesta non c'e'. Il cursore alza
        le due ance insieme, quindi le ragioni sono le stesse."""
        soffio, aspiro = self.soffiati[foro - 1], self.aspirati[foro - 1]
        coda = "<" if cursore else ""
        if aspiro > soffio:
            piega, salto = "-", aspiro - soffio
        elif soffio > aspiro:
            piega, salto = "+", soffio - aspiro
        else:
            return f"il foro {foro} ha le due ance sulla stessa nota: non si piega e non fa overbend"
        nome_piega = "aspirando" if piega == "-" else "soffiando"
        if overbend:
            giusto = "+" if piega == "-" else "-"
            return f"sul foro {foro} l'overbend si fa {'soffiando' if giusto == '+' else 'aspirando'}: {giusto}{foro}*{coda}"
        # Prima il semitono solo: su quei fori non si piega in nessun verso, e
        # suggerire l'altro verso proporrebbe un simbolo che non esiste
        if salto <= 1:
            return f"il foro {foro} non si piega: fra le sue due ance c'e' un semitono solo"
        if verso != piega:
            return f"il foro {foro} si piega {nome_piega}, perche' e' l'ancia piu' acuta a scendere: {piega}{foro}/{coda}"
        massimo = salto - 1
        quanto = "un semitono" if massimo == 1 else f"{massimo} semitoni"
        return f"il foro {foro} {nome_piega} si piega al massimo di {quanto}, {piega}{foro}{'/' * massimo}{coda}"

    def accordi(self, classi):
        """I gruppi di fori vicini, stesso verso e senza tecniche, le cui note
        stanno tutte nell'accordo. Un gruppo e' grande quanto le note distinte
        dell'accordo, al massimo quattro, cioe' quanto si prende con la bocca.
        Restituisce i gruppi completi; se non ce ne sono, i parziali con piu'
        note dell'accordo, almeno due diverse, cercati anche su meno fori:
        su un'armonica in DO il LA minore non sta in tre fori vicini, ma DO e
        MI stanno in due."""
        classi = frozenset(c % 12 for c in classi)
        larghezza_piena = max(2, min(len(classi), 4))
        versi = [("+", False, self.soffiati), ("-", False, self.aspirati)]
        if self.cromatica:
            versi += [("+", True, [n + 1 for n in self.soffiati]), ("-", True, [n + 1 for n in self.aspirati])]
        candidate = []
        for larghezza in range(larghezza_piena, 1, -1):
            for verso, cursore, note in versi:
                for inizio in range(self.fori - larghezza + 1):
                    gruppo = tuple(note[inizio:inizio + larghezza])
                    presenti = {n % 12 for n in gruppo}
                    if not presenti <= classi or len(presenti) < 2:
                        continue
                    mancanti = classi - presenti
                    candidate.append(Finestra(verso, cursore, inizio + 1, inizio + larghezza, gruppo, not mancanti, frozenset(mancanti)))
        complete = [f for f in candidate if f.completo and len(f.note) == larghezza_piena]
        if complete:
            return complete
        if not candidate:
            return []
        # Fra i parziali, quelli con piu' note dell'accordo; a parita', i piu'
        # larghi, e di un gruppo non si ripetono i pezzi che ci stanno dentro.
        meglio = max(len(classi) - len(f.mancanti) for f in candidate)
        scelte = []
        for finestra in candidate:
            if len(classi) - len(finestra.mancanti) != meglio:
                continue
            if any(altra.verso == finestra.verso and altra.cursore == finestra.cursore
                   and altra.primo <= finestra.primo and finestra.ultimo <= altra.ultimo for altra in scelte):
                continue
            scelte.append(finestra)
        return sorted(scelte, key=lambda f: (f.cursore, f.verso != "+", f.primo))


def posizione(tonalita, classe_tonica):
    """La posizione, da 1 a 12, in cui si suona una scala con quella tonica:
    1 piu' le quinte che separano la tonalita' dell'armonica dalla tonica."""
    distanza = (classe_tonica - TONALITA.index(normalizza_tonalita(tonalita))) % 12
    # Sette semitoni sono una quinta, e 7 e' l'inverso di se stesso modulo 12
    return (distanza * 7) % 12 + 1


def descrivi_posizione(numero):
    """La posizione a parole: l'ordinale, il nome tradizionale se c'e', e
    quante quinte separano la tonica dalla tonalita' dell'armonica."""
    testo = f"{ORDINALI[numero - 1]} posizione"
    if numero in NOMI_POSIZIONE:
        testo += f" ({NOMI_POSIZIONE[numero]})"
    passi = numero - 1
    if passi == 0:
        return testo + ", la tonica e' quella dell'armonica"
    if passi <= 6:
        quinte = "una quinta" if passi == 1 else f"{passi} quinte"
        return testo + f", la tonica sta {quinte} sopra quella dell'armonica"
    quinte = "una quinta" if passi == 11 else f"{12 - passi} quinte"
    return testo + f", la tonica sta {quinte} sotto quella dell'armonica"


def tonalita_per(classe_tonica, numero):
    """La tonalita' dell'armonica su cui una tonica si suona nella posizione
    indicata: per il SOL in seconda, l'armonica in DO."""
    return TONALITA[(classe_tonica - 7 * (numero - 1)) % 12]


def ottava_comoda(modello, classe_tonica, intervalli):
    """Il tratto di un'ottava, dalla tonica alla tonica sopra, che su questa
    armonica chiede meno fatica, a parita' il piu' grave. Restituisce la
    coppia (numero MIDI della tonica, tecnica migliore di ogni nota), con
    None dove la nota manca; None se la tonica non sta nell'estensione."""
    gradi = [*sorted({i % 12 for i in intervalli}), 12]
    grave, acuta = modello.estensione()
    trovata = None
    for tonica in range(grave, acuta + 1):
        if tonica % 12 != classe_tonica:
            continue
        tecniche = [modello.migliore(tonica + g) for g in gradi]
        if trovata is None or fatica(tecniche) < fatica(trovata[1]):
            trovata = (tonica, tecniche)
    return trovata


def tabella_posizioni(modello, intervalli):
    """La stessa scala nelle dodici posizioni di questa armonica.
    intervalli sono i semitoni delle note della scala sopra la tonica. Per
    ogni posizione restituisce la quaterna (numero, classe della tonica che
    la scala ha su questa armonica, tecnica migliore di ogni sua nota su
    tutta l'estensione, ottava piu' comoda come la da' ottava_comoda).
    Spostare la tonica sull'armonica o cambiare armonica per la stessa tonica
    chiede le stesse tecniche, a parte gli estremi dell'estensione: per
    questo una tabella sola risponde a tutte e due le domande."""
    base = TONALITA.index(modello.tonalita)
    grave, acuta = modello.estensione()
    righe = []
    for numero in range(1, 13):
        tonica = (base + 7 * (numero - 1)) % 12
        classi = {(tonica + i) % 12 for i in intervalli}
        estensione = [modello.migliore(m) for m in range(grave, acuta + 1) if m % 12 in classi]
        righe.append((numero, tonica, estensione, ottava_comoda(modello, tonica, intervalli)))
    return righe


def piu_comode(righe, quante=3):
    """Le posizioni piu' comode di una tabella_posizioni: prima la fatica
    dell'ottava piu' comoda, che e' quella che si suona, poi quella di tutta
    l'estensione, poi il numero. La somma su tutta l'estensione, da sola,
    premia le posizioni che evitano gli overbend dell'ottava acuta, che in
    seconda posizione nessuno usa per il blues."""
    def chiave(riga):
        ottava = riga[3]
        return (fatica(ottava[1]) if ottava else float("inf"), fatica(riga[2]), riga[0])
    return [riga[0] for riga in sorted(righe, key=chiave)[:quante]]


def conta_tecniche(tecniche):
    """Quante volte compare ogni categoria in un elenco di tecniche, con
    None per le note che l'armonica non ha. Ordinate dalla piu' facile."""
    conteggi = {}
    for tecnica in sorted((t for t in tecniche if t is not None), key=Tecnica.ordine):
        conteggi[tecnica.categoria] = conteggi.get(tecnica.categoria, 0) + 1
    mancanti = sum(1 for t in tecniche if t is None)
    if mancanti:
        conteggi["fuori dall'armonica"] = mancanti
    return conteggi


# Quanto pesa una nota presa con il cursore: meno di un bending, ma non
# niente. Senza peso, su una cromatica ogni posizione aveva fatica zero e la
# classifica delle posizioni non misurava niente.
FATICA_CURSORE = 0.5


def fatica(tecniche):
    """Un numero per confrontare due tratti di scala: la somma dei livelli,
    mezzo punto per ogni nota con il cursore, e le note che mancano che
    pesano piu' di qualunque tecnica."""
    return sum(10 if t is None else t.livello + (FATICA_CURSORE if t.cursore else 0) for t in tecniche)
