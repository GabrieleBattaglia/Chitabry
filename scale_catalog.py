# Chitabry, catalogo delle scale e degli accordi: introspezione di music21.
# Autori: Gabriele Battaglia (IZ4APU) & ClaudIA (Claude Fable 5.1, UltraCode).
# Revisione 1 del 2026-09-09: le eccezioni catturate sono quelle che music21
# e il file system sollevano davvero, e ogni errore rilanciato conserva la causa.
# Dalla 9.3.2 le scale dell'archivio Scala portano la loro descrizione, letta
# dal file, e le classi generiche di music21 non stanno piu' nel catalogo.
# Dalla 9.5.0 il catalogo ha un terzo paradigma, comune: le scale di tutti i
# giorni, temperate e con i nomi italiani, che music21 non ha, o non ha in
# una forma che si possa esercitare, come la blues.

import inspect
import re
from pathlib import Path

from music21 import harmony, pitch, scale
from music21.exceptions21 import Music21Exception

SCALE_CATALOG: list[dict] = []
# Le scale comuni: chiave, nome italiano, intervalli dalla tonica come li
# scrive music21, e la formula in gradi. Gli intervalli, e non i semitoni,
# danno la grafia giusta: il SOL blues ha il REb, non il DO#.
SCALE_COMUNI = (
    ("maggiore", "maggiore", ("P1", "M2", "M3", "P4", "P5", "M6", "M7"), "1 2 3 4 5 6 7, il modo ionio"),
    ("minore_naturale", "minore naturale", ("P1", "M2", "m3", "P4", "P5", "m6", "m7"), "1 2 b3 4 5 b6 b7, il modo eolio"),
    ("minore_armonica", "minore armonica", ("P1", "M2", "m3", "P4", "P5", "m6", "M7"), "1 2 b3 4 5 b6 7"),
    ("minore_melodica", "minore melodica", ("P1", "M2", "m3", "P4", "P5", "M6", "M7"), "1 2 b3 4 5 6 7, quella del jazz, uguale in salita e in discesa"),
    ("dorica", "dorica", ("P1", "M2", "m3", "P4", "P5", "M6", "m7"), "1 2 b3 4 5 6 b7"),
    ("frigia", "frigia", ("P1", "m2", "m3", "P4", "P5", "m6", "m7"), "1 b2 b3 4 5 b6 b7"),
    ("lidia", "lidia", ("P1", "M2", "M3", "A4", "P5", "M6", "M7"), "1 2 3 #4 5 6 7"),
    ("misolidia", "misolidia", ("P1", "M2", "M3", "P4", "P5", "M6", "m7"), "1 2 3 4 5 6 b7"),
    ("locria", "locria", ("P1", "m2", "m3", "P4", "d5", "m6", "m7"), "1 b2 b3 4 b5 b6 b7"),
    ("pentatonica_maggiore", "pentatonica maggiore", ("P1", "M2", "M3", "P5", "M6"), "1 2 3 5 6"),
    ("pentatonica_minore", "pentatonica minore", ("P1", "m3", "P4", "P5", "m7"), "1 b3 4 5 b7"),
    ("blues", "blues", ("P1", "m3", "P4", "d5", "P5", "m7"), "1 b3 4 b5 5 b7, la pentatonica minore con la quinta diminuita: quella dell'armonica in seconda posizione"),
    ("blues_maggiore", "blues maggiore", ("P1", "M2", "m3", "M3", "P5", "M6"), "1 2 b3 3 5 6, la pentatonica maggiore con la terza minore"),
    ("bebop_dominante", "bebop dominante", ("P1", "M2", "M3", "P4", "P5", "M6", "m7", "M7"), "1 2 3 4 5 6 b7 7, la misolidia con la settima maggiore di passaggio"),
    ("bebop_maggiore", "bebop maggiore", ("P1", "M2", "M3", "P4", "P5", "m6", "M6", "M7"), "1 2 3 4 5 b6 6 7, la maggiore con la sesta minore di passaggio"),
    ("frigia_dominante", "frigia dominante", ("P1", "m2", "M3", "P4", "P5", "m6", "m7"), "1 b2 3 4 5 b6 b7, quella del flamenco e della musica ebraica"),
    ("toni_interi", "toni interi", ("P1", "M2", "M3", "A4", "A5", "m7"), "1 2 3 #4 #5 b7, l'esatonale"),
    ("diminuita_tono_semitono", "diminuita tono semitono", ("P1", "M2", "m3", "P4", "d5", "m6", "M6", "M7"), "1 2 b3 4 b5 b6 6 7, l'ottatonica che comincia con un tono"),
    ("diminuita_semitono_tono", "diminuita semitono tono", ("P1", "m2", "m3", "M3", "A4", "P5", "M6", "m7"), "1 b2 b3 3 #4 5 6 b7, l'ottatonica che comincia con un semitono"),
    ("cromatica", "cromatica", ("P1", "m2", "M2", "m3", "M3", "P4", "A4", "P5", "m6", "M6", "m7", "M7"), "le dodici note"),
)
_COMUNI_PER_CHIAVE = {voce[0]: voce for voce in SCALE_COMUNI}
# Le classi di music21 dette in italiano, per il menu del secondo gruppo.
DESCRIZIONI_MUSIC21 = {
    "ChromaticScale": "cromatica, le dodici note",
    "DorianScale": "dorica",
    "HarmonicMinorScale": "minore armonica",
    "HypoaeolianScale": "ipoeolia, cioe' l'eolia plagale, che si stende dalla quarta sotto la tonica alla quinta sopra",
    "HypodorianScale": "ipodorica, la dorica plagale, dalla quarta sotto la tonica alla quinta sopra",
    "HypolocrianScale": "ipolocria, la locria plagale, dalla quarta sotto la tonica alla quinta sopra",
    "HypolydianScale": "ipolidia, la lidia plagale, dalla quarta sotto la tonica alla quinta sopra",
    "HypomixolydianScale": "ipomisolidia, la misolidia plagale, dalla quarta sotto la tonica alla quinta sopra",
    "HypophrygianScale": "ipofrigia, la frigia plagale, dalla quarta sotto la tonica alla quinta sopra",
    "LocrianScale": "locria",
    "LydianScale": "lidia",
    "MajorScale": "maggiore",
    "MelodicMinorScale": "minore melodica: sale con la sesta e la settima maggiori, scende come la naturale",
    "MinorScale": "minore naturale",
    "MixolydianScale": "misolidia",
    "OctatonicScale": "ottatonica, la diminuita tono semitono",
    "PhrygianScale": "frigia",
    "RagAsawari": "raga Asawari, indiano, con la salita e la discesa diverse",
    "RagMarwa": "raga Marwa, indiano, con la salita e la discesa diverse",
    "WeightedHexatonicBlues": "blues probabilistica: a ogni esecuzione music21 decide se mettere la quinta diminuita",
    "WholeToneScale": "toni interi, l'esatonale",
}
# Le classi di music21 che non sono scale ma basi per costruirne: istanziate
# con la sola tonica danno una scala vuota, di due o tre note, o ripetono la
# cromatica e la maggiore. Fino alla 9.3.1 stavano nel catalogo come scale.
CLASSI_GENERICHE = frozenset({"ConcreteScale", "CyclicalScale", "OctaveRepeatingScale", "SieveScale",
                              "ScalaScale", "DiatonicScale"})
SCALE_TYPES_DICT: dict[str, str] = {}
USER_CHORD_DICT: dict[str, str] = {}


class ScaleException(Exception):
    """Classe base per errori relativi alle scale in questo modulo."""

class InvalidUSIFormatError(ScaleException):
    """Sollevata quando una stringa USI non è nel formato atteso."""
    def __init__(self, usi_string):
        message = (
            f"La stringa USI '{usi_string}' non è valida. "
            "Il formato atteso è 'paradigm:tonic:scale_id'."
        )
        super().__init__(message)
class UnknownScaleError(ScaleException):
    """Sollevata quando uno scale_id non può essere trovato o istanziato."""
    def __init__(self, paradigm, scale_id):
        message = (
            f"Impossibile trovare/istanziare la scala con id '{scale_id}' "
            f"per il paradigma '{paradigm}'."
        )
        super().__init__(message)

# --- Funzioni Helper per Introspezione (dal documento) ---

def _find_scale_subclasses(base_class):
    """
    Funzione helper ricorsiva per trovare tutte le sottoclassi
    ConcreteScale valide, escludendo il modulo key.
    """
    found_classes = set()
    try:
        subclasses = base_class.__subclasses__()
    except TypeError:
        subclasses = []

    for subclass in subclasses:
        if subclass.__module__.startswith('music21.key'):
            continue
        if (not inspect.isabstract(subclass) and issubclass(subclass, scale.ConcreteScale)
                and subclass.__name__ not in CLASSI_GENERICHE):
            found_classes.add(subclass)
        found_classes.update(_find_scale_subclasses(subclass))
    return found_classes

def _format_friendly_name(programmatic_id, paradigm):
    """Helper per creare nomi leggibili."""
    name = programmatic_id
    if paradigm == 'concrete':
        name = name.removesuffix('Scale')
        # Modifica suggerita per inserire spazi: usa regex
        name = re.sub(r'(?<!^)(?=[A-Z])', ' ', name).title()
    elif paradigm == 'scala':
        name = ' '.join(a.capitalize() for a in name.split('_'))
    return name.strip()

def scala_comune(tonica, chiave):
    """La scala comune indicata dalla chiave, costruita sulla tonica, che e'
    un pitch di music21, fino all'ottava sopra. UnknownScaleError se la
    chiave non c'e'."""
    voce = _COMUNI_PER_CHIAVE.get(chiave)
    if voce is None:
        raise UnknownScaleError("comune", chiave)
    altezze = [tonica.transpose(intervallo) for intervallo in voce[2]] + [tonica.transpose("P8")]
    return scale.ConcreteScale(tonic=tonica, pitches=altezze)


def descrizione_scl(percorso) -> str:
    """La riga di descrizione di un file .scl dell'archivio Scala: per il
    formato e' la prima che non comincia con il punto esclamativo, che apre i
    commenti, e puo' anche essere vuota. I file sono in utf-8 o, i piu'
    vecchi, in latin-1, che legge qualunque byte.
    Fino alla 9.3.1 la descrizione si chiedeva a getScaleInfo, che music21
    non ha piu': ogni voce restava con il nome del file, come 05-19, e la
    ricerca per parola non trovava le scale per quello che sono."""
    for codifica in ("utf-8", "latin-1"):
        try:
            with open(percorso, encoding=codifica) as f:
                for riga in f:
                    if not riga.startswith("!"):
                        return riga.strip()
            return ""
        except UnicodeDecodeError:
            continue
        except OSError:
            return ""
    return ""


def get_user_chord_dictionary() -> dict[str, str]:
    """
    Esegue l'introspezione di music21.harmony per costruire un
    dizionario pulito di tipi di accordi per l'interfaccia utente.

    Ritorna:
        Dict[str, str]: Un dizionario dove la chiave è
        l'abbreviazione (shorthand) primaria usata per la costruzione
        e il valore è il nome leggibile per il menu.
    """
    user_dict = {}
    processed_types = set() # Per evitare duplicati dovuti a shorthand non unici

    # Itera sull'elenco master dei tipi di accordo canonici
    for chord_type in harmony.CHORD_TYPES:

        # Salta tipi già processati (se getCurrentAbbreviationFor non è univoco)
        if chord_type in processed_types:
            continue

        # 1. Ottiene l'abbreviazione "preferita" dalla libreria -> CHIAVE
        primary_shorthand = harmony.getCurrentAbbreviationFor(chord_type)

        # Evita di sovrascrivere una chiave già assegnata (es. '' per major)
        # Diamo priorità alla prima assegnazione trovata (che di solito è quella corretta)
        if primary_shorthand in user_dict:
             continue

        # 2. Pulisce il nome canonico per la visualizzazione -> VALORE
        readable_name = chord_type.replace('-', ' ').title()

        # Correzioni specifiche per leggibilità
        if primary_shorthand == '' and chord_type == 'major':
            readable_name = 'Major' # Triade Maggiore
        elif primary_shorthand == 'm' and chord_type == 'minor':
            readable_name = 'Minor' # Triade Minore
        elif primary_shorthand == 'dim' and chord_type == 'diminished':
            readable_name = 'Diminished' # Triade Diminuita
        elif primary_shorthand == 'aug' and chord_type == 'augmented':
            readable_name = 'Augmented' # Triade Aumentata
        elif primary_shorthand == 'm7b5':
             readable_name = 'Half-Diminished (m7b5)' # Più chiaro
        elif chord_type == 'power':
             readable_name = 'Power Chord (5)'
        # Aggiungi altre correzioni se necessario per migliorare la leggibilità

        user_dict[primary_shorthand] = readable_name
        processed_types.add(chord_type) # Segna il tipo canonico come processato


    # --- MODIFICA CHIAVE ---
    # Ordina il dizionario principale PER VALORE (nome leggibile)
    sorted_dict = dict(sorted(user_dict.items(), key=lambda item: item[1]))

    # Aggiungi l'opzione di ricerca fuzzy ALLA FINE con la chiave '...'
    sorted_dict["..."] = ">> Cerca tipo di accordo..."
    # --- FINE MODIFICA CHIAVE ---

    return sorted_dict
def build_scale_catalog() -> list[dict]:
    """
    Esegue l'introspezione di music21 per costruire un dizionario
    unificato di tutte le scale disponibili (Concrete e Scala).

    Restituisce:
        list[dict]: Un elenco di dizionari, ognuno
                    rappresentante una scala.
    """
    catalog = []
    processed_ids = set() # Per evitare ID duplicati

    # --- Paradigma 0: le scale comuni di Chitabry ---
    # Le chiavi non entrano in processed_ids: hanno un paradigma loro, e un
    # file Scala con lo stesso nome restera' una scala diversa.
    for chiave, nome, _intervalli, formula in SCALE_COMUNI:
        catalog.append({'programmatic_id': chiave, 'friendly_name': nome, 'paradigm': 'comune', 'descrizione': formula})

    # --- Paradigma 1: Sottoclassi ConcreteScale ---
    print("   Analisi classi ConcreteScale...")
    try:
        # Usiamo scale.Scale come base per la ricorsione iniziale,
        # _find_scale_subclasses filtrerà per ConcreteScale e non astratte.
        concrete_classes = _find_scale_subclasses(scale.Scale)

        for cls in sorted(concrete_classes, key=lambda x: x.__name__):
            prog_id = cls.__name__
            if prog_id not in processed_ids:
                catalog.append({
                    'programmatic_id': prog_id,
                    'friendly_name': _format_friendly_name(prog_id, 'concrete'),
                    'paradigm': 'concrete',
                    'descrizione': DESCRIZIONI_MUSIC21.get(prog_id, ""),
                })
                processed_ids.add(prog_id)
    except (TypeError, AttributeError) as e:
         print(f"Attenzione: Errore durante introspezione classi ConcreteScale: {e}")

    # --- Paradigma 2: Archivio ScalaScale ---
    print("   Analisi archivio Scala (.scl)...")
    try:
        scala_paths = scale.scala.getPaths()

        # Ordina in modo robusto
        def get_sort_key(p):
            try:
                return Path(p).stem.lower()
            except (TypeError, ValueError):
                return str(p).lower()
        sorted_scala_paths = sorted(scala_paths, key=get_sort_key)

        for scl_path_obj in sorted_scala_paths:
            try:
                scl_path = Path(scl_path_obj) # Assicura sia Path
                prog_id = scl_path.stem

                if prog_id not in processed_ids and scl_path.is_file():
                    friendly_name_raw = _format_friendly_name(prog_id, 'scala')
                    # La descrizione e' un di piu': senza, resta il nome del file
                    description = descrizione_scl(scl_path)

                    catalog.append({
                        'programmatic_id': prog_id,
                        'friendly_name': description if description else friendly_name_raw,
                        'paradigm': 'scala'
                        # 'class': scale.scala.ScalaScale # Rimosso per semplicità
                    })
                    processed_ids.add(prog_id)
            except (OSError, ValueError, TypeError, Music21Exception) as path_error:
                 print(f"Attenzione: Errore nell'elaborare il percorso Scala '{scl_path_obj}': {path_error}")

    except ImportError: print("Attenzione: Modulo 'scala.scala' non trovato.")
    except AttributeError: print("Attenzione: Funzione 'getPaths' non trovata in scala.scala.")
    except (Music21Exception, OSError) as e: print(f"Attenzione: Impossibile caricare l'archivio Scala. {e}")

    # Ordina catalogo finale
    catalog.sort(key=lambda x: x.get('friendly_name', '').lower())

    print(f"   ...Catalogo scale costruito con {len(catalog)} voci.")
    return catalog

def get_scale_from_usi(usi_string: str) -> scale.Scale:
    """
    Analizza un Identificatore di Scala Univoco (USI) e
    restituisce un'istanza di music21.scale.Scale.
    (Basato sulla Sezione 4.2 del documento)
    """
    try:
        parts = usi_string.split(':', 2)
        if len(parts) != 3:
            raise ValueError("Formato non valido")
        paradigm, tonic_str, scale_id = parts
    except ValueError as e:
        raise InvalidUSIFormatError(usi_string) from e
    try:
        tonic_pitch = pitch.Pitch(tonic_str)
    except (Music21Exception, ValueError) as e:
        raise ScaleException(f"Tonica non valida '{tonic_str}': {e}") from e

    # --- Routing del Paradigma ---
    if paradigm == 'concrete':
        try:
            scale_class = getattr(scale, scale_id) # Recupera classe da music21.scale
            # Istanzia passando solo la tonica
            return scale_class(tonic_pitch)
        except AttributeError as e:
            raise UnknownScaleError(paradigm, scale_id) from e
        except (Music21Exception, TypeError, ValueError) as e:
            raise ScaleException(f"Errore istanziazione {scale_id}({tonic_str}): {e}") from e

    elif paradigm == 'scala':
        scl_filename = scale_id + ".scl"
        try:
            # Istanzia ScalaScale (accedendo da scale, come corretto prima)
            return scale.ScalaScale(tonic_pitch, scl_filename)
        except FileNotFoundError as e:
            raise UnknownScaleError(paradigm, f"File {scl_filename} non trovato.") from e
        except AttributeError as e:  # Se scale.ScalaScale non esiste
            raise ScaleException("Classe ScalaScale non trovata.") from e
        except (Music21Exception, OSError, TypeError, ValueError) as e:
            raise ScaleException(f"Errore istanziazione ScalaScale('{tonic_str}', '{scl_filename}'): {e}") from e

    elif paradigm == 'comune':
        try:
            return scala_comune(tonic_pitch, scale_id)
        except (Music21Exception, TypeError, ValueError) as e:
            raise ScaleException(f"Errore costruzione della scala comune {scale_id} su {tonic_str}: {e}") from e

    elif paradigm == 'custom':
        try:
            pitch_list_str = scale_id.split(',')
            pitch_list = [pitch.Pitch(p.strip()) for p in pitch_list_str if p.strip()]
            if not pitch_list: raise ValueError("Lista pitch vuota")
            # Istanzia ConcreteScale con pitches e tonic
            return scale.ConcreteScale(pitches=pitch_list, tonic=tonic_pitch)
        except (Music21Exception, TypeError, ValueError) as e:
            raise ScaleException(f"Errore parsing/creazione scala 'custom' da '{scale_id}': {e}") from e

    else:
        raise ScaleException(f"Paradigma USI sconosciuto: '{paradigm}'")

