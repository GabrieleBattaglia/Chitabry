from music21 import pitch, scale, harmony
import inspect
import re
from typing import Dict
from pathlib import Path

SCALE_CATALOG: list[Dict] = []
SCALE_TYPES_DICT: Dict[str, str] = {}
USER_CHORD_DICT: Dict[str, str] = {}

class ScaleException(Exception):
    """Classe base per errori relativi alle scale in questo modulo."""
    pass

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
        if not inspect.isabstract(subclass) and issubclass(subclass, scale.ConcreteScale):
            found_classes.add(subclass)
        found_classes.update(_find_scale_subclasses(subclass))
    return found_classes

def _format_friendly_name(programmatic_id, paradigm):
    """Helper per creare nomi leggibili."""
    name = programmatic_id
    if paradigm == 'concrete':
        if name.endswith('Scale'):
            name = name[:-5]
        # Modifica suggerita per inserire spazi: usa regex
        name = re.sub(r'(?<!^)(?=[A-Z])', ' ', name).title()
    elif paradigm == 'scala':
        name = ' '.join(a.capitalize() for a in name.split('_'))
    return name.strip()

def get_user_chord_dictionary() -> Dict[str, str]:
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
def build_scale_catalog() -> list[Dict]:
    """
    Esegue l'introspezione di music21 per costruire un dizionario
    unificato di tutte le scale disponibili (Concrete e Scala).

    Restituisce:
        list[dict]: Un elenco di dizionari, ognuno
                    rappresentante una scala.
    """
    catalog = []
    processed_ids = set() # Per evitare ID duplicati

    # --- Paradigma 1: Sottoclassi ConcreteScale ---
    print("   Analisi classi ConcreteScale...")
    try:
        # Usiamo scale.Scale come base per la ricorsione iniziale,
        # _find_scale_subclasses filtrerà per ConcreteScale e non astratte.
        concrete_classes = _find_scale_subclasses(scale.Scale)

        for cls in sorted(list(concrete_classes), key=lambda x: x.__name__):
            prog_id = cls.__name__
            if prog_id not in processed_ids:
                catalog.append({
                    'programmatic_id': prog_id,
                    'friendly_name': _format_friendly_name(prog_id, 'concrete'),
                    'paradigm': 'concrete'
                    # 'class': cls # Rimosso per semplicità
                })
                processed_ids.add(prog_id)
    except Exception as e:
         print(f"Attenzione: Errore durante introspezione classi ConcreteScale: {e}")

    # --- Paradigma 2: Archivio ScalaScale ---
    print("   Analisi archivio Scala (.scl)...")
    try:
        scala_paths = scale.scala.getPaths()

        # Ordina in modo robusto
        def get_sort_key(p):
            try: return Path(p).stem.lower()
            except Exception: return str(p).lower()
        sorted_scala_paths = sorted(scala_paths, key=get_sort_key)

        for scl_path_obj in sorted_scala_paths:
            try:
                scl_path = Path(scl_path_obj) # Assicura sia Path
                prog_id = scl_path.stem
                filename_scl = scl_path.name

                if prog_id not in processed_ids and scl_path.is_file():
                    friendly_name_raw = _format_friendly_name(prog_id, 'scala')
                    description = friendly_name_raw
                    try:
                         scale_info_data = scale.scala.getScaleInfo(filename_scl)
                         description = scale_info_data.get('description', friendly_name_raw)
                    except Exception: pass # Ignora errori lettura descrizione

                    catalog.append({
                        'programmatic_id': prog_id,
                        'friendly_name': description if description else friendly_name_raw,
                        'paradigm': 'scala'
                        # 'class': scale.scala.ScalaScale # Rimosso per semplicità
                    })
                    processed_ids.add(prog_id)
            except Exception as path_error:
                 print(f"Attenzione: Errore nell'elaborare il percorso Scala '{scl_path_obj}': {path_error}")

    except ImportError: print("Attenzione: Modulo 'scala.scala' non trovato.")
    except AttributeError: print("Attenzione: Funzione 'getPaths' non trovata in scala.scala.")
    except Exception as e: print(f"Attenzione: Impossibile caricare l'archivio Scala. {e}")

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
        if len(parts) != 3: raise ValueError("Formato non valido")
        paradigm, tonic_str, scale_id = parts
    except ValueError:
        raise InvalidUSIFormatError(usi_string)

    try:
        tonic_pitch = pitch.Pitch(tonic_str)
    except Exception as e:
        raise ScaleException(f"Tonica non valida '{tonic_str}': {e}")

    # --- Routing del Paradigma ---
    if paradigm == 'concrete':
        try:
            scale_class = getattr(scale, scale_id) # Recupera classe da music21.scale
            # Istanzia passando solo la tonica
            return scale_class(tonic_pitch)
        except AttributeError:
            raise UnknownScaleError(paradigm, scale_id)
        except Exception as e:
            raise ScaleException(f"Errore istanziazione {scale_id}({tonic_str}): {e}")

    elif paradigm == 'scala':
        scl_filename = scale_id + ".scl"
        try:
            # Istanzia ScalaScale (accedendo da scale, come corretto prima)
            return scale.ScalaScale(tonic_pitch, scl_filename)
        except FileNotFoundError:
             raise UnknownScaleError(paradigm, f"File {scl_filename} non trovato.")
        except AttributeError: # Se scale.ScalaScale non esiste
             raise ScaleException("Classe ScalaScale non trovata.")
        except Exception as e:
            raise ScaleException(f"Errore istanziazione ScalaScale('{tonic_str}', '{scl_filename}'): {e}")

    elif paradigm == 'custom':
        try:
            pitch_list_str = scale_id.split(',')
            pitch_list = [pitch.Pitch(p.strip()) for p in pitch_list_str if p.strip()]
            if not pitch_list: raise ValueError("Lista pitch vuota")
            # Istanzia ConcreteScale con pitches e tonic
            return scale.ConcreteScale(pitches=pitch_list, tonic=tonic_pitch)
        except Exception as e:
            raise ScaleException(f"Errore parsing/creazione scala 'custom' da '{scale_id}': {e}")

    else:
        raise ScaleException(f"Paradigma USI sconosciuto: '{paradigm}'")

